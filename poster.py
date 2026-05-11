import pandas as pd
import os
import random
from atproto import Client
import re

def clean_name(name):
    """
    Cleans B-Ref markers (*, +, digits) but keeps the correct accented 
    characters for a professional look.
    """
    # Force to string and strip B-Ref junk
    clean = re.sub(r'[*#+?0-9]', '', str(name)).replace('HOF', '').strip()
    
    # Format as 'F. Last' to save space for the 300-char limit
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
        # Load with 'utf-8-sig' to ensure accents (é, á, ñ) are read correctly
        batters = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
        pitchers = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
        
        # --- POSITION-INDEPENDENT MAPPING ---
        # We don't care what the headers are named. We use their location:
        # Index 1 = Name (usually the 2nd column)
        # Index -1 = PosSummary (The very last column)
        # Index -2 = OPS (Usually the 2nd to last column)
        
        batters = batters.rename(columns={
            batters.columns[1]: 'Name', 
            batters.columns[-1]: 'PosSearch',
            batters.columns[-2]: 'OPS'
        })
        
        pitchers = pitchers.rename(columns={
            pitchers.columns[1]: 'Name', 
            pitchers.columns[-1]: 'PosSearch'
        })

        # Ensure the position data is treated as uppercase text (string)
        batters['PosSearch'] = batters['PosSearch'].astype(str).str.upper()
        pitchers['PosSearch'] = pitchers['PosSearch'].astype(str).str.upper()
        
    except Exception as e:
        print(f"❌ Load Error: {e}")
        return

    # Filter: Pitchers must have '1' in their PosSummary.
    # Hitters must have a fielding position (2-9) in their PosSummary.
    real_pitcher_pool = pitchers[pitchers['PosSearch'].str.contains('1', na=False)]
    real_hitter_pool = batters[batters['PosSearch'].str.contains(r'[2-9]', na=False)]

    # 1. Fill the 8 fielding spots (C, 1B, 2B, 3B, SS, LF, CF, RF)
    slots = [('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), ('7|O', 'LF'), ('8|O', 'CF'), ('9|O', 'RF')]
    final_roster = []
    used_names = set()

    for code, label in slots:
        mask = real_hitter_pool['PosSearch'].str.contains(code, na=False)
        pool = real_hitter_pool[mask & ~real_hitter_pool['Name'].isin(used_names)]
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used_names.add(sel['Name'])
            # Convert OPS to number, default to 0.000 if blank
            val = pd.to_numeric(sel['OPS'], errors='coerce') or 0.0
            final_roster.append({'Name': sel['Name'], 'Pos': label, 'Val': val})

    # 2. Pick a DH (Must be a position player, not a pitcher)
    dh_pool = real_hitter_pool[~real_hitter_pool['Name'].isin(used_names)]
    if not dh_pool.empty:
        dh_sel = dh_pool.sample(1).iloc[0]
        final_roster.append({
            'Name': dh_sel['Name'], 
            'Pos': 'DH', 
            'Val': pd.to_numeric(dh_sel['OPS'], errors='coerce') or 0.0
        })

    # 3. Select Pitchers (Includes all 1-game wonders who are primary pitchers)
    sp_row = real_pitcher_pool.sample(1).iloc[0]
    rp_rows = real_pitcher_pool[real_pitcher_pool['Name'] != sp_row['Name']].sample(4)

    # 4. Sort Lineup by OPS (Highest to Lowest)
    order = sorted(final_roster, key=lambda x: x['Val'], reverse=True)
    lineup_rows = [f"{i+1} {clean_name(p['Name'])} {p['Pos']}" for i, p in enumerate(order)]
    
    # Random Manager selection
    mgr = random.choice(['Hodges', 'Johnson', 'Valentine', 'Berra', 'Collins', 'Mendoza'])

    # 5. Construct the Post
    status_body = (
        f"Game #{current_game}\nMgr: {mgr}\n\n"
        + "\n".join(lineup_rows) + 
        f"\n\nP: {clean_name(sp_row['Name'])}\n"
        f"Bullpen: " + ", ".join([clean_name(n['Name']) for _, n in rp_rows.iterrows()])
    )

    # Final character safety check
    if len(status_body) > 300:
        status_body = status_body[:300]

    # 6. Send to Bluesky
    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(status_body)
        
        # Advance the game counter for the next run
        with open(game_file, "w") as f:
            f.write(str(current_game + 1))
            
        print(f"✅ Success! Game #{current_game} is live with correct accents.")
    except Exception as e:
        print(f"❌ Bluesky Error: {e}")

if __name__ == "__main__":
    post_lineup()
