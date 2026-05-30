import pandas as pd
import random
from atproto import Client
import os
import unicodedata
from datetime import datetime, date
import pytz
import httpx

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

def get_status_label(score):
    if score >= 88: return "World Series Favorites 🏆"
    elif score >= 78: return "The 1986 Vibes 🍏"
    elif score >= 68: return "Solid Wild Card Contender ⚾️"
    elif score >= 55: return "The '73 Ya Gotta Believe Era 🏗️"
    else: return "Panic Citi 😱"

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
    
    if today == date(2026, 5, 30):
        hof_players = ["Bud Harrelson", "Rusty Staub", "Tom Seaver", "Jerry Koosman", "Ed Kranepool", "Cleon Jones", "Jerry Grote", "Tug McGraw", "Mookie Wilson", "Keith Hernandez", "Gary Carter", "Tommie Agee", "Dwight Gooden", "Darryl Strawberry", "John Franco", "Mike Piazza", "Jon Matlack", "Ron Darling", "Edgardo Alfonzo", "Howard Johnson", "Al Leiter", "David Wright", "Lee Mazzilli", "Kevin McReynolds"]
        
        hof_batters_df = master_batters[master_batters['Player'].isin(hof_players)].copy()
        hof_pitchers_df = p_stats[p_stats['Name'].isin(hof_players)].copy()
        
        mazzilli_row = hof_batters_df[hof_batters_df['Player'] == "Lee Mazzilli"].to_dict('records')[0]
        other_hof_batters = hof_batters_df[hof_batters_df['Player'] != "Lee Mazzilli"]
        sampled_batters = other_hof_batters.sample(13).to_dict('records')
        
        lineup_pool = [mazzilli_row] + sampled_batters[:8]
        bench = sampled_batters[8:]
        
        defense_map = solve_defense([p for p in lineup_pool if p['Player'] != "Lee Mazzilli"], ['C', '1B', '2B', '3B', 'SS', 'LF', 'RF', 'DH'])
        defense_map["Lee Mazzilli"] = "CF"
        
        starter_row = hof_pitchers_df[hof_pitchers_df['GS'] > 0].sample(1).iloc[0]
        bp_rows = hof_pitchers_df[hof_pitchers_df['Name'] != starter_row['Name']].sample(4)
        
        mgr = "Bobby Valentine (In Disguise) 🥸"
        score = calculate_amazin_index(lineup_pool, starter_row, bp_rows.to_dict('records'), mgr)
        return lineup_pool, defense_map, starter_row, bp_rows, bench, mgr, score
    
    # ... (Rest of your standard logic remains here) ...
    return lineup_pool, defense_map, starter_row, bp_rows, bench, mgr, score

def post_to_bluesky():
    try:
        lineup, defense, starter, bp_rows, bench, mgr, score = generate_lineup()
        et = pytz.timezone('America/New_York')
        game_num = (datetime.now(et).date() - date(2026, 5, 15)).days + 1
        
        post_text = f"Game #{game_num}\nAmazin' Index: {score}/100\nMgr: {mgr}\n\n"
        
        for i, p in enumerate(lineup):
            name = p['Player']
            # Forgiving lookup: finds match even if case is slightly off
            pos = defense.get(name) or next((v for k, v in defense.items() if k.lower() == name.lower()), "N/A")
            post_text += f"{i+1} {name} {pos}\n"
        post_text += f"\nP: {starter['Name']}"

        client = Client(base_url='https://bsky.social')
        client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
        client.send_post(post_text)
        print(f"Successfully posted Game #{game_num}")
    except Exception as e:
        print(f"Post failed: {e}")

if __name__ == "__main__":
    post_to_bluesky()
