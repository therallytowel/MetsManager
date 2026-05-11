import pandas as pd
import os
import random
from atproto import Client
import re
import unicodedata

def clean_name(name):
    clean = re.sub(r'[*#+?0-9]', '', str(name)).replace('HOF', '').strip()
    clean = unicodedata.normalize('NFKD', clean).encode('ascii', 'ignore').decode('ascii')
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
        
        # Clean headers: remove spaces, dots, and non-word characters
        batters.columns = [re.sub(r'\W+', '', str(c)) for c in batters.columns]
        pitchers.columns = [re.sub(r'\W+', '', str(c)) for c in pitchers.columns]
        
        # FIND THE POSITION COLUMN (The logic that was failing)
        # We look for the first column header that contains "Pos"
        b_pos_col = next((c for c in batters.columns if 'Pos' in c.upper()), None)
        p_pos_col = next((c for c in pitchers.columns if 'Pos' in c.upper()), None)

        if not b_pos_col or not p_pos_col:
            # Fallback if B-Ref changed the header name
            b_pos_col, p_pos_col = batters.columns[-1], pitchers.columns[-1]

        # Force the column to be treated as string before using .str methods
        batters['PosSearch'] = batters[b_pos_col].astype(str).str.upper()
        pitchers['PosSearch'] = pitchers[p_pos_col].astype(str).str.upper()
        
    except Exception as e:
        print(f"❌ Load Error: {e}")
        return

    # Filter: Pitchers must start with '1', Hitters must contain 2-9
    real_pitcher_pool = pitchers[pitchers['PosSearch'].str.startswith('1', na=False)]
    real_hitter_pool = batters[batters['PosSearch'].str.contains(r'[2-9]', na=False)]

    slots = [('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), ('7|O', 'LF'), ('8|O', 'CF'), ('9|O', 'RF')]
    final_roster = []
    used_names = set()

    for code, label in slots:
        mask = real_hitter_pool['PosSearch'].str.contains(code, na=False)
        pool = real_hitter_pool[mask & ~real_hitter_pool['Name'].isin(used_names)]
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used_names.add(sel['Name'])
            val = pd.to_numeric(sel['OPS'], errors='coerce') or 0.0
            final_roster.append({'Name': sel['Name'], 'Pos': label, 'Val': val})

    dh_pool = real_hitter_pool[~real_hitter_pool['Name'].isin(used_names)]
    if not dh_pool.empty:
        dh_sel = dh_pool.sample(1).iloc[0]
        final_roster.append({'Name': dh_sel['Name'], 'Pos': 'DH', 'Val': pd.to_numeric(dh_sel['OPS'], errors='coerce') or 0.0})

    sp_row = real_pitcher_pool.sample(1).iloc[0]
    rp_rows = real_pitcher_pool[real_pitcher_pool['Name'] != sp_row['Name']].sample(4)

    order = sorted(final_roster, key=lambda x: x['Val'], reverse=True)
    lineup_rows = [f"{i+1} {clean_name(p['Name'])} {p['Pos']}" for i, p in enumerate(order)]
    mgr = random.choice(['Hodges', 'Johnson', 'Valentine', 'Berra', 'Collins', 'Mendoza'])

    status_body = (
        f"Game #{current_game}\nMgr: {mgr}\n\n"
        + "\n".join(lineup_rows) + 
        f"\n\nP: {clean_name(sp_row['Name'])}\n"
        f"Bullpen: " + ", ".join([clean_name(n['Name']) for _, n in rp_rows.iterrows()])
    )

    if len(status_body) > 300:
        status_body = status_body[:300]

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(status_body)
        with open(game_file, "w") as f: f.write(str(current_game + 1))
        print(f"✅ Success! Game #{current_game} is live.")
    except Exception as e:
        print(f"❌ Bluesky Error: {e}")

if __name__ == "__main__":
    post_lineup()
