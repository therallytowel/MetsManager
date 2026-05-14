import pandas as pd
import random
from atproto import Client
import os

def solve_defense(players, required_positions):
    if not players:
        return {}
    current_player = players[0]
    remaining_players = players[1:]
    
    # Check eligibility based on the aggregated 'EligiblePositions' from the merge
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
    # 1. LOAD ALL THREE FILES
    pos_df = pd.read_csv('Mets_Positional_History - Mets_Positional_History.csv')
    bat_df = pd.read_csv('mets_batters.csv')
    pitchers_df = pd.read_csv('mets_pitchers.csv')
    
    # 2. STANDARDIZE COLUMNS
    pos_df.columns = [c.strip() for c in pos_df.columns]
    bat_df.columns = [c.strip() for c in bat_df.columns]
    pitchers_df.columns = [c.strip() for c in pitchers_df.columns]
    
    pos_cols = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'P']

    # 3. PROCESS POSITIONAL ELIGIBILITY
    pos_df = pos_df[pos_df['Player'].notna() & (pos_df['Player'].astype(str).str.lower() != 'player')]
    for p_col in pos_cols:
        if p_col in pos_df.columns:
            pos_df[p_col] = pd.to_numeric(pos_df[p_col], errors='coerce').fillna(0)

    # Aggregate by Player to capture all positions played across all years
    pos_master = pos_df.groupby('Player').agg({p: 'sum' for p in pos_cols if p in pos_df.columns}).reset_index()
    
    def get_eligible_list(row):
        return [p for p in pos_cols if p in row and row[p] > 0]
    pos_master['EligiblePositions'] = pos_master.apply(get_eligible_list, axis=1)

    # 4. PROCESS BATTING STATS
    # Rename 'Name' to 'Player' to facilitate the merge
    bat_df = bat_df.rename(columns={'Name': 'Player'})
    for stat in ['OBP', 'OPS', 'SLG']:
        if stat in bat_df.columns:
            bat_df[stat] = pd.to_numeric(bat_df[stat], errors='coerce').fillna(0)

    # 5. MERGE BATTERS WITH POSITIONS
    # This creates a pool of players who have both stats and defensive data
    master_batters = pd.merge(pos_master, bat_df[['Player', 'OBP', 'OPS', 'SLG']], on='Player', how='inner')

    # 6. DRAFT & LINEUP STRATEGY
    sampled_players = master_batters.sample(9).to_dict('records')
    lineup = [None] * 9
    pool = sorted(sampled_players, key=lambda x: x['OPS'], reverse=True)
    
    lineup[0] = max(pool, key=lambda x: x['OBP']) # Leadoff (OBP)
    pool.remove(lineup[0])
    lineup[3] = max(pool, key=lambda x: x['SLG']) # Cleanup (Power)
    pool.remove(lineup[3])
    lineup[1] = max(pool, key=lambda x: x['OPS']) # #2 (Overall)
    pool.remove(lineup[1])
    
    remaining_slots = [2, 4, 5, 6, 7, 8]
    pool = sorted(pool, key=lambda x: x['OPS'], reverse=True)
    for i, slot in enumerate(remaining_slots):
        lineup[slot] = pool[i]

    # 7. ASSIGN DEFENSE
    required_pos = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH']
    defense_map = solve_defense(lineup, required_pos)
    
    if not defense_map:
        return generate_lineup()

    # 8. PROCESS PITCHING (Starters vs Relievers)
    pitchers_df['GS'] = pd.to_numeric(pitchers_df['GS'], errors='coerce').fillna(0)
    # A 'Starter' is anyone with 5+ Games Started in their dataset
    starter = pitchers_df[pitchers_df['GS'] >= 5].sample(1).iloc[0]
    # Relievers are chosen from the remaining pool
    bullpen = pitchers_df[pitchers_df['Name'] != starter['Name']].sample(4).to_dict('records')

    return lineup, defense_map, starter, bullpen

def post_to_bluesky():
    try:
        lineup, defense, starter, bullpen = generate_lineup()
        
        post_text = "Mets Mystery Manager - Game #4\n\n"
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
