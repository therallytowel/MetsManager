import pandas as pd
import random
from atproto import Client
import os

def solve_defense(players, required_positions):
    if not players:
        return {}
    current_player = players[0]
    remaining_players = players[1:]
    
    # Check eligibility based on the list of positions we identified earlier
    eligible_pos = [p for p in required_positions if p in current_player['EligiblePositions']]
    if 'DH' in required_positions:
        eligible_pos.append('DH')
    
    random.shuffle(eligible_pos)
    for pos in eligible_pos:
        result = solve_defense(remaining_players, [p for p in required_positions if p != pos])
        if result is not None:
            result[current_player['Player']] = pos
            return result
    return None

def generate_lineup():
    # 1. Load the specific history file
    filename = 'Mets_Positional_History - Mets_Positional_History.csv'
    df = pd.read_csv(filename)
    pitchers_df = pd.read_csv('mets_pitchers.csv')
    
    # 2. Identify Position Columns
    # We look for the exact abbreviations you provided
    pos_cols = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'P']
    
    # Standardize Column Names (Handling potential spaces from the merge)
    df.columns = [c.strip() for c in df.columns]

    # 3. CLEANUP
    df = df[df['Player'].notna()]
    df = df[df['Player'].astype(str).str.lower() != 'player']

    # Convert position columns to numeric (filling NaNs with 0)
    for p_col in pos_cols:
        if p_col in df.columns:
            df[p_col] = pd.to_numeric(df[p_col], errors='coerce').fillna(0)

    # 4. AGGREGATE ELIGIBILITY
    # We sum the games at each position across all years for every player
    agg_dict = {p: 'sum' for p in pos_cols if p in df.columns}
    # Add stats (taking the max/peak performance found in the data)
    agg_dict.update({'OPS': 'max', 'OBP': 'max', 'SLG': 'max'})
    
    player_master = df.groupby('Player').agg(agg_dict).reset_index()

    # Create a list of positions where the player has > 0 games played
    def get_eligible_list(row):
        return [p for p in pos_cols if p in row and row[p] > 0]

    player_master['EligiblePositions'] = player_master.apply(get_eligible_list, axis=1)

    # 5. DRAFT & ORDERING
    # Ensure stats are numeric for the lineup strategy
    for col in ['OPS', 'OBP', 'SLG']:
        player_master[col] = pd.to_numeric(player_master[col], errors='coerce').fillna(0)

    sampled_players = player_master.sample(9).to_dict('records')
    lineup = [None] * 9
    pool = sorted(sampled_players, key=lambda x: x.get('OPS', 0), reverse=True)
    
    lineup[0] = max(pool, key=lambda x: x.get('OBP', 0)) 
    pool.remove(lineup[0])
    lineup[3] = max(pool, key=lambda x: x.get('SLG', 0)) 
    pool.remove(lineup[3])
    lineup[1] = max(pool, key=lambda x: x.get('OPS', 0)) 
    pool.remove(lineup[1])
    
    remaining_slots = [2, 4, 5, 6, 7, 8]
    pool = sorted(pool, key=lambda x: x.get('OPS', 0), reverse=True)
    for i, slot in enumerate(remaining_slots):
        lineup[slot] = pool[i]

    # 6. ASSIGN POSITIONS
    required_pos = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH']
    defense_map = solve_defense(lineup, required_pos)
    
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
            name = player['Player']
            post_text += f"{i+1}. {name} ({defense[name]})\n"
        
        post_text += f"\nP: {starter['Name']}\n"
        post_text += f"Bullpen: {', '.join([p['Name'] for p in bullpen])}"

        client = Client()
        client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
        client.send_post(post_text)
    except Exception as e:
        print(f"Bot Error: {e}")

if __name__ == "__main__":
    post_to_bluesky()
