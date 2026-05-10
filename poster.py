import pandas as pd
import os
import random
import datetime
import pytz
from atproto import Client

def get_primary_pos(pos_str):
    for char in str(pos_str):
        if char in '23456789':
            return char
    return 'DH'

def format_name(full_name):
    parts = str(full_name).split()
    if len(parts) >= 2:
        return f"{parts[-1]}, {parts[0][0]}"
    return full_name

def post_lineup():
    # --- GAME NUMBER LOGIC ---
    game_file = "game_number.txt"
    if os.path.exists(game_file):
        with open(game_file, "r") as f:
            try:
                current_game = int(f.read().strip())
            except:
                current_game = 1
    else:
        current_game = 1

    ny_tz = pytz.timezone('America/New_York')
    ny_now = datetime.datetime.now(ny_tz)
    
    # Testing window
    if ny_now.hour not in [13, 14, 15, 16, 17, 18]:
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

    try:
        batters_df = pd.read_csv('mets_batters.csv')
        pitchers_df = pd.read_csv('mets_pitchers.csv')
        if 'Pos Summary' in batters_df.columns:
            batters_df = batters_df[batters_df['Pos Summary'] != 'P'].copy()
    except Exception as e:
        print(f"Error: {e}")
        return

    # Lineup Selection
    lineup_sample = batters_df.sample(min(9, len(batters_df))).copy()
    for col in ['OBP', 'SLG']:
        lineup_sample[col] = pd.to_numeric(lineup_sample[col], errors='coerce').fillna(0)
    lineup_sample['HITTING_VAL'] = (lineup_sample['OBP'] * 1.2) + (lineup_sample['SLG'] * 1.0)
    
    lineup_sample['PRIMARY_POS'] = lineup_sample['Pos Summary'].apply(get_primary_pos)
    lineup_sample['POS_COUNT'] = lineup_sample['Pos Summary'].str.len()
    lineup_sample = lineup_sample.sort_values(by='HITTING_VAL', ascending=False)
    
    final_lineup_text = []
    taken_positions = set()
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

    # Pitching
    used = set(lineup_sample['Name'].tolist())
    available_p = pitchers_df[~pitchers_df['Name'].isin(used)].copy()
    sp_row = available_p.sample(1).iloc[0]
    sp_name = format_name(sp_row['Name'])
    used.add(sp_row['Name'])
    rp_pool = available_p[~available_p['Name'].isin(used)].sample(min(4, len(available_p)-1))
    rp_names = [format_name(n) for n in rp_pool['Name'].tolist()]

    # Construct Post
    status_text = f"Game #{current_game}\n"
    status_text += f"Manager: {selected_manager}\n\n"
    status_text += "\n".join(final_lineup_text)
    status_text += f"\n\nP: {sp_name}\n\n"
    status_text += "Bullpen:\n"
    status_text += "\n".join(rp_names)
    status_text += "\n\n#MetsSky"

    # Post to Bluesky
    try:
        client = Client()
        handle = os.environ.get('BSKY_HANDLE')
        password = os.environ.get('BSKY_PASSWORD')
        client.login(handle, password)
        
        if len(status_text) > 300:
            status_text = status_text.replace("\n\n", "\n")
            
        client.send_post(status_text)
        print(f"Success! Posted Game #{current_game}")

        # UPDATE THE GAME NUMBER FOR NEXT TIME
        with open(game_file, "w") as f:
            f.write(str(current_game + 1))

    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    post_lineup()
