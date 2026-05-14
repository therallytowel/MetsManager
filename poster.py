import pandas as pd
import random
from atproto import Client
import os

def solve_defense(players, required_positions):
    if not players:
        return {}
    current_player = players[0]
    remaining_players = players[1:]
    eligible_pos = [p for p in required_positions if p in current_player['EligiblePositions']]
    
    # Universal DH Logic: Every player is DH eligible, but they cannot be a pitcher
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
    # 1. Load data from all three consolidated sources
    pos_df = pd.read_csv('Mets_Positional_History - Mets_Positional_History.csv')
    bat_df = pd.read_csv('mets_batters.csv')
    pitchers_df = pd.read_csv('mets_pitchers.csv')
    
    pos_df.columns = [c.strip() for c in pos_df.columns]
    bat_df.columns = [c.strip() for c in bat_df.columns]
    pitchers_df.columns = [c.strip() for c in pitchers_df.columns]
    
    # 2. Define standard fielding positions (excluding P and DH for the field pool)
    field_pos_cols = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF']

    # 3. Process Position Players: Aggregate all-time eligibility
    pos_df = pos_df[pos_df['Player'].notna() & (pos_df['Player'].astype(str).str.lower() != 'player')]
    for p_col in field_pos_cols:
        if p_col in pos_df.columns:
            pos_df[p_col] = pd.to_numeric(pos_df[p_col], errors='coerce').fillna(0)
    
    pos_master = pos_df.groupby('Player').agg({p: 'sum' for p in field_pos_cols if p in pos_df.columns}).reset_index()
    def get_eligible_list(row):
        return [p for p in field_pos_cols if p in row and row[p] > 0]
    pos_master['EligiblePositions'] = pos_master.apply(get_eligible_list, axis=1)

    # 4. Merge with Batting Stats
    bat_df = bat_df.rename(columns={'Name': 'Player'})
    for stat in ['OBP', 'OPS', 'SLG']:
        bat_df[stat] = pd.to_numeric(bat_df[stat], errors='coerce').fillna(0)
    
    master_batters = pd.merge(pos_master, bat_df[['Player', 'OBP', 'OPS', 'SLG']], on='Player', how='inner')

    # 5. THE ROLE FIREWALL: Remove anyone who appears in the pitching file from the hitting pool
    pitcher_names = pitchers_df['Name'].unique().tolist()
    clean_batter_pool = master_batters[~master_batters['Player'].isin(pitcher_names)]

    # 6. Draft 14 non-pitchers for the Lineup and Bench
    all_sampled = clean_batter_pool.sample(14).to_dict('records')
    starters = all_sampled[:9]
    bench = all_sampled[9:]

    # 7. Lineup Strategy based on Peak Stats
    pool = sorted(starters, key=lambda x: x['OPS'], reverse=True)
    lineup = [None] * 9
    lineup[0] = max(pool, key=lambda x: x['OBP'])
    pool.remove(lineup[0])
    lineup[3] = max(pool, key=lambda x: x['SLG'])
    pool.remove(lineup[3])
    lineup[1] = max(pool, key=lambda x: x['OPS'])
    pool.remove(lineup[1])
    
    rem_slots = [2, 4, 5, 6, 7, 8]
    pool = sorted(pool, key=lambda x: x['OPS'], reverse=True)
    for i, slot in enumerate(rem_slots):
        lineup[slot] = pool[i]

    # Assign Defense (Universal DH Rule applied inside solve_defense)
    required_pos = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH']
    defense_map = solve_defense(lineup, required_pos)
    if not defense_map:
        return generate_lineup()

    # 8. Pitching: Draft only from the pitching file (excluding any cross-pool names)
    pitchers_df['GS'] = pd.to_numeric(pitchers_df['GS'], errors='coerce').fillna(0)
    batter_names = [p['Player'] for p in all_sampled]
    clean_pitcher_pool = pitchers_df[~pitchers_df['Name'].isin(batter_names)]
    
    starter_p = clean_pitcher_pool[clean_pitcher_pool['GS'] >= 5].sample(1).iloc[0]
    bullpen = clean_pitcher_pool[clean_pitcher_pool['Name'] != starter_p['Name']].sample(4).to_dict('records')

    # 9. Random Manager Selection
    managers = ["Stengel", "Westrum", "Hodges", "Berra", "Frazier", "McMillan", "Torre", "Bamberger", 
                "Johnson", "Harrelson", "Cubbage", "Torborg", "Green", "Valentine", "Howe", "Randolph", 
                "Manuel", "Collins", "Callaway", "Beltrán", "Rojas", "Showalter", "Mendoza"]
    mgr = random.choice(managers)

    return lineup, defense_map, starter_p, bullpen, bench, mgr

def post_to_bluesky():
    try:
        lineup, defense, starter, bullpen, bench, mgr = generate_lineup()
        
        post_text = f"Game #4\nMgr: {mgr}\n\n"
        for i, p in enumerate(lineup):
            name = p['Player']
            post_text += f"{i+1} {name} {defense[name]}\n"
        post_text += f"\nP: {starter['Name']}"

        bp_names = ", ".join([p['Name'] for p in bullpen])
        bench_names = ", ".join([b['Player'] for b in bench])
        reply_text = f"Bullpen: {bp_names}\n\nBench: {bench_names}"

        client = Client()
        client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
        
        root_post = client.send_post(post_text)
        parent_ref = {'cid': root_post.cid, 'uri': root_post.uri}
        client.send_post(reply_text, reply_to={'root': parent_ref, 'parent': parent_ref})
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    post_to_bluesky()
