import pandas as pd
import os
import random
from atproto import Client
import re

def clean_name(name):
    """
    Cleans names from Baseball-Reference markers and formats them 
    as 'F. Last' to save space for the 300-character limit.
    """
    # Remove HOF (+), Active (*), and ID digits/junk
    clean = re.sub(r'[*#+?0-9]', '', str(name)).replace('HOF', '').strip()
    parts = clean.split()
    if len(parts) >= 2:
        return f"{parts[0][0]}. {parts[-1]}"
    return clean

def post_lineup():
    # Game counter tracking
    game_file = "game_number.txt"
    current_game = 1
    if os.path.exists(game_file):
        with open(game_file, "r") as f:
            try:
                current_game = int(f.read().strip())
            except:
                pass

    try:
        # Using 'latin1' encoding to fix accented characters (e.g., Hernández)
        batters = pd.read_csv('mets_batters.csv', encoding='latin1')
        pitchers = pd.read_csv('mets_pitchers.csv', encoding='latin1')
        
        # Standardize headers to remove dots/spaces
        batters.columns = [re.sub(r'\W+', '', str(c)) for c in batters.columns]
        pitchers.columns = [re.sub(r'\W+', '', str(c)) for c in pitchers.columns]
        
        # Identify the position column
        pos_col = next((c for c in batters.columns if 'Pos' in c), batters.columns[-1])
        batters['PosSearch'] = batters[pos_col].astype(str).str.upper()
    except Exception as e:
        print(f"❌ Load Error: {e}. Check your CSV files.")
        return

    # Position Blueprint (2=C, 3=1B, 4=2B, 5=3B, 6=SS, 7/8/9/O=OF)
    slots = [
        ('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), 
        ('7|O', 'LF'), ('8|O', 'CF'), ('9|O', 'RF')
    ]
    
    final_roster = []
    used_names = set()

    for code, label in slots:
        mask = batters['PosSearch'].str.contains(code, na=False)
        pool = batters[mask & ~batters['Name'].isin(used_names)]
        
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used_names.add(sel['Name'])
            # Pull OPS for sorting the batting order
            val = pd.to_numeric(sel['OPS'], errors='coerce') or 0.000
            final_roster.append({'Name': sel['Name'], 'Pos': label, 'Val': val})
        else:
            print(f"🚫 Error: Could not find a player for {label}.")
            return

    # Select DH from remaining pool
    dh_pool = batters[~batters['Name'].isin(used_names)]
    dh_sel = dh_pool.sample(1).iloc[0]
    final_roster.append({'Name': dh_sel['Name'], 'Pos': 'DH', 'Val': pd.to_numeric(dh_sel['OPS'], errors='coerce') or 0.000})

    # Select Pitchers (1 SP, 4 RP)
    sp_row = pitchers.sample(1).iloc[0]
    rp_rows = pitchers[pitchers['Name'] != sp_row['Name']].sample(4)

    # Sort batters by OPS (High to Low)
    order = sorted(final_roster, key=lambda x: x['Val'], reverse=True)
    lineup_rows = [f"{i+1} {clean_name(p['Name'])} {p['Pos']}" for i, p in enumerate(order)]
    
    # Random Manager pool
    mgr = random.choice(['Hodges', 'Johnson', 'Valentine', 'Berra', 'Collins', 'Mendoza'])

    # Format the status body
    status_body = (
        f"Game #{current_game}\nMgr: {mgr}\n\n"
        + "\n".join(lineup_rows) + 
        f"\n\nP: {clean_name(sp_row['Name'])}\n"
        f"Bullpen: " + ", ".join([clean_name(n['Name']) for _, n in rp_rows.iterrows()])
    )

    # Final character safety check for Bluesky
    if len(status_body) > 300:
        print(f"⚠️ Warning: Post is {len(status_body)} chars. Truncating.")
        status_body = status_body[:300]

    # Post to Bluesky
    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(status_body)
        
        # Save updated game number
        with open(game_file, "w") as f:
            f.write(str(current_game + 1))
            
        print(f"✅ Posted Game #{current_game} successfully!")
    except Exception as e:
        print(f"❌ Bluesky Posting Error: {e}")

if __name__ == "__main__":
    post_lineup()
