import pandas as pd
import os
import random
from atproto import Client
import re

def clean_name(name):
    return re.sub(r'[*#+?0-9]', '', str(name)).replace('HOF', '').strip()

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
        batters['PosSearch'] = batters['PosSummary'].astype(str).str.upper()
    except Exception as e:
        print(f"❌ Load Error: {e}. Scraper failed to create files.")
        return

    # Map for the entire player pool
    slots = [
        ('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), 
        ('7|O', 'LF'), ('8|O', 'CF'), ('9|O', 'RF')
    ]
    
    final_lineup = []
    used = set()

    for code, label in slots:
        mask = batters['PosSearch'].str.contains(code, na=False)
        pool = batters[mask & ~batters['Name'].isin(used)]
        
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used.add(sel['Name'])
            ops = pd.to_numeric(sel['OPS'], errors='coerce') or 0.000
            final_lineup.append({'Name': sel['Name'], 'Pos': label, 'OPS': ops})
        else:
            print(f"🚫 Critical Error: Could not find a legitimate {label}. Aborting.")
            return

    # DH - Best remaining bat
    dh = batters[~batters['Name'].isin(used)].sample(1).iloc[0]
    final_lineup.append({'Name': dh['Name'], 'Pos': 'DH', 'OPS': pd.to_numeric(dh['OPS'], errors='coerce') or 0.0})

    # PITCHERS
    sp = pitchers.sample(1).iloc[0]
    rp = pitchers[pitchers['Name'] != sp['Name']].sample(4)

    # Post
    order = sorted(final_lineup, key=lambda x: x['OPS'], reverse=True)
    body = (f"Game #{current_game}\n"
            f"Manager: {random.choice(['Gil Hodges', 'Davey Johnson', 'Bobby Valentine', 'Yogi Berra'])}\n\n" +
            "\n".join([f"{i+1}. {clean_name(p['Name'])} - {p['Pos']}" for i, p in enumerate(order)]) + 
            f"\n\nP: {clean_name(sp['Name'])}\n\nBullpen:\n" + 
            "\n".join([clean_name(n['Name']) for _, n in rp.iterrows()]) + "\n\n#MetsSky #LGM")

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(body)
        with open(game_file, "w") as f: f.write(str(current_game + 1))
        print(f"✅ Success: Game #{current_game} is live.")
    except Exception as e:
        print(f"❌ Bluesky Error: {e}")

if __name__ == "__main__":
    post_lineup()
