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
    pos_df = pd.read_csv('Mets_Positional_History - Mets_Positional_History.csv')
    bat_df = pd.read_csv('mets_batters.csv')
    pitchers_df = pd.read_csv('mets_pitchers.csv')
    
    pos_df.columns = [c.strip() for c in pos_df.columns]
    bat_df.columns = [c.strip() for c in bat_df.columns]
    pos_cols = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'P']

    pos_df = pos_df[pos_df['Player'].notna() & (pos_df['Player'].astype(str).str.lower() != 'player')]
    for p_col in pos_cols:
        if p_col in pos_df.columns:
            pos_df[p_col] = pd.to_numeric(pos_df[p_col], errors='coerce').fillna(0)
    
    pos_master = pos_df.groupby('Player').agg({p: 'sum' for p in pos_cols if p in pos_df.columns}).reset_index()
    def get_eligible_list(row):
        return [p for p in pos_cols if p in row and row[p] > 0]
    pos_master['EligiblePositions'] = pos_master.apply(get_eligible_list, axis=1)

    bat_df = bat_df.rename(columns={'Name': 'Player'})
    for stat in ['OBP', 'OPS', 'SLG']:
        bat_df[stat] = pd.to_numeric(bat_df[stat], errors='coerce').fillna(0)

    master_df = pd.merge(pos_master, bat_df[['Player', 'OBP', 'OPS', 'SLG']], on='Player', how='inner')
    
    all_sampled = master_df.sample(14).to_dict('records')
    starters = all_sampled[:9]
    bench = all_sampled[9:]

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

    required_pos = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH']
    defense_map = solve_defense(lineup, required_pos)
    if not defense_map:
        return generate_lineup()

    pitchers_df['GS'] = pd.to_numeric(pitchers_df['GS'], errors='coerce').fillna(0)
    starter_p = pitchers_df[pitchers_df['GS'] >= 5].sample(1).iloc[0]
    bullpen = pitchers_df[pitchers_df['Name'] != starter_p['Name']].sample(4).to_dict('records')

    return lineup, defense_map, starter_p, bullpen, bench

def post_to_bluesky():
    try:
        lineup, defense, starter, bullpen, bench = generate_lineup()
        
        # 1. MAIN POST (Lineup + Starter only)
        post_text = "Game #4\n\n"
        for i, p in enumerate(lineup):
            name = p['Player']
            post_text += f"{i+1} {name} {defense[name]}\n"
        
        post_text += f"\nP: {starter['Name']}"

        # 2. REPLY POST (Bullpen + Bench)
        bp_names = ", ".join([p['Name'] for p in bullpen])
        bench_names = ", ".join([b['Player'] for b in bench])
        reply_text = f"Bullpen: {bp_names}\n\nBench: {bench_names}"

        client = Client()
        client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
        
        # Send main post
        root_post = client.send_post(post_text)
        
        # Send reply
        parent_ref = {'cid': root_post.cid, 'uri': root_post.uri}
        client.send_post(reply_text, reply_to={'root': parent_ref, 'parent': parent_ref})

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    post_to_bluesky()
