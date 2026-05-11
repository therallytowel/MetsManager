import pandas as pd
import os
import random
from atproto import Client
import re

def clean_name(name):
    # Strip B-Ref junk: HOF (+), Active (*), and ID digits
    clean = re.sub(r'[*#+?0-9]', '', str(name)).replace('HOF', '').strip()
    parts = clean.split()
    if len(parts) >= 2:
        # 'F. Last' format is the most space-efficient
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
        batters = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
        pitchers = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
        batters.columns = [re.sub(r'\W+', '', str(c)) for c in batters.columns]
        pitchers.columns = [re.sub(r'\W+', '', str(c)) for c in pitchers.columns]
        pos_col = next((c for c in batters.columns if 'Pos' in c), batters.columns[-1])
        batters['PosSearch'] = batters[pos_col].astype(str).str.upper()
    except Exception as e:
        print(f"❌ Load Error: {e}")
        return

    slots = [('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), ('7|O', 'LF'), ('8|O', 'CF'), ('9|O', 'RF')]
    final_roster = []
    used = set()

    for code, label in slots:
        mask = batters['PosSearch'].str.contains(code, na=False)
        pool = batters[mask & ~batters['Name'].isin(used)]
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used.add(sel['Name'])
            ops = pd.to_numeric(sel['OPS'], errors='coerce') or 0.0
            final_roster.append({'Name': sel['Name'], 'Pos': label, 'Val': ops})
        else: return

    dh = batters[~batters['Name'].isin(used)].sample(1).iloc[0]
    final_roster.append({'Name': dh['Name'], 'Pos': 'DH', 'Val': pd.to_numeric(dh['OPS'], errors='coerce') or 0.0})

    sp = pitchers.sample(1).iloc[0]
    rp = pitchers[pitchers['Name'] != sp['Name']].sample(4)

    # SORT & FORMAT
    order = sorted(final_roster, key=lambda x: x['Val'], reverse=True)
    rows = [f"{i+1} {clean_name(p['Name'])} {p['Pos']}" for i, p in enumerate(order)]
    
    mgr = random.choice(['Hodges', 'Johnson', 'Valentine', 'Berra', 'Collins'])

    # Building the post without hashtags
    status_body = (
        f"Game #{current_game}\nMgr: {mgr}\n\n"
        + "\n".join(rows) + 
        f"\n\nP: {clean_name(sp['Name'])}\n"
        f"Bullpen: " + ", ".join([clean_name(n['Name']) for _, n in rp.iterrows()])
    )

    # Final safety check for Bluesky's 300-char limit
    if len(status_body) > 300:
        status_body = status_body[:300]

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(status_body)
        with open(game_file, "w") as f: f.write(str(current_game + 1))
        print(f"✅ Success! Game #{current_game} posted without hashtags.")
    except Exception as e:
        print(f"❌ Bluesky Error: {e}")

if __name__ == "__main__":
    post_lineup()
