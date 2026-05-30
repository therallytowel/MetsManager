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
    if 'DH' in required_positions:
        eligible_pos.append('DH')
    random.shuffle(eligible_pos)
    for pos in eligible_pos:
        result = solve_defense(remaining_players, [p for p in required_positions if p != pos])
        if result is not None:
            result[current_player['Player']] = pos
            return result
    return None

def calculate_amazin_index(lineup, starter_row, bp_rows, mgr_name):
    avg_ops = sum([float(p.get('OPS', 0.720)) for p in lineup]) / 9
    hitting_score = (avg_ops - 0.600) * 160
    hitting_score = max(0, min(hitting_score, 40)) 
    s_era = float(starter_row.get('ERA+', 100))
    bp_era = sum([float(p.get('ERA+', 100)) for p in bp_rows]) / len(bp_rows)
    pitching_score = ((s_era - 100) * 0.4) + ((bp_era - 100) * 0.2) + 20
    pitching_score = max(0, min(pitching_score, 40)) 
    total_asg = sum([int(p.get('ASG', 0)) for p in lineup]) + int(starter_row.get('ASG', 0))
    legacy_boost = min(total_asg * 0.5, 10) 
    final_score = hitting_score + pitching_score + legacy_boost + 10
    return round(max(15, min(final_score, 100)))

def generate_lineup():
    pos_df = pd.read_csv('Mets_Positional_History - Mets_Positional_History.csv', encoding='utf-8-sig')
    bat_df = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
    pitchers_df = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
    
    for df, col_name in [(pos_df, 'Player'), (bat_df, 'Name'), (pitchers_df, 'Name')]:
        if col_name in df.columns:
            df[col_name] = df[col_name].apply(lambda x: unicodedata.normalize('NFKC', str(x)))
    
    field_pos_cols = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF']
    for p_col in field_pos_cols:
        pos_df[p_col] = pd.to_numeric(pos_df[p_col], errors='coerce').fillna(0)
    
    pos_master = pos_df.groupby('Player')[field_pos_cols].sum().reset_index()
    pos_master['EligiblePositions'] = pos_master.apply(lambda r: [p for p in field_pos_cols if r[p] > 0], axis=1)

    bat_df = bat_df.rename(columns={'Name': 'Player'})
    master_batters = pd.merge(pos_master, bat_df, on='Player', how='inner')
    
    pitchers_df['GS'] = pd.to_numeric(pitchers_df['GS'], errors='coerce').fillna(0)
    pitchers_df['ERA+'] = pd.to_numeric(pitchers_df['ERA+'].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(100)
    pitchers_df['ASG'] = pd.to_numeric(pitchers_df['ASG'], errors='coerce').fillna(0)
    p_stats = pitchers_df.groupby('Name').agg({'GS': 'sum', 'G': 'sum', 'ERA+': 'mean', 'ASG': 'max'}).reset_index()
    
    et = pytz.timezone('America/New_York')
    today = datetime.now(et).date()
    
    # --- SPECIAL HOF OVERRIDE BLOCK ---
    if today == date(2026, 5, 30):
        lineup_dict = {
            "Lee Mazzilli": "CF", "Gary Carter": "C", "Keith Hernandez": "1B", 
            "Edgardo Alfonzo": "2B", "David Wright": "3B", "Bud Harrelson": "SS",
            "Cleon Jones": "LF", "Darryl Strawberry": "RF", "Rusty Staub": "DH"
        }
        bench_names = ["Mookie Wilson", "Ed Kranepool", "Howard Johnson", "Kevin McReynolds"]
        starter_name = "Tom Seaver"
        bp_names = ["Jerry Koosman", "Tug McGraw", "John Franco", "Dwight Gooden"]
        
        lineup_pool = []
        for name in lineup_dict.keys():
            row = master_batters[master_batters['Player'] == name].iloc[0].to_dict()
            lineup_pool.append(row)
            
        starter_row = p_stats[p_stats['Name'] == starter_name].iloc[0]
        bp_rows = [p_stats[p_stats['Name'] == name].iloc[0].to_dict() for name in bp_names]
        
        mgr = "Bobby Valentine (In Disguise) 🥸"
        score = calculate_amazin_index(lineup_pool, starter_row, bp_rows, mgr)
        return lineup_pool, lineup_dict, starter_row, bp_rows, bench_names, mgr, score

    # --- REGULAR SCRIPT ---
    clean_batters = master_batters[~master_batters['Player'].isin(p_stats['Name'])]
    all_sampled = clean_batters.sample(15).to_dict('records')
    lineup_pool = all_sampled[:9]
    defense_map = solve_defense(lineup_pool, ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH'])
    starter = p_stats[p_stats['GS'] > 0].sample(1).iloc[0]
    bp = p_stats[p_stats['Name'] != starter['Name']].sample(4)
    return lineup_pool, defense_map, starter, bp, all_sampled[9:], "Terry Collins", calculate_amazin_index(lineup_pool, starter, bp.to_dict('records'), "Terry")

def post_to_bluesky():
    try:
        lineup, defense, starter, bp_rows, bench, mgr, score = generate_lineup()
        game_num = (datetime.now(pytz.timezone('America/New_York')).date() - date(2026, 5, 15)).days + 1
        
        post_text = f"Game #{game_num}\nAmazin' Index: {score}/100\nMgr: {mgr}\n\n"
        for i, p in enumerate(lineup):
            name = p['Player']
            pos = defense[name] if isinstance(defense, dict) else (defense.get(name) or "N/A")
            post_text += f"{i+1} {name} {pos}\n"
        post_text += f"\nP: {starter['Name']}"

        bp_list = bp_rows.to_dict('records') if isinstance(bp_rows, pd.DataFrame) else bp_rows
        bp_names = ", ".join([p['Name'] for p in bp_list])
        bench_names = ", ".join(bench) if isinstance(bench, list) else ", ".join([b['Player'] for b in bench])
        
        reply_text = f"Bullpen: {bp_names}\n\nBench: {bench_names}"

        client = Client(base_url='https://bsky.social')
        client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
        
        root = client.send_post(post_text)
        parent_ref = {'cid': root.cid, 'uri': root.uri}
        client.send_post(reply_text, reply_to={'root': parent_ref, 'parent': parent_ref})
        print(f"Posted Game #{game_num} successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        traceback.print_exc()
        raise

if __name__ == "__main__":
    post_to_bluesky()
