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
            return char
    return 'DH'

def post_lineup():
    # --- DST GUARD ---
    # Ensures the post only happens during the 1:00 PM (13:00) hour in New York
    ny_tz = pytz.timezone('America/New_York')
    ny_now = datetime.datetime.now(ny_tz)
    
    if ny_now.hour != 13:
        print(f"Skipping... Current NY hour is {ny_now.hour}. Manager waiting for 13:00.")
        return 

    # 1. Load Data
    try:
        batters_df = pd.read_csv('mets_batters.csv')
        pitchers_df = pd.read_csv('mets_pitchers.csv')
    except Exception as e:
        print(f"Error loading CSVs: {e}")
        return

    # Clean numeric columns for sorting
    for col in ['BA', 'OBP', 'SLG']:
        if col in batters_df.columns:
            batters_df[col] = pd.to_numeric(batters_df[col], errors='coerce').fillna(0)

    # 2. Manager Logic: Pick 9 unique hitters
    lineup_sample = batters_df.sample(min(9, len(batters_df))).copy()
    lineup_sample['HITTING_VAL'] = (lineup_sample.get('OBP', 0) * 1.2) + (lineup_sample.get('SLG', 0) * 1.0)
    
    if 'Pos Summary' in lineup_sample.columns:
        lineup_sample['PRIMARY_POS'] = lineup_sample['Pos Summary'].apply(get_primary_pos)
        lineup_sample['POS_COUNT'] = lineup_sample['Pos Summary'].str.len()
    else:
        lineup_sample['PRIMARY_POS'] = 'DH'
        lineup_sample['POS_COUNT'] = 1

    lineup_sample = lineup_sample.sort_values(by='HITTING_VAL', ascending=False)
    
    final_lineup_text = []
    taken_positions = set()
    dh_candidate_idx = lineup_sample['POS_COUNT'].idxmax() if 'POS_COUNT' in lineup_sample.columns else lineup_sample.index[0]
    
    for i, (idx, player) in enumerate(lineup_sample.iterrows(), 1):
        pos_code = str(player['PRIMARY_POS'])
        if idx == dh_candidate_idx or pos_code in taken_positions or pos_code == 'DH':
            actual_pos = 'DH'
        else:
            mapping = {'2':'C', '3':'1B', '4':'2B', '5':'3B', '6':'SS', '7':'LF', '8':'CF', '9':'RF'}
            actual_pos = mapping.get(pos_code, 'DH')
            taken_positions.add(pos_code)
        final_lineup_text.append(f"{i}. {player['Name']} - {actual_pos}")

    # 3. Pitching Staff
    used_names = set(lineup_sample['Name'].tolist())
    available_p = pitchers_df[~pitchers_df['Name'].isin(used_names)].copy()
    
    sp_name = available_p.sample(1).iloc[0]['Name']
    if 'GS' in available_p.columns:
        starters = available_p[pd.to_numeric(available_p['GS'], errors='coerce') > 0]
        if not starters.empty:
            sp_name = starters.sample(1).iloc[0]['Name']

    used_names.add(sp_name)
    bullpen_pool = available_p[~available_p['Name'].isin(used_names)]
    bullpen = bullpen_pool.sample(min(4, len(bullpen_pool)))['Name'].tolist()

    # 4. Format Post
    status_text = "⚾️ Today's Mystery Manager Lineup:\n\n"
    status_text += "\n".join(final_lineup_text)
    status_text += f"\n\nP: {sp_name}"
    status_text += "\n------------------"
    status_text += f"\n\n🔥 Bullpen Available:\nRP: {bullpen[0]}\nRP: {bullpen[1]}\nRP: {bullpen[2]}\nCL: {bullpen[3]}"
    status_text += "\n\n#LGM #MetsLaundry #TheRallyTowel"

    # 5. Post to Bluesky using your specific secret names
    try:
        client = Client()
        handle = os.environ.get('BSKY_HANDLE')
        password = os.environ.get('BSKY_PASSWORD')
        
        if not handle or not password:
            print("FAILED: Secrets BSKY_HANDLE or BSKY_PASSWORD are not set.")
            return

        client.login(handle, password)
        client.send_post(status_text)
        print("Success! Mystery Manager post is live.")
    except Exception as e:
        print(f"FAILED TO POST: {e}")

if __name__ == "__main__":
    post_lineup()
