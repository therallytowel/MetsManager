import pandas as pd
import os
import random
import datetime
import pytz
from atproto import Client

def get_primary_pos(pos_str):
    """Searches for defensive positions 2-9 in the position summary string."""
    pos_str = str(pos_str)
    for char in pos_str:
        if char in '23456789':
            return char
    return 'DH'

def format_name(full_name):
    """Converts 'Keith Hernandez' to 'Hernandez, K'."""
    clean_name = str(full_name).replace('Jr.', '').replace('Sr.', '').strip()
    parts = clean_name.split()
    if len(parts) >= 2:
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
    
    if ny_now.hour not in range(11, 23): # 11am to 10pm ET
        print(f"Skipping... Hour is {ny_now.hour}.")
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

    # --- 3. DATA LOADING & FILTERING ---
    try:
        batters_df = pd.read_csv('mets_batters.csv', encoding='utf-8')
        pitchers_df = pd.read_csv('mets_pitchers.csv', encoding='utf-8')
        
        if 'Pos Summary' not in batters_df.columns:
            batters_df.rename(columns={'Pos': 'Pos Summary'}, inplace=True, errors='ignore')
            
        # --- THE DEFENSIVE SPECIALIST FILTER ---
        # 1. Must contain a digit 2-9 (Catcher through RF)
        batters_df = batters_df[batters_df['Pos Summary'].astype(str).str.contains('[2-9]', regex=True, na=False)].copy()
        
        # 2. Must NOT contain 'P' (Standard Pitcher designation)
        batters_df = batters_df[~batters_df['Pos Summary'].astype(str).str.contains('P', na=False)].copy()
            
    except Exception as e:
        print(f"Error: {e}")
        return

    # --- 4. LINEUP SELECTION ---
    if len(batters_df) < 9:
        print("Error: Roster too small. Filter might be too strict.")
        return

    lineup_sample = batters_df.sample(n=9).copy()
    
    for col in ['OBP', 'SLG']:
        lineup_sample[col] = pd.to_numeric(lineup_sample[col], errors='coerce').fillna(0)
    
    lineup_sample['HITTING_VAL'] = (lineup_sample['OBP'] * 1.2) + (lineup_sample['SLG'] * 1.0)
    lineup_sample['PRIMARY_POS_CODE'] = lineup_sample['Pos Summary'].apply(get_primary_pos)
    lineup_sample['POS_COUNT'] = lineup_sample['Pos Summary'].astype(str).str.len()

    lineup_sample = lineup_sample.sort_values(by='HITTING_VAL', ascending=False)
    
    final_lineup_text = []
    taken_positions = set()
    dh_idx = lineup_sample['POS_COUNT'].idxmax()
    
    for i, (idx, player) in enumerate(lineup_sample.iterrows(), 1):
        pos_code = str(player.get('PRIMARY_POS_CODE', 'DH'))
        p_name = format_name(player['Name'])
        mapping = {'2':'C', '3':'1B', '4':'2B', '5':'3B', '6':'SS', '7':'LF', '8':'CF', '9':'RF'}
        
        if idx == dh_idx or pos_code in taken_positions or pos_code == 'DH':
            actual_pos = 'DH'
        else:
            actual_pos = mapping.get(pos_code, 'DH')
            taken_positions.add(pos_code)
        
        final_lineup_text.append(f"{i}. {p_name} - {actual_pos}")

    # --- 5. PITCHING ---
    used_names = set(lineup_sample['Name'].tolist())
    available_p = pitchers_df[~pitchers_df['Name'].isin(used_names)].copy()
    sp_row = available_p.sample(1).iloc[0]
    sp_name = format_name(sp_row['Name'])
    
    used_names.add(sp_row['Name'])
    rp_pool = available_p[~available_p['Name'].isin(used_names)].sample(min(4, len(available_p)-1))
    rp_names = [format_name(n) for n in rp_pool['Name'].tolist()]

    # --- 6. POST ---
    status_text = f"Game #{current_game}\nManager: {selected_manager}\n\n"
    status_text += "\n".join(final_lineup_text)
    status_text += f"\n\nP: {sp_name}\n\nBullpen:\n"
    status_text += "\n".join(rp_names)
    status_text += "\n\n#MetsSky"

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(status_text)
        print(f"Success! Posted Game #{current_game}")

        with open(game_file, "w", encoding='utf-8') as f:
            f.write(str(current_game + 1))
    except Exception as e:
        print(f"Post failed: {e}")

if __name__ == "__main__":
    post_lineup()
