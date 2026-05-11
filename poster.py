import pandas as pd
import os
import random
from atproto import Client
import re
import unicodedata

def clean_name(name):
    # 1. Strip B-Ref markers (*, +, digits)
    clean = re.sub(r'[*#+?0-9]', '', str(name)).replace('HOF', '').strip()
    
    # 2. Normalize to strip encoding artifacts (Perez/Fernandez fix)
    clean = unicodedata.normalize('NFKD', clean).encode('ascii', 'ignore').decode('ascii')
    
    # 3. Format as 'F. Last'
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
        
        # Clean headers
        batters.columns = [re.sub(r'\W+', '', str(c)) for c in batters.columns]
        pitchers.columns = [re.sub(r'\W+', '', str(c)) for c in pitchers.columns]
        
        # Locate PosSummary columns
        b_pos_col = next((c for c in batters.columns if 'Pos' in c), batters.columns[-1])
        p_pos_col = next((c for c in pitchers.columns if 'Pos' in c), pitchers.columns[-1])
        
        batters['PosSearch'] = batters[b_pos_col].astype(str).str.upper()
        pitchers['PosSearch'] = pitchers[p_pos_col].astype(str).str.upper()
    except Exception as e:
        print(f"❌ Load Error: {e}")
        return

    # --- THE "ALL-PITCHER" FILTER ---
    
    # We define 'Real Pitchers' as anyone in the pitcher file whose PosSummary 
    # starts with '1'. This keeps the 1-game specialists but kills the position player cameos.
    real_pitcher_pool = pitchers[pitchers['PosSearch'].str.startswith('1', na=False)]

    # We define 'Real Hitters' as anyone in the batter file whose PosSummary 
    # contains any field position (2-9).
    real_hitter_pool = batters[batters['PosSearch'].str.contains(r'[2-9]', na=False)]

    # --- LINEUP SELECTION ---
    
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

    # DH: Best remaining non-pitcher
    dh_pool = real_hitter_pool[~real_hitter_pool['Name'].isin(used_names)]
    if not dh_pool.empty:
        dh_sel = dh_pool.sample(1).iloc[0]
        final_roster.append({'Name': dh_sel['Name'], 'Pos': 'DH', 'Val': pd.to_numeric(dh_sel['OPS'], errors='coerce') or 0.0})

    # Pitching: Pull from the 'Starts with 1' pool (includes 1-game Mets)
    sp_row = real_pitcher_pool.sample(1).iloc[0]
    rp_rows = real_pitcher_pool[real_pitcher_pool['Name'] != sp_row['Name']].sample(4)

    # --- FORMATTING ---
    
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

    # Post
    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(status_body)
        with open(game_file, "w") as f: f.write(str(current_game + 1))
        print(f"✅ Posted Game #{current_game} with all pitchers included.")
    except Exception as e:
        print(f"❌ Bluesky Error: {e}")

if __name__ == "__main__":
    post_lineup()
