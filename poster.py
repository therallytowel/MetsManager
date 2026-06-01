import pandas as pd
import random
from atproto import Client
import os
import unicodedata
from datetime import datetime, date
import pytz
import traceback

def solve_defense(players, required_positions):
    if not players: return {}
    current_player = players[0]
    remaining_players = players[1:]
    eligible_pos = [p for p in required_positions if p in current_player['EligiblePositions']]
    if 'DH' in required_positions: eligible_pos.append('DH')
    random.shuffle(eligible_pos)
    for pos in eligible_pos:
        result = solve_defense(remaining_players, [p for p in required_positions if p != pos])
        if result is not None:
            result[current_player['Player']] = pos
            return result
    return None

def calculate_amazin_index(lineup, starter_row, bp_rows, mgr_name):
    try:
        avg_ops = sum([float(p.get('OPS', 0.720)) for p in lineup]) / 9
        hitting_score = max(0, min((avg_ops - 0.600) * 160, 40))
        s_era = float(starter_row.get('ERA+', 100))
        bp_era = sum([float(p.get('ERA+', 100)) for p in bp_rows]) / len(bp_rows)
        pitching_score = max(0, min(((s_era - 100) * 0.4) + ((bp_era - 100) * 0.2) + 20, 40))
        return round(max(15, min(hitting_score + pitching_score + 25, 100)))
    except: return 85

def generate_lineup():
    pos_df = pd.read_csv('Mets_Positional_History - Mets_Positional_History.csv', encoding='utf-8-sig')
    bat_df = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
    pitchers_df = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
    
    for df, col_name in [(pos_df, 'Player'), (bat_df, 'Name'), (pitchers_df, 'Name')]:
        if col_name in df.columns:
            df[col_name] = df[col_name].apply(lambda x: unicodedata.normalize('NFKC', str(x)).strip())
    
    field_pos_cols = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF']
    for p_col in field_pos_cols:
        pos_df[p_col] = pd.to_numeric(pos_df[p_col], errors='coerce').fillna(0)
    
    pos_master = pos_df.groupby('Player')[field_pos_cols].sum().reset_index()
    pos_master['EligiblePositions'] = pos_master.apply(lambda r: [p for p in field_pos_cols if r[p] > 0], axis=1)
    
    master_batters = pd.merge(pos_master, bat_df.rename(columns={'Name': 'Player'}), on='Player', how='inner')
    p_stats = pitchers_df.groupby('Name').agg({'GS': 'sum', 'ERA+': 'mean', 'ASG': 'max'}).reset_index()
    
    all_sampled = master_batters.sample(15).to_dict('records')
    lineup_pool = all_sampled[:9]
    defense_map = solve_defense(lineup_pool, ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH'])
    
    # Handle potential None result from solver
    if defense_map is None:
        defense_map = {p['Player']: "DH" for p in lineup_pool}
    
    starter = p_stats[p_stats['GS'] > 0].sample(1).iloc[0]
    bp = p_stats[p_stats['Name'] != starter['Name']].sample(4).to_dict('records')
    
    return lineup_pool, defense_map, starter, bp, all_sampled[9:], "Terry Collins", calculate_amazin_index(lineup_pool, starter, bp, "Terry")

def post_to_bluesky():
    try:
        lineup, defense, starter, bp_rows, bench, mgr, score = generate_lineup()
        game_num = (datetime.now(pytz.timezone('America/New_York')).date() - date(2026, 5, 15)).days + 1
        
        post_text = f"Game #{game_num}\nAmazin' Index: {score}/100\nMgr: {mgr}\n\n"
        for p in lineup:
            name = p['Player']
            pos = defense.get(name, "DH")
            post_text += f"{name} {pos}\n"
        post_text += f"\nP: {starter['Name']}"

        bp_names = ", ".join([p['Name'] for p in bp_rows])
        bench_names = ", ".join([b['Player'] for b in bench])
        
        client = Client(base_url='https://bsky.social')
        client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
        root = client.send_post(post_text)
        client.send_post(f"Bullpen: {bp_names}\n\nBench: {bench_names}", reply_to={'root': {'cid': root.cid, 'uri': root.uri}, 'parent': {'cid': root.cid, 'uri': root.uri}})
        print(f"Posted Game #{game_num} successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        traceback.print_exc()
        raise

if __name__ == "__main__":
    post_to_bluesky()
