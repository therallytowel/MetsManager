import pandas as pd
import os
import random
from atproto import Client
import re

def clean_name(name):
    # Clean B-Ref junk
    clean = re.sub(r'[*#+?0-9]', '', str(name)).replace('HOF', '').strip()
    
    # Brute-force fix for encoding artifacts (the "Alvarez" fix)
    fixes = {'ÃƒÂ': 'A', 'Ã¡': 'a', 'Ã©': 'e', 'Ã­': 'i', 'Ã³': 'o', 'Ãº': 'u', 'Ã±': 'n'}
    for bad, good in fixes.items():
        clean = clean.replace(bad, good)

    parts = clean.split()
    if len(parts) >= 2:
        return f"{parts[0][0]}. {parts[-1]}"
    return clean

def post_lineup():
    game_file = "game_number.txt"
    current_game = 1
    if os.path.exists(game_file):
        with open(game_file, "r") as f:
            try: current_game = int(f.read().strip())
            except: pass

    try:
        batters = pd.read_csv('mets_batters.csv', encoding='latin1')
        pitchers = pd.read_csv('mets_pitchers.csv', encoding='latin1')
        batters.columns = [re.sub(r'\W+', '', str(c)) for c in batters.columns]
        pitchers.columns = [re.sub(r'\W+', '', str(c)) for c in pitchers.columns]
        pos_col = next((c for c in batters.columns if 'Pos' in c), batters.columns[-1])
        batters['PosSearch'] = batters[pos_col].astype(str).str.upper()
    except Exception as e:
        print(f"❌ Load Error: {e}")
        return

    # Positions 2 through 9
    slots = [('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), ('7|O', 'LF'), ('8|O', 'CF'), ('9|O', 'RF')]
    final_roster = []
    used_names = set()

    for code, label in slots:
        mask = batters['PosSearch'].str.contains(code, na=False)
        pool = batters[mask & ~batters['Name'].isin(used_names)]
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used_names.add(sel['Name'])
            val = pd.to_numeric(sel['OPS'], errors='coerce') or 0.0
            final_roster.append({'Name': sel['Name'], 'Pos': label, 'Val': val})

    # DH LOGIC: Must be a position player (PosSearch contains any digit 2-9)
    # This keeps the Justin Verlanders out of the DH spot.
    dh_pool = batters[
        ~batters['Name'].isin(used_names) & 
        batters['PosSearch'].str.contains(r'[2-9]', na=False)
    ]
    
    if not dh_pool.empty:
        dh_sel = dh_pool.sample(1).iloc[0]
        final_roster.append({
            'Name': dh_sel['Name'], 
            'Pos': 'DH', 
            'Val': pd.to_numeric(dh_sel['OPS'], errors='coerce') or 0.0
        })

    # Pitching Staff
    sp_row = pitchers.sample(1).iloc[0]
    rp_rows = pitchers[pitchers['Name'] != sp_row['Name']].sample(4)

    # Format & Post
    order = sorted(final_roster, key=lambda x: x['Val'], reverse=True)
    lineup_rows = [f"{i+1} {clean_name(p['Name'])} {p['Pos']}" for i, p in enumerate(order)]
    mgr = random.choice(['Hodges', 'Johnson', 'Valentine', 'Berra', 'Collins', 'Mendoza'])

    status_body = (
        f"Game #{current_game}\nMgr: {mgr}\n\n"
        + "\n".join(lineup_rows) + 
        f"\n\nP: {clean_name(sp_row['Name'])}\n"
        f"Bullpen: " + ", ".join([clean_name(n['Name']) for _, n in rp_rows.iterrows()])
    )

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(status_body)
        with open(game_file, "w") as f: f.write(str(current_game + 1))
        print(f"✅ Success! DH is a real hitter now.")
    except Exception as e:
        print(f"❌ Bluesky Error: {e}")

if __name__ == "__main__":
    post_lineup()
