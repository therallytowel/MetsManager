import pandas as pd
import os
import random
import datetime
import pytz
from atproto import Client

def get_primary_pos(pos_str):
    """Searches for defensive positions 2-9 in the position summary string."""
    # Convert to string and handle potential NaNs
    pos_str = str(pos_str)
    for char in pos_str:
        if char in '23456789':
            return char
    return 'DH'

def format_name(full_name):
    """Converts 'Keith Hernandez' to 'Hernandez, K'."""
    # Remove common suffixes and clean up whitespace
    clean_name = str(full_name).replace('Jr.', '').replace('Sr.', '').strip()
    parts = clean_name.split()
    if len(parts) >= 2:
        # Returns 'Surname, FirstInitial'
        return f"{parts[-1]}, {parts[0][0]}"
    return full_name

def post_lineup():
    # --- 1. GAME NUMBER LOGIC ---
    game_file = "game_number.txt"
    if os.path.exists(game_file):
        with open(game_file, "r", encoding='utf-8') as f:
            try:
                current_game = int(f.read().strip())
            except:
                current_game = 1
    else:
        current_game = 1

    # --- 2. TIME & MANAGER LOGIC ---
    ny_tz = pytz.timezone('America/New_York')
    ny_now = datetime.datetime.now(ny_tz)
    
    # Execution window (1pm - 7pm ET)
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
        # Load with UTF-8 to handle accented names like Buttó
        batters_df = pd.read_csv('mets_batters.csv', encoding='utf-8')
        pitchers_df = pd.read_csv('mets_pitchers.csv', encoding='utf-8')
        
        # Standardize position column name
        if 'Pos Summary' not in batters_df.columns and 'Pos' in batters_df.columns:
            batters_df.rename(columns={'Pos': 'Pos Summary'}, inplace=True)
            
        # THE ULTIMATE PITCHER FILTER
        # Removes anyone who has 'P' in their position summary (e.g., 'P', 'P/H', '1P')
        if 'Pos Summary' in batters_df.columns:
            # Drop players with 'P' in their position list
            batters_df = batters_df[~batters_df['Pos Summary'].astype(str).str.contains('P', na=False)].copy()
            # Ensure the row actually has a position listed
            batters_df = batters_df.dropna(subset=['Pos Summary'])
            
    except Exception as e:
        print(f"Error loading CSV data: {e}")
        return

    # --- 4. LINEUP SELECTION (STAT-BASED) ---
    if len(batters_df) < 9:
        print("Not enough batters found after filtering. Checking scraper...")
        return

    # Draw 9 random position players
    lineup_sample = batters_df.sample(n=9).copy()
    
    # Clean up hitting stats for sorting
    for col in ['OBP', 'SLG']:
        lineup_sample[col] = pd.to_numeric(lineup_sample[col], errors='coerce').fillna(0)
    
    # Weight OBP slightly higher for the manager's preference
    lineup_sample['HITTING_VAL'] = (lineup_sample['OBP'] * 1.2) + (lineup_sample['SLG'] * 1.0)
    
    # Assign defensive codes
    lineup_sample['PRIMARY_POS_CODE'] = lineup_sample['Pos Summary'].apply(get_primary_pos)
    lineup_sample['POS_COUNT'] = lineup_sample['Pos Summary'].astype(str).str.len()

    # Sort by hitting value to establish batting order 1-9
    lineup_sample = lineup_sample.sort_values(by='HITTING_VAL', ascending=False)
    
    final_lineup_text = []
    taken_positions = set()
    
    # Identify the DH candidate (the player with the most positions listed takes the hit if their spot is full)
    dh_idx = lineup_sample['POS_COUNT'].idxmax()
    
    for i, (idx, player) in enumerate(lineup_sample.iterrows(), 1):
        pos_code = str(player['PRIMARY_POS_CODE'])
        p_name = format_name(player['Name'])
        
        # Mapping numerical codes to baseball shorthand
        mapping = {'2':'C', '3':'1B', '4':'2B', '5':'3B', '6':'SS', '7':'LF', '8':'CF', '9':'RF'}
        
        # Check if the player is designated DH or if their position is already occupied
        if idx == dh_idx or pos_code in taken_positions or pos_code == 'DH':
            actual_pos = 'DH'
        else:
            actual_pos = mapping.get(pos_code, 'DH')
            taken_positions.add(pos_code)
        
        final_lineup_text.append(f"{i}. {p_name} - {actual_pos}")

    # --- 5. PITCHING SELECTION ---
    used_names = set(lineup_sample['Name'].tolist())
    available_p = pitchers_df[~pitchers_df['Name'].isin(used_names)].copy()
    
    # Pick a Starter
    sp_row = available_p.sample(1).iloc[0]
    sp_name = format_name(sp_row['Name'])
    
    # Pick 4 unique Relievers
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
        
        # Character limit safety (tighten spacing if over 300)
        if len(status_text) > 300:
            status_text = status_text.replace("\n\n", "\n").strip()

        client.send_post(status_text)
        print(f"Success! Game #{current_game} posted ({len(status_text)} chars).")

        # Increment game counter for the next run
        with open(game_file, "w", encoding='utf-8') as f:
            f.write(str(current_game + 1))

    except Exception as e:
        print(f"FAILED TO POST: {e}")

if __name__ == "__main__":
    post_lineup()
