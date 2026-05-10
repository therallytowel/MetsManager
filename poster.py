import pandas as pd
import os
import random
import datetime
import pytz
from atproto import Client

def get_primary_pos(pos_str):
    # Returns the first defensive position (2-9) found in the string
    for char in str(pos_str):
        if char in '23456789':
            mapping = {'2':'C', '3':'1B', '4':'2B', '5':'3B', '6':'SS', '7':'LF', '8':'CF', '9':'RF'}
            return char
    return 'DH'

def post_lineup():
    # --- DST GUARD ---
    # Ensures the bot only posts during the 1:00 PM ET hour
    ny_tz = pytz.timezone('America/New_York')
    ny_now = datetime.datetime.now(ny_tz)
    
    if ny_now.hour != 13:
        print(f"Skipping... Current NY hour is {ny_now.hour}. Manager is waiting for 13:00.")
        return 

    # 1. Load and Clean Data
    try:
        batters_df = pd.read_csv('mets_batters.csv')
        pitchers_df = pd.read_csv('mets_pitchers.csv')
    except Exception as e:
        print(f"Error loading CSVs: {e}")
        return

    for col in ['BA', 'OBP', 'SLG', 'OPS']:
        batters_df[col] = pd.to_numeric(batters_df[col], errors='coerce').fillna(0)

    # 2. Manager Logic: Select 9 unique hitters and calculate 'Manager Score'
    # We pull a sample, then determine the best hitting lineup from it
    lineup_sample = batters_df.sample(9).copy()
    
    # Weighted Score: Prioritizes OBP and SLG
    lineup_sample['HITTING_VAL'] = (lineup_sample['OBP'] * 1.2) + (lineup_sample['SLG'] * 1.0)
    lineup_sample['PRIMARY_POS'] = lineup_sample['Pos Summary'].apply(get_primary_pos)
    lineup_sample['POS_COUNT'] = lineup_sample['Pos Summary'].str.len() 

    # Sort the 9 players by HITTING_VAL to set the batting order (1-9)
    lineup_sample = lineup_sample.sort_values(by='HITTING_VAL', ascending=False)
    
    final_lineup_text = []
    taken_positions = set()
    
    # Identify the DH: The player with the most "positional noise" (utility players or blocked starters)
    # This prevents just 'plopping' a player into the DH spot randomly
    dh_candidate_idx = lineup_sample['POS_COUNT'].idxmax()
    
    for i, (idx, player) in enumerate(lineup_sample.iterrows(), 1):
        pos_code = player['PRIMARY_POS']
        
        # If the position is taken or they are the DH candidate, they DH
        if idx == dh_candidate_idx or pos_code in taken_positions or pos_code == 'DH':
            actual_pos = 'DH'
        else:
            mapping = {'2':'C', '3':'1B', '4':'2B', '5':'3B', '6':'SS', '7':'LF', '8':'CF', '9':'RF'}
            actual_pos = mapping.get(pos_code, 'DH')
            taken_positions.add(pos_code)
            
        final_lineup_text.append(f"{i}. {player['Name']} - {actual_pos}")

    # 3. Pitching Staff (Unique from hitters)
    used_names = set(lineup_sample['Name'].tolist())
    available_p = pitchers_df[~pitchers_df['Name'].isin(used_names)].copy()
    
    # Pull 1 Starter
    starters = available_p[pd.to_numeric(available_p['GS'], errors='coerce') >= 1]
    sp_name = starters.sample(1).iloc[0]['Name']
    used_names.add(sp_name)
    
    # Pull Bullpen
    bullpen_pool = available_p[~available_p['Name'].isin(used_names)].copy()
    cl_name = bullpen_pool[pd.to_numeric(bullpen_pool['SV'], errors='coerce') >= 1].sample(1).iloc[0]['Name']
    used_names.add(cl_name)
    rp_names = bullpen_pool[~bullpen_pool['Name'].isin(used_names)].sample(3)['Name'].tolist()

    # 4. Format the Text
    status_text = "⚾️ Today's Mystery Manager Lineup:\n\n"
    status_text += "\n".join(final_lineup_text)
    status_text += f"\n\nP: {sp_name}"
    status_text += "\n------------------"
    status_text += f"\n\n🔥 Bullpen Available:\nRP: {rp_names[0]}\nRP: {rp_names[1]}\nRP: {rp_names[2]}\nCL: {cl_name}"
    status_text += "\n\n#LGM #MetsLaundry #TheRallyTowel"

    # 5. Connect and Post to Bluesky
    try:
        client = Client()
        client.login(os.environ['BLUESKY_HANDLE'], os.environ['BLUESKY_PASSWORD'])
        client.send_post(status_text)
        print("Success! Mystery Manager post is live.")
    except Exception as e:
        print(f"Post failed: {e}")

if __name__ == "__main__":
    post_lineup()
