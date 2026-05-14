import pandas as pd
import random
from atproto import Client
import os

def solve_defense(players, required_positions):
    if not players:
        return {}
    current_player = players[0]
    remaining_players = players[1:]
    summary = str(current_player.get('PosSummary', ''))
    
    # Try DH last to prioritize putting players in the field
    eligible_pos = [p for p in required_positions if p in summary]
    if 'DH' in required_positions:
        eligible_pos.append('DH')
    
    random.shuffle(eligible_pos)
    for pos in eligible_pos:
        result = solve_defense(remaining_players, [p for p in required_positions if p != pos])
        if result is not None:
            result[current_player['Name']] = pos
            return result
    return None

def generate_lineup():
    # Load once to prevent the recursion crash
    batters_df = pd.read_csv('mets_batters.csv')
    pitchers_df = pd.read_csv('mets_pitchers.csv')
    
    for col in ['OPS', 'OBP', 'SLG']:
        batters_df[col] = pd.to_numeric(batters_df[col], errors='coerce').fillna(0)
    batters_df['PosSummary'] = batters_df['PosSummary'].fillna('')

    # To avoid the loop, let's ensure we pick at least one person eligible for the hard spots
    # We'll pick one candidate for each of the 8 field spots, then 1 extra
    core_positions = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF']
    sampled_batters = []
    
    for pos in core_positions:
        # Pick a player who has actually played this position
        match = batters_df[batters_df['PosSummary'].str.contains(pos)].sample(1)
        sampled_batters.append(match.iloc[0].to_dict())
    
    # Add one more random "Wildcard" for the DH/Bench
    wildcard = batters_df.sample(1).iloc[0].to_dict()
    sampled_batters.append(wildcard)

    # Strategy-based Batting Order
    lineup = [None] * 9
    pool = sorted(sampled_batters, key=lambda x: x['OPS'], reverse=True)
    lineup[0] = max(pool, key=lambda x: x['OBP'])
    pool.remove(lineup[0])
    lineup[3] = max(pool, key=lambda x: x['SLG'])
    pool.remove(lineup[3])
    lineup[1] = max(pool, key=lambda x: x['OPS'])
    pool.remove(lineup[1])
    
    remaining_slots = [2, 4, 5, 6, 7, 8]
    pool = sorted(pool, key=lambda x: x['OPS'], reverse=True)
    for i, slot in enumerate(remaining_slots):
        lineup[slot] = pool[i]

    # Field Assignment
    pos_list = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH']
    defense_map = solve_defense(lineup, pos_list)
    
    # Fail-safe: if it still fails, just do one retry (not infinite recursion)
    if not defense_map:
        return generate_lineup()

    pitchers_df['GS'] = pd.to_numeric(pitchers_df['GS'], errors='coerce').fillna(0)
    starter = pitchers_df[pitchers_df['GS'] >= 5].sample(1).iloc[0]
    bullpen = pitchers_df[pitchers_df['Name'] != starter['Name']].sample(4).to_dict('records')

    return lineup, defense_map, starter, bullpen

def post_to_bluesky():
    try:
        lineup, defense, starter, bullpen = generate_lineup()
        post_text = "Mets Mystery Manager - Daily Lineup\n\n"
        for i, player in enumerate(lineup):
            post_text += f"{i+1}. {player['Name']} {defense[player['Name']]}\n"
        post_text += f"\nP: {starter['Name']}\n"
        post_text += f"Bullpen: {', '.join([p['Name'] for p in bullpen])}"

        client = Client()
        client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
        client.send_post(post_text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    post_to_bluesky()
