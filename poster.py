import pandas as pd
import random
from atproto import Client
import os
import unicodedata
from datetime import date

def solve_defense(players, required_positions):
    """Assigns players to valid defensive slots using Universal DH rules."""
    if not players:
        return {}
    current_player = players[0]
    remaining_players = players[1:]
    eligible_pos = [p for p in required_positions if p in current_player['EligiblePositions']]
    
    # Every player in this pool is DH eligible
    if 'DH' in required_positions:
        eligible_pos.append('DH')
    
    random.shuffle(eligible_pos)
    for pos in eligible_pos:
        result = solve_defense(remaining_players, [p for p in required_positions if p != pos])
        if result is not None:
            result[current_player['Player']] = pos
            return result
    return None

def nuclear_clean(text):
    """Enforces NFC normalization and fixes potential double-encoding for Bluesky."""
    if isinstance(text, str):
        try:
            # Attempt to fix existing mojibake if it exists in the CSV
            text = text.encode('cp1252').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        return unicodedata.normalize('NFC', text)
    return text

def generate_lineup():
    # Load data with utf-8-sig to handle Excel-exported CSV artifacts
    pos_df = pd.read_csv('Mets_Positional_History - Mets_Positional_History.csv', encoding='utf-8-sig')
    bat_df = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
    pitchers_df = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
    
    # Clean whitespace and normalize text across all dataframes
    for df in [pos_df, bat_df, pitchers_df]:
        df.columns = [c.strip() for c in df.columns]
        name_col = 'Player' if 'Player' in df.columns else 'Name'
        df[name_col] = df[name_col].apply(nuclear_clean)

    field_pos_cols = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF']

    # Position Player Processing
    pos_df = pos_df[pos_df['Player'].notna() & (pos_df['Player'].astype(str).str.lower() != 'player')]
    for p_col in field_pos_cols:
        if p_col in pos_df.columns:
            pos_df[p_col] = pd.to_numeric(pos_df[p_col], errors='coerce').fillna(0)
    
    pos_master = pos_df.groupby('Player').agg({p: 'sum' for p in field_pos_cols if p in pos_df.columns}).reset_index()
    def get_eligible_list(row):
        return [p for p in field_pos_cols if p in row and row[p] > 0]
    pos_master['EligiblePositions'] = pos_master.apply(get_eligible_list, axis=1)

    bat_df = bat_df.rename(columns={'Name': 'Player'})
    master_batters = pd.merge(pos_master, bat_df[['Player', 'OBP', 'OPS', 'SLG']], on='Player', how='inner')

    # Pitcher Role Logic: Starters, Bullpen, and Hybrids
    pitchers_df['GS'] = pd.to_numeric(pitchers_df['GS'], errors='coerce').fillna(0)
    p_stats = pitchers_df.groupby('Name').agg({'GS': 'sum', 'Name': 'count'}).rename(columns={'Name': 'Apps'}).reset_index()
    
    bp_only = p_stats[p_stats['GS'] == 0]['Name'].tolist()
    starters_only = p_stats[p_stats['GS'] == p_stats['Apps']]['Name'].tolist()
    hybrids = p_stats[(p_stats['GS'] > 0) & (p_stats['GS'] < p_stats['Apps'])]['Name'].tolist()

    # Role Firewall: Block anyone in the pitcher file from the hitting pool
    pitcher_names = p_stats['Name'].tolist()
    clean_batter_pool = master_batters[~master_batters['Player'].isin(pitcher_names)]

    # Draft 14 hitters (9 starters, 5 bench)
    all_sampled = clean_batter_pool.sample(14).to_dict('records')
    starters_list = all_sampled[:9]
    bench = all_sampled[9:]

    # Optimized Lineup Construction
    pool = sorted(starters_list, key=lambda x: x['OPS'], reverse=True)
    lineup = [None] * 9
    lineup[0] = max(pool, key=lambda x: x['OBP']); pool.remove(lineup[0])
    lineup[3] = max(pool, key=lambda x: x['SLG']); pool.remove(lineup[3])
    lineup[1] = max(pool, key=lambda x: x['OPS']); pool.remove(lineup[1])
    
    rem_slots = [2, 4, 5, 6, 7, 8]
    pool = sorted(pool, key=lambda x: x['OPS'], reverse=True)
    for i, slot in enumerate(rem_slots):
        lineup[slot] = pool[i]

    # Resolve Defense with Universal DH
    defense_map = solve_defense(lineup, ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH'])
    if not defense_map: return generate_lineup()

    # Pitching Selection
    batter_names = [p['Player'] for p in all_sampled]
    valid_starters = [n for n in (starters_only + hybrids) if n not in batter_names]
    starter_name = random.choice(valid_starters)
    
    valid_rp = [n for n in (bp_only + hybrids) if n not in batter_names and n != starter_name]
    bullpen_names = random.sample(valid_rp, 4)

    # Manager Selection
    managers = [nuclear_clean(m) for m in [
        "Casey Stengel", "Wes Westrum", "Gil Hodges", "Yogi Berra", "Roy McMillan", 
        "Joe Frazier", "Joe Torre", "George Bamberger", "Frank Howard", "Davey Johnson", 
        "Bud Harrelson", "Mike Cubbage", "Jeff Torborg", "Dallas Green", "Bobby Valentine", 
        "Art Howe", "Willie Randolph", "Jerry Manuel", "Terry Collins", "Mickey Callaway", 
        "Carlos Beltrán", "Luis Rojas", "Buck Showalter", "Carlos Mendoza"
    ]]
    mgr = random.choice(managers)

    return lineup, defense_map, starter_name, bullpen_names, bench, mgr

def post_to_bluesky():
    try:
        lineup, defense, starter, bullpen, bench, mgr = generate_lineup()
        
        # Game Counter Logic: May 14, 2026 is Game #1
        start_date = date(2026, 5, 14)
        game_number = (date.today() - start_date).days + 1

        # Format Main Post
        post_text = f"Game #{game_number}\nMgr: {mgr}\n\n"
        for i, p in enumerate(lineup):
            name = p['Player']
            post_text += f"{i+1} {name} {defense[name]}\n"
        post_text += f"\nP: {starter}"

        # Format Reply Post
        bp_text = ", ".join(bullpen)
        bench_text = ", ".join([b['Player'] for b in bench])
        reply_text = f"Bullpen: {bp_text}\n\nBench: {bench_text}"

        # Bluesky Authentication and Posting
        client = Client()
        client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
        
        root_post = client.send_post(post_text)
        parent_ref = {'cid': root_post.cid, 'uri': root_post.uri}
        client.send_post(reply_text, reply_to={'root': parent_ref, 'parent': parent_ref})
        
        print(f"Successfully posted Game #{game_number}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    post_to_bluesky()
