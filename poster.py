import pandas as pd
import random
from atproto import Client
import os

def solve_defense(players, required_positions):
    if not players:
        return {}

    current_player = players[0]
    remaining_players = players[1:]
    
    # Treat the PosSummary as a string to avoid the 'float' error
    summary = str(current_player.get('PosSummary', ''))
    
    # Everyone is eligible to DH
    eligible_pos = [p for p in required_positions if p in summary or p == 'DH']
    random.shuffle(eligible_pos)

    for pos in eligible_pos:
        result = solve_defense(remaining_players, [p for p in required_positions if p != pos])
        if result is not None:
            result[current_player['Name']] = pos
            return result
    return None

def generate_lineup():
    batters_df = pd.read_csv('mets_batters.csv')
    pitchers_df = pd.read_csv('mets_pitchers.csv')
    
    # Clean the data: Treat empty stats as 0 and empty positions as blank strings
    for col in ['OPS', 'OBP', 'SLG']:
        batters_df[col] = pd.to_numeric(batters_df[col], errors='coerce').fillna(0)
    batters_df['PosSummary'] = batters_df['PosSummary'].fillna('')

    # Draft 9 unique batters
    sampled_batters = batters_df.sample(9).to_dict('records')
    
    # Set Batting Order by Strategy
    lineup = [None] * 9
    pool = sorted(sampled_batters, key=lambda x: x['OPS'], reverse=True)
    
    lineup[0] = max(pool, key=lambda x: x['OBP'])  # #1 Leadoff (OBP)
    pool.remove(lineup[0])
    
    lineup[3] = max(pool, key=lambda x: x['SLG'])  # #4 Cleanup (SLG)
    pool.remove(lineup[3])
    
    lineup[1] = max(pool, key=lambda x: x['OPS'])  # #2 Best Overall (OPS)
    pool.remove(lineup[1])
    
    # Fill remaining spots (3, 5, 6, 7, 8, 9) by descending OPS
    remaining_slots = [2, 4, 5, 6, 7, 8]
    pool = sorted(pool, key=lambda x: x['OPS'], reverse=True)
    for i, slot in enumerate(remaining_slots):
        lineup[slot] = pool[i]

    # Assign Defense based on PosSummary eligibility
    pos_list = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH']
    defense_map = solve_defense(lineup, pos_list)
    
    # If this specific 9-man group can't field a team, pull a new 9
    if not defense_map:
        return generate_lineup()

    # Pitcher Logic: Require at least 5 Games Started for the starter
    pitchers_df['GS'] = pd.to_numeric(pitchers_df['GS'], errors='coerce').fillna(0)
    starter = pitchers_df[pitchers_df['GS'] >= 5].sample(1).iloc[0]
    bullpen = pitchers_df[pitchers_df['Name'] != starter['Name']].sample(4).to_dict('records')

    return lineup, defense_map, starter, bullpen

def post_to_bluesky():
    lineup, defense, starter, bullpen = generate_lineup()
    
    post_text = "Mets Mystery Manager - Daily Lineup\n\n"
    for i, player in enumerate(lineup):
        post_text += f"{i+1}. {player['Name']} {defense[player['Name']]}\n"
    
    post_text += f"\nP: {starter['Name']}\n"
    post_text += f"Bullpen: {', '.join([p['Name'] for p in bullpen])}"

    client = Client()
    client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
    client.send_post(post_text)

if __name__ == "__main__":
    post_to_bluesky()
