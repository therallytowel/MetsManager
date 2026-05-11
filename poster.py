import pandas as pd
import os
import random
from atproto import Client
import re

def clean_name(name):
    # Removes B-Ref markers like * (active), # (switch), + (HOF)
    return re.sub(r'[*#+?0-9]', '', str(name)).strip()

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
        
        # Clean the position strings for searching
        batters['PosClean'] = batters['PosSummary'].astype(str).str.upper()
    except Exception as e:
        print(f"❌ Load Error: {e}")
        return

    # MAPPING: 2=C, 3=1B, 4=2B, 5=3B, 6=SS, 7=LF, 8=CF, 9=RF
    # Also including 'O' for general Outfielders
    slots = [
        ('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), 
        ('7|O', 'LF'), ('8|O', 'CF'), ('9|O', 'RF')
    ]
    
    final_lineup = []
    used_players = set()

    for code, label in slots:
        # Strict filter: Must contain the specific number OR the 'O' wildcard
        mask = batters['PosClean'].str.contains(code, na=False)
        pool = batters[mask & ~batters['Name'].isin(used_players)]
        
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used_players.add(sel['Name'])
            # Pull OPS for sorting, default to 0 if missing
            ops = pd.to_numeric(sel['OPS'], errors='coerce') or 0.000
            final_lineup.append({'Name': sel['Name'], 'Pos': label, 'OPS': ops})
        else:
            print(f"🚫 Critical Error: No legitimate {label} in the 1300-player pool.")
            return

    # DH: Best remaining player in the pool
    dh_pool = batters[~batters['Name'].isin(used_players)]
    dh = dh_pool.sample(1).iloc[0]
    final_lineup.append({'Name': dh['Name'], 'Pos': 'DH', 'OPS': pd.to_numeric(dh['OPS'], errors='coerce') or 0.0})

    # PITCHERS: 1 Starter, 4 Relievers
    sp = pitchers.sample(1).iloc[0]
    rp = pitchers[pitchers['Name'] != sp['Name']].sample(4)

    # Lineup construction: Sort by OPS
    batting_order = sorted(final_lineup, key=lambda x: x['OPS'], reverse=True)
    lineup_rows = [f"{i+1}. {clean_name(p['Name'])} - {p['Pos']}" for i, p in enumerate(batting_order)]
    
    body = (
        f"Game #{current_game}\n"
        f"Manager: {random.choice(['Gil Hodges', 'Davey Johnson', 'Bobby Valentine', 'Yogi Berra'])}\n\n"
        + "\n".join(lineup_rows) + 
        f"\n\nP: {clean_name(sp['Name'])}\n\n"
        f"Bullpen:\n" + "\n".join([clean_name(n['Name']) for _, n in rp.iterrows()]) + 
        "\n\n#MetsSky #LGM"
    )

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(body)
        with open(game_file, "w") as f: f.write(str(current_game + 1))
        print(f"✅ Posted Game #{current_game} using the full franchise history.")
    except Exception as e:
        print(f"❌ Posting Error: {e}")

if __name__ == "__main__":
    post_lineup()
