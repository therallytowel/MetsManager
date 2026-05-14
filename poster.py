import pandas as pd
import random
from atproto import Client
import os

def solve_defense(players, required_positions):
    """
    A backtracking algorithm to ensure every player is assigned a 
    legal position based on their 'PosSummary' string.
    """
    if not players:
        return {}

    current_player = players[0]
    remaining_players = players[1:]
    
    # Everyone is eligible to DH
    eligible_pos = [p for p in required_positions if p in current_player['PosSummary'] or p == 'DH']
    
    random.shuffle(eligible_pos) # Add variety to assignments

    for pos in eligible_pos:
        # Recursive check to see if this assignment allows for a valid full lineup
        result = solve_defense(remaining_players, [p for p in required_positions if p != pos])
        if result is not None:
            result[current_player['Name']] = pos
            return result
    return None

def generate_lineup():
    # Load Data
    batters_df = pd.read_csv('mets_batters.csv')
    pitchers_df = pd.read_csv('mets_pitchers.csv')
    
    # 1. Draft the Talent: Pick 9 random unique batters
    sampled_batters = batters_df.sample(9).to_dict('records')
    
    # 2. Set Batting Order based on Strategy (OBP for leadoff, SLG for cleanup, etc.)
    # We sort by various stats to find the best fit for specific holes
    lineup = [None] * 9
    
    # Sort a copy to pick specialists
    pool = sorted(sampled_batters, key=lambda x: x.get('OPS', 0), reverse=True)
    
    # #1 Leadoff: Highest OBP in the sampled 9
    lineup[0] = max(pool, key=lambda x: x.get('OBP', 0))
    pool.remove(lineup[0])
    
    # #4 Cleanup: Highest SLG remaining
    lineup[3] = max(pool, key=lambda x: x.get('SLG', 0))
    pool.remove(lineup[3])
    
    # #2 The Best Hitter: Highest remaining OPS
    lineup[1] = max(pool, key=lambda x: x.get('OPS', 0))
    pool.remove(lineup[1])
    
    # Fill 3, 5, 6, 7, 8, 9 with remaining talent by descending OPS
    remaining_indices = [2, 4, 5, 6, 7, 8]
    pool = sorted(pool, key=lambda x: x.get('OPS', 0), reverse=True)
    for i, idx in enumerate(remaining_indices):
        lineup[idx] = pool[i]

    # 3. Defensive Assignment (The Positional Puzzle)
    # This ensures Baty never catches, but can play 3B/OF/DH.
    pos_list = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH']
    defense_map = solve_defense(lineup, pos_list)
    
    # If the random 9 literally cannot field a team (e.g., 9 DHs), try again
    if not defense_map:
        return generate_lineup()

    # 4. Pitching Staff: 1 Starter (high GS) and 4 Bullpen (high G/GF)
    starter = pitchers_df[pitchers_df['GS'] > 5].sample(1).iloc[0]
    bullpen = pitchers_df[pitchers_df['Name'] != starter['Name']].sample(4).tolist()

    return lineup, defense_map, starter, bullpen

def post_to_bluesky():
    lineup, defense, starter, bullpen = generate_lineup()
    
    # Formatting the post
    post_text = "Mets Mystery Manager - Daily Lineup\n\n"
    for i, player in enumerate(lineup):
        pos = defense[player['Name']]
        post_text += f"{i+1}. {player['Name']} {pos}\n"
    
    post_text += f"\nP: {starter['Name']}\n"
    post_text += f"Bullpen: {', '.join([p['Name'] for p in bullpen])}"

    # Bluesky Login
    client = Client()
    client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
    client.send_post(post_text)

if __name__ == "__main__":
    post_to_bluesky()
