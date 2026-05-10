import pandas as pd
import os
import random
import datetime
import pytz
from atproto import Client

def get_primary_pos(pos_str):
    """Searches for defensive positions 2-9 in the position summary string."""
    for char in str(pos_str):
        if char in '23456789':
            return char
    return 'DH'

def format_name(full_name):
    """Converts 'Keith Hernandez' to 'Hernandez, K'."""
    parts = str(full_name).split()
    if len(parts) >= 2:
        return f"{parts[-1]}, {parts[0][0]}"
    return full_name

def post_lineup():
    # --- 1. GAME NUMBER LOGIC ---
    game_file = "game_number.txt"
    if os.path.exists(game_file):
        with open(game_file, "r") as f:
            try:
                current_game = int(f.read().strip())
            except:
                current_game = 1
    else:
        current_game = 1

    # --- 2. TIME & MANAGER LOGIC ---
    ny_tz = pytz.timezone('America/New_York')
    ny_now = datetime.datetime.now(ny_tz)
    
    # Debugging/Running window (1pm - 7pm ET)
    if ny_now.hour not in [13, 14, 15, 16, 17, 18, 19]:
        print(f"Skipping... Hour is {ny_now.hour}. Manager is off-duty.")
        return 

    managers = [
        "George Bamberger", "Yogi Berra", "Mickey Callaway", "Terry Collins",
        "Mike Cubbage", "Joe Frazier", "Dallas Green", "Bud Harrelson",
        "Gil Hodges", "Frank Howard", "Art Howe", "Davey Johnson",
        "Jerry Manuel", "Roy McMillan", "Carlos Mendoza", "Salty Parker",
        "Willie Randolph", "Luis Rojas", "Buck Showalter", "Casey Stengel",
        "Jeff Torborg", "Joe Torre", "Bobby Valentine", "Wes Westrum"
    ]
    selected_manager = random.choice(managers)

    # --- 3. DATA LOADING & CLEANING ---
    try:
        batters_df = pd.read_csv('mets_batters.csv')
        pitchers_df = pd.read_csv('mets_pitchers.csv')
        
        # Unify position column naming
        if 'Pos Summary' not in batters_df.columns and 'Pos' in batters_df.columns:
            batters_df.rename(columns={'Pos': 'Pos Summary'}, inplace=True)
            
        # Filter out pure pitchers from the hitting pool
        if 'Pos Summary' in batters_df.columns:
            batters_df = batters_df[batters_df['Pos Summary'] != 'P'].copy()
            
    except Exception as e:
        print(f"Error loading CSV data: {e}")
        return

    # --- 4. LINEUP SELECTION (STAT-BASED) ---
    lineup_sample = batters_df.sample(min(9, len(batters_df))).copy()
    
    # Ensure numeric stats for sorting
    for col in ['OBP', 'SLG']:
        lineup_sample[col] = pd.to_numeric(lineup_sample[col], errors='coerce').fillna(0)
    
    # Simple algorithm: OBP is king, SLG is queen
    lineup_sample['HITTING_VAL'] = (lineup_sample['OBP'] * 1.2) + (lineup_sample['SLG'] * 1.0)
    
    # Handle Position assignments
    if 'Pos Summary' in lineup_sample.columns:
        lineup_sample['PRIMARY_POS'] = lineup_sample['Pos Summary'].apply(get_primary_pos)
        lineup_sample['POS_COUNT'] = lineup_sample['Pos Summary'].astype(str).str.len()
    else:
        lineup_sample['PRIMARY_POS'] = 'DH'
        lineup_sample['POS_COUNT'] = 1

    # Sort by hitting value for the batting order
    lineup_sample = lineup_sample.sort_values(by='HITTING_VAL', ascending=False)
    
    final_lineup_text = []
    taken_positions = set()
    # Designate DH candidate based on most defensive flexibility (longest pos string)
    dh_idx = lineup_sample['POS_COUNT'].idxmax()
    
    for i, (idx, player) in enumerate(lineup_sample.iterrows(), 1):
        pos_code = str(player['PRIMARY_POS'])
        p_name = format_name(player['Name'])
        
        if idx == dh_idx or pos_code in taken_positions or pos_code == 'DH':
            actual_pos = 'DH'
        else:
            mapping = {'2':'C', '3':'1B', '4':'2B', '5':'3B', '6':'SS', '7':'LF', '8':'CF', '9':'RF'}
            actual_pos = mapping.get(pos_code, 'DH')
            taken_positions.add(pos_code)
        
        final_lineup_text.append(f"{i}. {p_name} - {actual_pos}")

    # --- 5. PITCHING SELECTION ---
    used_names = set(lineup_sample['Name'].tolist())
    available_p = pitchers_df[~pitchers_df['Name'].isin(used_names)].copy()
    
    sp_row = available_p.sample(1).iloc[0]
    sp_name = format_name(sp_row['Name'])
    
    used_names.add(sp_row['Name'])
    rp_pool = available_p[~available_p['Name'].isin(used_names)].sample(min(4, len(available_p)-1))
    rp_names = [format_name(n) for n in rp_pool['Name'].tolist()]

    # --- 6. CONSTRUCT POST ---
    status_text = f"Game #{current_game}\n"
    status_text += f"Manager: {selected_manager}\n\n"
    status_text += "\n".join(final_lineup_text)
    status_text += f"\n\nP: {sp_name}\n\n"
    status_text += "Bullpen:\n"
    status_text += "\n".join(rp_names)
    status_text += "\n\n#MetsSky"

    # --- 7. POST TO BLUESKY ---
    try:
        client = Client()
        handle = os.environ.get('BSKY_HANDLE')
        password = os.environ.get('BSKY_PASSWORD')
        
        if not handle or not password:
            print("FAILED: Secrets missing.")
            return

        client.login(handle, password)
        
        # Character limit safety trim (300 char max)
        if len(status_text) > 300:
            status_text = status_text.replace("\n\n", "\n").strip()

        client.send_post(status_text)
        print(f"Success! Game #{current_game} posted ({len(status_text)} chars).")

        # Update the game number file for the next run
        with open(game_file, "w") as f:
            f.write(str(current_game + 1))

    except Exception as e:
        print(f"FAILED TO POST: {e}")

if __name__ == "__main__":
    post_lineup()
