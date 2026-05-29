import pandas as pd
import random
from atproto import Client
import os
import unicodedata
from datetime import datetime, date
import pytz
import httpx  # Overhauls the network engine to bypass TLS fingerprint firewalls

def solve_defense(players, required_positions):
    """
    The Position Assignor: 
    Finds a valid defensive configuration based on historical records.
    """
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
    """
    The Amazin' Index Calculation (Calibrated):
    - Hitting (40 pts max): Scaled linearly between .600 OPS (0 pts) and .850 OPS (40 pts).
    - Pitching (40 pts max): Scaled so 100 ERA+ is 20 pts, 150 ERA+ is 40 pts.
    - Legacy (10 pts max): 0.5 pts per All-Star appearance, capped at 10.
    Maximum theoretical score = 90 + 10 = 100.
    """
    # 1. Hitting (Cap at 40 points)
    avg_ops = sum([float(p.get('OPS', 0.720)) for p in lineup]) / 9
    hitting_score = (avg_ops - 0.600) * 160
    hitting_score = max(0, min(hitting_score, 40)) 
    
    # 2. Pitching (Cap at 40 points)
    s_era = float(starter_row.get('ERA+', 100))
    bp_era = sum([float(p.get('ERA+', 100)) for p in bp_rows]) / len(bp_rows)
    
    pitching_score = ((s_era - 100) * 0.4) + ((bp_era - 100) * 0.2) + 20
    pitching_score = max(0, min(pitching_score, 40)) 
    
    # 3. Legacy (The Superstar Clause - Cap at 10 points)
    total_asg = sum([int(p.get('ASG', 0)) for p in lineup]) + int(starter_row.get('ASG', 0))
    legacy_boost = min(total_asg * 0.5, 10) 
    
    final_score = hitting_score + pitching_score + legacy_boost + 10
    return round(max(15, min(final_score, 100)))

def get_status_label(score):
    """Maps the numeric score to our historical Mets tiers."""
    if score >= 88:
        return "World Series Favorites 🏆"
    elif score >= 78:
        return "The 1986 Vibes 🍏"
    elif score >= 68:
        return "Solid Wild Card Contender ⚾️"
    elif score >= 55:
        return "The '73 Ya Gotta Believe Era 🏗️"
    else:
        return "Panic Citi 😱"

def generate_lineup():
    # Load Data from Baseball-Reference Source Files
    pos_df = pd.read_csv('Mets_Positional_History - Mets_Positional_History.csv', encoding='utf-8-sig')
    bat_df = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
    pitchers_df = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
    
    # FIX: Clean up encoding artifacts (like JosÃ©) across all raw text streams
    for df, col_name in [(pos_df, 'Player'), (bat_df, 'Name'), (pitchers_df, 'Name')]:
        if col_name in df.columns:
            df[col_name] = df[col_name].apply(
                lambda x: unicodedata.normalize('NFKC', str(x).encode('latin1', errors='ignore').decode('utf-8', errors='ignore'))
                if any(err in str(x) for err in ['Ã', '©', '¶', '®']) else str(x)
            )
    
    # Position Mapping
    field_pos_cols = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF']
    for p_col in field_pos_cols:
        pos_df[p_col] = pd.to_numeric(pos_df[p_col], errors='coerce').fillna(0)
    
    pos_master = pos_df.groupby('Player')[field_pos_cols].sum().reset_index()
    pos_master['EligiblePositions'] = pos_master.apply(lambda r: [p for p in field_pos_cols if r[p] > 0], axis=1)

    # Process Batter Stats
    bat_df = bat_df.rename(columns={'Name': 'Player'})
    master_batters = pd.merge(pos_master, bat_df, on='Player', how='inner')
    
    # Process Pitcher Stats
    pitchers_df['GS'] = pd.to_numeric(pitchers_df['GS'], errors='coerce').fillna(0)
    pitchers_df['ERA+'] = pd.to_numeric(pitchers_df['ERA+'].str.replace(r'[^\d.]', '', regex=True) if pitchers_df['ERA+'].dtype == 'object' else pitchers_df['ERA+'], errors='coerce').fillna(100)
    pitchers_df['ASG'] = pd.to_numeric(pitchers_df['ASG'], errors='coerce').fillna(0)
    
    p_stats = pitchers_df.groupby('Name').agg({
        'GS': 'sum', 
        'Name': 'count', 
        'ERA+': 'mean', 
        'ASG': 'max'
    }).rename(columns={'Name': 'Apps'}).reset_index()
    
    # Ensure Pitchers aren't drafted as Batters
    pitcher_names = p_stats['Name'].tolist()
    clean_batters = master_batters[~master_batters['Player'].isin(pitcher_names)]
    
    # Randomized Drafting
    all_sampled = clean_batters.sample(14).to_dict('records')
    lineup_pool = all_sampled[:9]
    bench = all_sampled[9:]

    defense_map = solve_defense(lineup_pool, ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH'])
    if not defense_map: return generate_lineup()

    # Staff Selection
    valid_starters = p_stats
