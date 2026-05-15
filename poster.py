import pandas as pd
import random
from atproto import Client
import os
import unicodedata
from datetime import datetime, date
import pytz

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

def nuclear_clean(text):
    if isinstance(text, str):
        try: text = text.encode('cp1252').decode('utf-8')
        except: pass
        return unicodedata.normalize('NFC', text)
    return text

def calculate_amazin_index(lineup, starter_row, bp_rows, mgr_name):
    # 1. Hitting Score (Based on OPS)
    avg_ops = sum([p.get('OPS', 0.720) for p in lineup]) / 9
    hitting_score = (avg_ops - 0.450) * 160 # Maps .750 OPS to ~48 pts
    
    # 2. Pitching Score (Based on ERA+)
    s_era = starter_row.get('ERA+', 100)
    bp_era = sum([p.get('ERA+', 100) for p in bp_rows]) / len(bp_rows)
    pitching_score = (s_era * 0.25) + (bp_era * 0.15) # Weights ERA+ into a 40pt scale
    
    # 3. Legacy/Star Power (Based on All-Star Games)
    total_asg = sum([p.get('ASG', 0) for p in lineup]) + starter_row.get('ASG', 0)
    legacy_boost = min(total_asg * 1.2, 20)
    
    final_score = hitting_score + pitching_score + legacy_boost
    return round(max(15, min(final_score, 100)))

def get_status_label(score):
    if score >= 88: return "World Series Favorites 🏆"
    if score >= 78: return "The 1986 Vibes 🍏"
    if score >= 68: return "Solid Wild Card Contender ⚾️"
    if score >= 55: return "The '73 Ya Gotta Believe Era 🏗️"
    return "Panic Citi 😱"

def generate_lineup():
    pos_df = pd.read_csv('Mets_Positional_History - Mets_Positional_History.csv', encoding='utf-8-sig')
    bat_df = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
    pitchers_df = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
    
    for df in [pos_df, bat_df, pitchers_df]:
        df.columns = [c.strip() for c in df.columns]
        name_col = 'Player' if 'Player' in df.columns else 'Name'
        df[name_col] = df[name_col].apply(nuclear_clean)

    field_pos_cols = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF']
    pos_df[field_pos_cols] = pos_df[field_pos_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
    pos_master = pos_df.groupby('Player')[field_pos_cols].sum().reset_index()
    pos_master['EligiblePositions'] = pos_master.apply(lambda r: [p for p in field_pos_cols if r[p] > 0], axis=1)

    bat_df = bat_df.rename(columns={'Name': 'Player'})
    master_batters = pd.merge(pos_master, bat_df, on='Player', how='inner')

    # Pitching Role Logic
    pitchers_df['GS'] = pd.to_numeric(pitchers_df['GS'], errors='coerce').fillna(0)
    p_stats = pitchers_df.groupby('Name').agg({'GS': 'sum', 'Name': 'count', 'ERA+': 'mean', 'ASG': 'max'}).rename(columns={'Name': 'Apps'}).reset_index()
    
    pitcher_names = p_stats['Name'].tolist()
    clean_batters = master_batters[~master_batters['Player'].isin(pitcher_names)]
    
    all_sampled = clean_batters.sample(14).to_dict('records')
    lineup_pool = all_sampled[:9]
    bench = all_sampled[9:]

    defense_map = solve_defense(lineup_pool, ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH'])
    if not defense_map: return generate_lineup()

    # Pitcher Selection
    valid_starters = p_stats[p_stats['GS'] > 0]
    starter_row = valid_starters.sample(1).iloc[0]
    
    valid_rp = p_stats[p_stats['Name'] != starter_row['Name']]
    bp_rows = valid_rp.sample(4)

    managers = ["Gil Hodges", "Davey Johnson", "Bobby Valentine", "Terry Collins", "Buck Showalter", "Carlos Mendoza", "Casey Stengel", "Yogi Berra", "George Bamberger", "Art Howe"]
    mgr = random.choice(managers)

    # Calculate Index
    index_score = calculate_amazin_index(lineup_pool, starter_row, bp_rows.to_dict('records'), mgr)
    
    return lineup_pool, defense_map, starter_row, bp_rows, bench, mgr, index_score

def post_to_bluesky():
    lineup, defense, starter, bp_rows, bench, mgr, score = generate_lineup()
    
    # Date Logic (Stamford Time)
    et = pytz.timezone('America/New_York')
    game_number = (datetime.now(et).date() - date(2026, 5, 14)).days + 1
    status = get_status_label(score)

    post_text = f"Game #{game_number}\n"
    post_text += f"Amazin' Index: {score}/100 ({status})\n"
    post_text += f"Mgr: {mgr}\n\n"
    
    for i, p in enumerate(lineup):
        name = p['Player']
        post_text += f"{i+1} {name} {defense[name]}\n"
    post_text += f"\nP: {starter['Name']}"

    reply_text = f"Bullpen: {', '.join(bp_rows['Name'])}\n\nBench: {', '.join([b['Player'] for b in bench])}"

    client = Client()
    client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
    root = client.send_post(post_text)
    client.send_post(reply_text, reply_to={'root': {'cid': root.cid, 'uri': root.uri}, 'parent': {'cid': root.cid, 'uri': root.uri}})

if __name__ == "__main__":
    post_to_bluesky()
