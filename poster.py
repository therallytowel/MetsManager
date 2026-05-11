import pandas as pd
import os
import random
from atproto import Client
import re

def clean_name(name):
    # Strip HOF tags (+), active tags (*), and digits
    return re.sub(r'[*#+?0-9]', '', str(name)).replace('HOF', '').strip()

def post_lineup():
    game_file = "game_number.txt"
    current_game = 1
    if os.path.exists(game_file):
        with open(game_file, "r") as f:
            try: current_game = int(f.read().strip())
            except: pass

    try:
        # Read the newly created full-franchise CSVs
        batters = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
        pitchers = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
        
        # Standardize position column for searching
        batters['PosClean'] = batters['PosSummary'].astype(str).str.upper()
    except Exception as e:
        print(f"❌ Load Error: {e}")
        return

    # Positions: 2=C, 3=1B, 4=2B, 5=3B, 6=SS, 7/O=LF, 8/O=CF, 9/O=RF
    slots = [
        ('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), 
        ('7|O', 'LF'), ('8|O', 'CF'), ('9|O', 'RF')
    ]
    
    final_roster = []
    used = set()

    for code, label in slots:
        # Search the entire history for this position
        mask = batters['PosClean'].str.contains(code, na=False)
        pool = batters[mask & ~batters['Name'].isin(used)]
        
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used.add(sel['Name'])
            ops = pd.to_numeric(sel['OPS'], errors='coerce') or 0.000
            final_roster.append({'Name': sel['Name'], 'Pos': label, 'Val': ops})
        else:
            print(f"🚫 Critical: No {label} found in the franchise pool.")
            return

    # DH: Randomly pick one remaining position player
    dh = batters[~batters['Name'].isin(used)].sample(1).iloc[0]
    final_roster.append({'Name': dh['Name'], 'Pos': 'DH', 'Val': pd.to_numeric(dh['OPS'], errors='coerce') or 0.000})

    # PITCHERS
    sp = pitchers.sample(1).iloc[0]
    rp = pitchers[pitchers['Name'] != sp['Name']].sample(4)

    # Lineup construction
    lineup = sorted(final_roster, key=lambda x: x['Val'], reverse=True)
    txt = [f"{i+1}. {clean_name(p['Name'])} - {p['Pos']}" for i, p in enumerate(lineup)]
    
    mgr = random.choice(['Gil Hodges', 'Davey Johnson', 'Bobby Valentine', 'Casey Stengel', 'Yogi Berra'])
    body = (f"Game #{current_game}\nManager: {mgr}\n\n" + "\n".join(txt) + 
            f"\n\nP: {clean_name(sp['Name'])}\n\nBullpen:\n" + 
            "\n".join([clean_name(n['Name']) for _, n in rp.iterrows()]) + "\n\n#MetsSky #LGM")

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(body)
        with open(game_file, "w") as f: f.write(str(current_game + 1))
        print(f"✅ Success: Game #{current_game} is live using the full history!")
    except Exception as e:
        print(f"❌ Bluesky Error: {e}")

if __name__ == "__main__":
    post_lineup()
