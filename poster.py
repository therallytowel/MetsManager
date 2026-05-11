import pandas as pd
import os
import random
from atproto import Client
import re

def clean_name(name):
    """
    Strips Baseball-Reference markers like '*' (active), '+' (HOF), 
    and trailing digits/IDs to keep the post looking professional.
    """
    # Remove HOF (+), Active (*), and digits
    clean = re.sub(r'[*#+?0-9]', '', str(name)).replace('HOF', '').strip()
    # Handle the 'Last Name, First Name' or 'First Last' formats
    parts = clean.split()
    if len(parts) >= 2:
        # Returns 'Last, F.' for that classic box score feel
        return f"{parts[-1]}, {parts[0][0]}."
    return clean

def post_lineup():
    # Tracking the game number in a local text file
    game_file = "game_number.txt"
    current_game = 1
    if os.path.exists(game_file):
        with open(game_file, "r") as f:
            try:
                current_game = int(f.read().strip())
            except:
                pass

    try:
        # Load the manual CSVs. 
        # encoding='utf-8-sig' handles the hidden BOM characters B-Ref often includes.
        batters = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
        pitchers = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
        
        # Standardize column names (removes spaces, dots, and special characters)
        batters.columns = [re.sub(r'\W+', '', str(c)) for c in batters.columns]
        pitchers.columns = [re.sub(r'\W+', '', str(c)) for c in pitchers.columns]
        
        # Locate the Position column (it's usually the last one in B-Ref exports)
        pos_col = next((c for c in batters.columns if 'Pos' in c), batters.columns[-1])
        batters['PosSearch'] = batters[pos_col].astype(str).str.upper()
        
    except Exception as e:
        print(f"❌ Load Error: {e}. Ensure mets_batters.csv and mets_pitchers.csv are in the folder.")
        return

    # THE BLUEPRINT
    # 2=C, 3=1B, 4=2B, 5=3B, 6=SS. 
    # For Outfield, we look for '7' (LF), '8' (CF), '9' (RF) or the generic 'O'
    slots = [
        ('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), 
        ('7|O', 'LF'), ('8|O', 'CF'), ('9|O', 'RF')
    ]
    
    final_roster = []
    used_names = set()

    # 1. Select Position Players
    for code, label in slots:
        # Search the entire history for a player matching this position code
        mask = batters['PosSearch'].str.contains(code, na=False)
        pool = batters[mask & ~batters['Name'].isin(used_names)]
        
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used_names.add(sel['Name'])
            # Use OPS for batting order logic, default to .000 if empty
            ops_val = pd.to_numeric(sel['OPS'], errors='coerce') or 0.000
            final_roster.append({'Name': sel['Name'], 'Pos': label, 'Val': ops_val})
        else:
            print(f"🚫 Critical: No {label} found in the CSV. Post aborted.")
            return

    # 2. Select DH (Best remaining bat)
    dh_pool = batters[~batters['Name'].isin(used_names)]
    dh_sel = dh_pool.sample(1).iloc[0]
    final_roster.append({
        'Name': dh_sel['Name'], 
        'Pos': 'DH', 
        'Val': pd.to_numeric(dh_sel['OPS'], errors='coerce') or 0.000
    })

    # 3. Select Pitchers (1 SP, 4 RP)
    sp_row = pitchers.sample(1).iloc[0]
    rp_rows = pitchers[pitchers['Name'] != sp_row['Name']].sample(4)

    # 4. Construct the Post
    # Sort the 9 batters by OPS (highest to lowest)
    order = sorted(final_roster, key=lambda x: x['Val'], reverse=True)
    lineup_rows = [f"{i+1}. {clean_name(p['Name'])} - {p['Pos']}" for i, p in enumerate(order)]
    
    mgr = random.choice(['Gil Hodges', 'Davey Johnson', 'Bobby Valentine', 'Yogi Berra', 'Terry Collins'])

    status_body = (
        f"Game #{current_game} (Franchise History)\n"
        f"Manager: {mgr}\n\n"
        + "\n".join(lineup_rows) + 
        f"\n\nP: {clean_name(sp_row['Name'])}\n\n"
        f"Bullpen:\n" + "\n".join([clean_name(n['Name']) for _, n in rp_rows.iterrows()]) + 
        "\n\n#MetsSky #LGM"
    )

    # 5. Send to BlueSky
    try:
        client = Client()
        # These come from your GitHub Secrets
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(status_body)
        
        # Increment the game number for tomorrow
        with open(game_file, "w") as f:
            f.write(str(current_game + 1))
            
        print(f"✅ Posted Game #{current_game} successfully!")
    except Exception as e:
        print(f"❌ Bluesky Posting Error: {e}")

if __name__ == "__main__":
    post_lineup()
