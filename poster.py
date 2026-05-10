import pandas as pd
import os
import random
import datetime
import pytz
from atproto import Client

def format_name(full_name):
    clean_name = str(full_name).replace('Jr.', '').replace('Sr.', '').strip()
    parts = clean_name.split()
    if len(parts) >= 2:
        return f"{parts[-1]}, {parts[0][0]}"
    return full_name

def post_lineup():
    game_file = "game_number.txt"
    if os.path.exists(game_file):
        with open(game_file, "r", encoding='utf-8') as f:
            try:
                current_game = int(f.read().strip())
            except:
                current_game = 1
    else:
        current_game = 1

    ny_tz = pytz.timezone('America/New_York')
    ny_now = datetime.datetime.now(ny_tz)
    
    if ny_now.hour not in range(11, 23):
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
        batters_df = pd.read_csv('mets_batters.csv', encoding='utf-8')
        pitchers_df = pd.read_csv('mets_pitchers.csv', encoding='utf-8')
        batters_df.columns = [str(c).replace('\xa0', ' ').strip() for c in batters_df.columns]
        
        pos_col = next((n for n in ['Pos Summary', 'Pos', 'Positions'] if n in batters_df.columns), None)
        if not pos_col: return
        batters_df.rename(columns={pos_col: 'Pos Summary'}, inplace=True)

        # Strict Filter: Must have a defensive number 2-9 and NOT be a Pitcher
        batters_df = batters_df[batters_df['Pos Summary'].astype(str).str.contains('[2-9]', regex=True, na=False)].copy()
        batters_df = batters_df[~batters_df['Pos Summary'].astype(str).str.contains('P', na=False)].copy()
            
    except Exception as e:
        print(f"Error: {e}")
        return

    # --- 4. LINEUP SELECTION (THE POSITIONAL DRAFT) ---
    lineup_sample = batters_df.sample(n=9).copy()
    for col in ['OBP', 'SLG']:
        lineup_sample[col] = pd.to_numeric(lineup_sample[col], errors='coerce').fillna(0)
    lineup_sample['HITTING_VAL'] = (lineup_sample['OBP'] * 1.2) + (lineup_sample['SLG'] * 1.0)
    
    # Sort by hitting value to define the batting order 1-9
    lineup_sample = lineup_sample.sort_values(by='HITTING_VAL', ascending=False).reset_index()

    # The Draft: Assign 2-9 to the best fit
    mapping = {'2':'C', '3':'1B', '4':'2B', '5':'3B', '6':'SS', '7':'LF', '8':'CF', '9':'RF'}
    assignments = {} # {player_index: position_name}
    taken_field_pos = set()

    # First Pass: Try to give everyone their 'Primary' (first listed) position
    for idx, player in lineup_sample.iterrows():
        primary = str(player['Pos Summary'])[0]
        if primary in mapping and primary not in taken_field_pos:
            assignments[idx] = mapping[primary]
            taken_field_pos.add(primary)

    # Second Pass: For those without a spot, check their other positions
    for idx, player in lineup_sample.iterrows():
        if idx not in assignments:
            for char in str(player['Pos Summary']):
                if char in mapping and char not in taken_field_pos:
                    assignments[idx] = mapping[char]
                    taken_field_pos.add(char)
                    break
    
    # Final Pass: Anyone left over is the DH
    for idx in range(9):
        if idx not in assignments:
            assignments[idx] = "DH"

    final_lineup_text = []
    for idx, player in lineup_sample.iterrows():
        p_name = format_name(player['Name'])
        pos = assignments[idx]
        final_lineup_text.append(f"{idx+1}. {p_name} - {pos}")

    # --- 5. PITCHING ---
    used_names = set(lineup_sample['Name'].tolist())
    available_p = pitchers_df[~pitchers_df['Name'].isin(used_names)].copy()
    sp_row = available_p.sample(1).iloc[0]
    sp_name = format_name(sp_row['Name'])
    used_names.add(sp_row['Name'])
    rp_pool = available_p[~available_p['Name'].isin(used_names)].sample(min(4, len(available_p)-1))
    rp_names = [format_name(n) for n in rp_pool['Name'].tolist()]

    # --- 6. CONSTRUCT & POST ---
    status_text = f"Game #{current_game}\nManager: {selected_manager}\n\n" + "\n".join(final_lineup_text) + f"\n\nP: {sp_name}\n\nBullpen:\n" + "\n".join(rp_names) + "\n\n#MetsSky"

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(status_text)
        with open(game_file, "w", encoding='utf-8') as f:
            f.write(str(current_game + 1))
    except Exception as e:
        print(f"Post failed: {e}")

if __name__ == "__main__":
    post_lineup()
