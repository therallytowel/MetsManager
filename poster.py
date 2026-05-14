import pandas as pd
import random
from atproto import Client
import os

def solve_defense(players, required_positions):
    if not players:
        return {}
    current_player = players[0]
    remaining_players = players[1:]
    # Combine all positions this player ever played into one searchable string
    summary = str(current_player.get('AllPos', '')).upper()
    
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
    # 1. Load the consolidated history file
    df = pd.read_csv('Mets_Positional_History - Mets_Positional_History.csv')
    pitchers_df = pd.read_csv('mets_pitchers.csv')
    
    # 2. Force Headers and Clean
    new_cols = ['Year', 'Name', 'Age', 'Tm', 'Lg', 'G', 'PA', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'BA', 'OBP', 'SLG', 'OPS', 'OPS+', 'TB', 'GDP', 'HBP', 'SH', 'SF', 'IBB', 'PosSummary']
    df.columns = new_cols[:len(df.columns)]
    df = df[df['Name'].notna()]
    df = df[df['Name'].astype(str).str.lower() != 'name']

    # 3. MAPPING ELIGIBILITY: Group by Name to get all-time positions and best stats
    # This creates a 'Master List' where each player appears once with their full history
    player_master = df.groupby('Name').agg({
        'PosSummary': lambda x: ''.join(set(''.join(x.astype(str)))), # Merges all positions ever played
        'OPS': 'max',
        'OBP': 'max',
        'SLG': 'max'
    }).reset_index()
    player_master.rename(columns={'PosSummary': 'AllPos'}, inplace=True)

    # 4. DRAFT: Pick 9 random unique players from the 2,000+ available
    sampled_players = player_master.sample(9).to_dict('records')

    # 5. ORDERING: Use the player's peak career stats from your data
    lineup = [None] * 9
    pool = sorted(sampled_players, key=lambda x: x['OPS'], reverse=True)
    
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

    # 6. ASSIGN POSITIONS (Using the 'AllPos' string we created)
    pos_list = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH']
    defense_map = solve_defense(lineup, pos_list)
    
    # If the random 9 can't field a team (e.g., 9 DHs), pick a new 9
    if not defense_map:
        return generate_lineup()

    # 7. PITCHING
    pitchers_df['GS'] = pd.to_numeric(pitchers_df['GS'], errors='coerce').fillna(0)
    starter = pitchers_df[pitchers_df['GS'] >= 5].sample(1).iloc[0]
    bullpen = pitchers_df[pitchers_df['Name'] != starter['Name']].sample(4).to_dict('records')

    return lineup, defense_map, starter, bullpen

def post_to_bluesky():
    try:
        lineup, defense, starter, bullpen = generate_lineup()
        
        post_text = "Mets Mystery Manager - Game #4\nAll-Time Roster Selection\n\n"
        for i, player in enumerate(lineup):
            p_name = player['Name']
            post_text += f"{i+1}. {p_name} ({defense[p_name]})\n"
        
        post_text += f"\nP: {starter['Name']}\n"
        post_text += f"Bullpen: {', '.join([p['Name'] for p in bullpen])}"

        client = Client()
        client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
        client.send_post(post_text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    post_to_bluesky()
