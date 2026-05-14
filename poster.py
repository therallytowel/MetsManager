import pandas as pd
import random
from atproto import Client
import os
import unicodedata

def solve_defense(players, required_positions):
    if not players:
        return {}
    current_player = players[0]
    remaining_players = players[1:]
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

def clean_text(text):
    if isinstance(text, str):
        return unicodedata.normalize('NFC', text)
    return text

def generate_lineup():
    pos_df = pd.read_csv('Mets_Positional_History - Mets_Positional_History.csv', encoding='utf-8-sig')
    bat_df = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
    pitchers_df = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
    
    pos_df.columns = [c.strip() for c in pos_df.columns]
    bat_df.columns = [c.strip() for c in bat_df.columns]
    pitchers_df.columns = [c.strip() for c in pitchers_df.columns]
    
    field_pos_cols = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF']

    # Position Player Processing
    pos_df = pos_df[pos_df['Player'].notna() & (pos_df['Player'].astype(str).str.lower() != 'player')]
    pos_df['Player'] = pos_df['Player'].apply(clean_text)
    for p_col in field_pos_cols:
        if p_col in pos_df.columns:
            pos_df[p_col] = pd.to_numeric(pos_df[p_col], errors='coerce').fillna(0)
    
    pos_master = pos_df.groupby('Player').agg({p: 'sum' for p in field_pos_cols if p in pos_df.columns}).reset_index()
    def get_eligible_list(row):
        return [p for p in field_pos_cols if p in row and row[p] > 0]
    pos_master['EligiblePositions'] = pos_master.apply(get_eligible_list, axis=1)

    bat_df = bat_df.rename(columns={'Name': 'Player'})
    bat_df['Player'] = bat_df['Player'].apply(clean_text)
    master_batters = pd.merge(pos_master, bat_df[['Player', 'OBP', 'OPS', 'SLG']], on='Player', how='inner')

    # Pitcher Processing with Specific Buckets
    pitchers_df['Name'] = pitchers_df['Name'].apply(clean_text)
    pitchers_df['GS'] = pd.to_numeric(pitchers_df['GS'], errors='coerce').fillna(0)
    
    # Identify roles based on history
    pitcher_stats = pitchers_df.groupby('Name').agg({'GS': 'sum', 'Name': 'count'}).rename(columns={'Name': 'Apps'}).reset_index()
    
    # 1. Bullpen ONLY (0 Starts)
    bp_only = pitcher_stats[pitcher_stats['GS'] == 0]['Name'].tolist()
    # 2. Starters ONLY (Starts == Appearances)
    starters_only = pitcher_stats[pitcher_stats['GS'] == pitcher_stats['Apps']]['Name'].tolist()
    # 3. Hybrid (Can do both)
    hybrids = pitcher_stats[(pitcher_stats['GS'] > 0) & (pitcher_stats['GS'] < pitcher_stats['Apps'])]['Name'].tolist()

    # Draft Position Players (14 Total)
    pitcher_names = pitcher_stats['Name'].tolist()
    clean_batter_pool = master_batters[~master_batters['Player'].isin(pitcher_names)]
    all_sampled = clean_batter_pool.sample(14).to_dict('records')
    starters_df = all_sampled[:9]
    bench = all_sampled[9:]

    # Lineup Strategy
    pool = sorted(starters_df, key=lambda x: x['OPS'], reverse=True)
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

    required_pos = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH']
    defense_map = solve_defense(lineup, required_pos)
    if not defense_map:
        return generate_lineup()

    # Pitching Selection Logic
    batter_names = [p['Player'] for p in all_sampled]
    
    # Valid Starters: Hybrid OR Starter-Only
    valid_starters = [n for n in (starters_only + hybrids) if n not in batter_names]
    starter_name = random.choice(valid_starters)
    
    # Valid Bullpen: Hybrid OR Bullpen-Only
    valid_rp = [n for n in (bp_only + hybrids) if n not in batter_names and n != starter_name]
    bullpen_names = random.sample(valid_rp, 4)

    managers = ["Casey Stengel", "Wes Westrum", "Gil Hodges", "Yogi Berra", "Roy McMillan", 
                "Joe Frazier", "Joe Torre", "George Bamberger", "Frank Howard", "Davey Johnson", 
                "Bud Harrelson", "Mike Cubbage", "Jeff Torborg", "Dallas Green", "Bobby Valentine", 
                "Art Howe", "Willie Randolph", "Jerry Manuel", "Terry Collins", "Mickey Callaway", 
                "Carlos Beltrán", "Luis Rojas", "Buck Showalter", "Carlos Mendoza"]
    mgr = clean_text(random.choice(managers))

    return lineup, defense_map, starter_name, bullpen_names, bench, mgr

def post_to_bluesky():
    try:
        lineup, defense, starter, bullpen, bench, mgr = generate_lineup()
        
        post_text = f"Game #4\nMgr: {mgr}\n\n"
        for i, p in enumerate(lineup):
            name = p['Player']
            post_text += f"{i+1} {name} {defense[name]}\n"
        post_text += f"\nP: {starter}"

        bp_text = ", ".join(bullpen)
        bench_names = ", ".join([b['Player'] for b in bench])
        reply_text = f"Bullpen: {bp_text}\n\nBench: {bench_names}"

        client = Client()
        client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
        
        root_post = client.send_post(post_text)
        parent_ref = {'cid': root_post.cid, 'uri': root_post.uri}
        client.send_post(reply_text, reply_to={'root': parent_ref, 'parent': parent_ref})
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    post_to_bluesky()
