import pandas as pd
import os
import random
from atproto import Client
import re

def format_name(full_name):
    """Returns 'Last Name, F.' and removes B-Ref junk."""
    clean = re.sub(r'[*#+?0-9]', '', str(full_name)).replace('HOF', '').strip()
    parts = clean.split()
    return f"{parts[-1]}, {parts[0][0]}" if len(parts) >= 2 else clean

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
        
        # FIND POSITION COLUMN
        pos_col = 'PosSummary' if 'PosSummary' in batters.columns else batters.columns[-1]
        
        # NEW: Clean the position column of all special characters (*, /, etc)
        # This turns "*7/89" into "789" and "*OF" into "OF"
        batters['PosClean'] = batters[pos_col].astype(str).str.replace(r'[^a-zA-Z0-9]', '', regex=True)
        
    except Exception as e:
        print(f"❌ Data Error: {e}")
        return

    # 2=C, 3=1B, 4=2B, 5=3B, 6=SS, 7=LF, 8=CF, 9=RF
    field_needs = [('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), ('7', 'LF'), ('8', 'CF'), ('9', 'RF')]
    final_roster = []
    used = set()

    for code, label in field_needs:
        # Search for the specific number (7) OR the letters "OF"
        if code in ['7', '8', '9']:
            mask = (batters['PosClean'].str.contains(code, na=False)) | \
                   (batters['PosClean'].str.contains('OF', na=False))
        else:
            mask = batters['PosClean'].str.contains(code, na=False)
            
        pool = batters[mask & ~batters['Name'].isin(used)]

        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used.add(sel['Name'])
            ops = pd.to_numeric(sel['OPS'], errors='coerce') or 0.000
            final_roster.append({'Name': sel['Name'], 'Pos': label, 'Val': ops})
        else:
            print(f"🚫 Could not find a {label}. Data in PosClean for all players: {batters['PosClean'].unique()[:10]}")
            return

    # DH, SP, RP
    dh = batters[~batters['Name'].isin(used)].sample(1).iloc[0]
    final_roster.append({'Name': dh['Name'], 'Pos': 'DH', 'Val': pd.to_numeric(dh['OPS'], errors='coerce') or 0.0})
    
    sp = pitchers.sample(1).iloc[0]
    rp = pitchers[pitchers['Name'] != sp['Name']].sample(4)

    # Post
    lineup = sorted(final_roster, key=lambda x: x['Val'], reverse=True)
    txt = [f"{i+1}. {format_name(p['Name'])} - {p['Pos']}" for i, p in enumerate(lineup)]
    
    mgr = random.choice(['Gil Hodges', 'Davey Johnson', 'Bobby Valentine', 'Casey Stengel', 'Yogi Berra'])
    body = (f"Game #{current_game}\nManager: {mgr}\n\n" + "\n".join(txt) + 
            f"\n\nP: {format_name(sp['Name'])}\n\nBullpen:\n" + 
            "\n".join([format_name(n['Name']) for _, n in rp.iterrows()]) + "\n\n#MetsSky #LGM")

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(body)
        with open(game_file, "w") as f: f.write(str(current_game + 1))
        print(f"✅ Success: Game #{current_game} is live!")
    except Exception as e:
        print(f"❌ Bluesky Error: {e}")

if __name__ == "__main__":
    post_lineup()
