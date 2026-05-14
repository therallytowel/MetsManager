import pandas as pd
import random
from atproto import Client
import os

def solve_defense(players, required_positions):
    """Recursively assigns players to legal defensive spots."""
    if not players:
        return {}
    current_player = players[0]
    remaining_players = players[1:]
    summary = str(current_player.get('PosSummary', '')).upper()
    
    # Check eligibility for the required spots
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
    # 1. Load the specific exported file
    df = pd.read_csv('Mets_Positional_History - Mets_Positional_History.csv')
    pitchers_df = pd.read_csv('mets_pitchers.csv')
    
    # 2. Cleanup artifacts from the stacking process
    df = df[df['Name'].notna()]
    df = df[df['Name'] != 'Name'] # Removes the repeated headers
    
    # Ensure stats are numeric for the batting order logic
    for col in ['OPS', 'OBP', 'SLG']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    df['PosSummary'] = df['PosSummary'].fillna('').astype(str).str.upper()

    # 3. Select a Year
    available_years = df['Year'].unique()
    selected_year = random.choice(available_years)
    year_pool = df[df['Year'] == selected_year]
    
    # 4. Draft 9 players from that era
    # We sample for the 'hard' positions first to ensure a legal lineup exists
    core_spots = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF']
    sampled_batters = []
    
    for pos in core_spots:
        pos_options = year_pool[year_pool['PosSummary'].str.contains(pos)]
        if not pos_options.empty:
            sampled_batters.append(pos_options.sample(1).iloc[0].to_dict())
        else:
            sampled_batters.append(year_pool.sample(1).iloc[0].to_dict())
            
    # Add the DH wildcard
    sampled_batters.append(year_pool.sample(1).iloc[0].to_dict())

    # 5. Strategic Batting Order
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

    # 6. Final Defense Check
    pos_list = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH']
    defense_map = solve_defense(lineup, pos_list)
    
    if not defense_map:
        return generate_lineup() # Try a different combination if the 9 can't field

    # 7. Pitching
    pitchers_df['GS'] = pd.to_numeric(pitchers_df['GS'], errors='coerce').fillna(0)
    starter = pitchers_df[pitchers_df['GS'] >= 5].sample(1).iloc[0]
    bullpen = pitchers_df[pitchers_df['Name'] != starter['Name']].sample(4).to_dict('records')

    return lineup, defense_map, starter, bullpen, selected_year

def post_to_bluesky():
    lineup, defense, starter, bullpen, year = generate_lineup()
    
    post_text = f"Mets Mystery Manager - Game #4\nEra: {year} Season\n\n"
    for i, player in enumerate(lineup):
        name = player['Name']
        post_text += f"{i+1}. {name} ({defense[name]})\n"
    
    post_text += f"\nP: {starter['Name']}\n"
    post_text += f"Bullpen: {', '.join([p['Name'] for p in bullpen])}"

    client = Client()
    client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
    client.send_post(post_text)

if __name__ == "__main__":
    post_to_bluesky()
