import pandas as pd
import os
import random
from atproto import Client, models
import re

def get_clean_name(name, all_names_list):
    """Clean encoding and apply Smart Name logic (F. Last if duplicate)."""
    if not isinstance(name, str): return str(name)
    replacements = {
        'ÃƒÂ­': 'í', 'ÃƒÂ±': 'ñ', 'ÃƒÂ³': 'ó', 'ÃƒÂ¡': 'á', 'ÃƒÂ©': 'é', 
        'ÃƒÂº': 'ú', 'Ã¡': 'á', 'Ã©': 'é', 'Ã­': 'í', 'Ã³': 'ó', 
        'Ãº': 'ú', 'Ã±': 'ñ', 'Ã‘': 'Ñ', 'Ã': 'Í', 'Ã': 'Á'
    }
    for bad, good in replacements.items():
        name = name.replace(bad, good)
    
    raw_clean = re.sub(r'[*#+?0-9]', '', name).replace('HOF', '').strip()
    parts = raw_clean.split()
    if not parts: return raw_clean
    last_name = parts[-1]
    
    all_lasts = [re.sub(r'[*#+?0-9]', '', str(n)).strip().split()[-1] for n in all_names_list if isinstance(n, str) and n.strip()]
    if all_lasts.count(last_name) > 1:
        return f"{parts[0][0]}. {last_name}"
    return last_name

def post_lineup():
    game_file = "game_number.txt"
    current_game = 1
    if os.path.exists(game_file):
        with open(game_file, "r") as f:
            try: current_game = int(f.read().strip())
            except: pass

    try:
        batters = pd.read_csv('mets_batters.csv', encoding='latin1')
        pitchers = pd.read_csv('mets_pitchers.csv', encoding='latin1')
        batters.columns = [str(c).upper().strip() for c in batters.columns]
        pitchers.columns = [str(c).upper().strip() for c in pitchers.columns]

        def map_df(df, is_pitcher=False):
            cols = list(df.columns)
            name_col = next((c for c in cols if 'NAME' in c or 'PLAYER' in c), cols[1])
            pos_col = next((c for c in cols if 'POS' in c or 'SUMMARY' in c), cols[-1])
            if is_pitcher:
                return df.rename(columns={name_col: 'NAME', pos_col: 'POS_SEARCH', 'G': 'G_COL', 'GS': 'GS_COL'})
            return df.rename(columns={name_col: 'NAME', pos_col: 'POS_SEARCH', 'OPS': 'OPS', 'OBP': 'OBP', 'G': 'G_COL'})

        batters = map_df(batters)
        pitchers = map_df(pitchers, is_pitcher=True)
        master_names = pd.concat([batters['NAME'], pitchers['NAME']]).tolist()
        pitcher_names_set = set(pitchers['NAME'].unique())
        
    except Exception as e:
        print(f"❌ Mapping Error: {e}"); return

    # 1. Pitcher Selection
    all_p = pitchers[pitchers['POS_SEARCH'].astype(str).str.contains('1', na=False)].copy()
    sp_row = all_p[pd.to_numeric(all_p['GS_COL'], errors='coerce') > 0].sample(1).iloc[0]
    rp_rows = all_p[all_p['NAME'] != sp_row['NAME']].sample(min(4, len(all_p)-1))

    # 2. Hitter Selection (Career-Based Position Eligibility)
    h_pool = batters[~batters['NAME'].isin(pitcher_names_set)].copy()
    
    # Map for career checks: 2=C, 3=1B, 4=2B, 5=3B, 6=SS, 7=LF, 8=CF, 9=RF
    # Note: 'O' in PosSummary usually denotes general Outfield
    slots = [('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), ('7|O', 'LF'), ('8|O', 'CF'), ('9|O', 'RF')]
    starters = []
    used_names = set()

    for code, label in slots:
        # Check if the player has EVER played this position code in their career
        mask = h_pool['POS_SEARCH'].astype(str).str.contains(code, na=False)
        pool = h_pool[mask & (~h_pool['NAME'].isin(used_names))]
        
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used_names.add(sel['NAME'])
            starters.append({
                'Name': sel['NAME'], 
                'Pos': label, 
                'OPS': float(sel['OPS']), 
                'OBP': float(sel['OBP']), 
                'G': float(sel['G_COL'])
            })

    # DH (Can be any remaining hitter)
    dh_pool = h_pool[~h_pool['NAME'].isin(used_names)]
    if not dh_pool.empty:
        sel = dh_pool.sample(1).iloc[0]
        used_names.add(sel['NAME'])
        starters.append({'Name': sel['NAME'], 'Pos': 'DH', 'OPS': float(sel['OPS']), 'OBP': float(sel['OBP']), 'G': float(sel['G_COL'])})

    # 3. Manager Brain Sorting (OBP for 1-2, OPS for 3-5)
    l_pool = sorted(starters, key=lambda x: (x['OBP'] * 0.7 + (x['G']/162) * 0.3), reverse=True)
    c_pool = sorted(starters, key=lambda x: x['OPS'], reverse=True)
    final_order = [None] * 9
    assigned = set()
    
    final_order[0] = l_pool[0]; assigned.add(l_pool[0]['Name'])
    for s in l_pool[1:]:
        if s['Name'] not in assigned: final_order[1] = s; assigned.add(s['Name']); break
    for spot in [2, 3, 4]:
        for s in c_pool:
            if s['Name'] not in assigned: final_order[spot] = s; assigned.add(s['Name']); break
    remaining = [s for s in starters if s['Name'] not in assigned]
    for i in range(9):
        if final_order[i] is None and remaining: final_order[i] = remaining.pop(0)

    l_rows = [f"{i+1} {get_clean_name(p['Name'], master_names)} {p['Pos']}" for i, p in enumerate(final_order)]

    # 4. Bench
    bench_names = [get_clean_name(n['NAME'], master_names) for _, n in h_pool[~h_pool['NAME'].isin(used_names)].sample(min(5, len(h_pool)-9)).iterrows()]

    # 5. Execute Post
    mgr = random.choice(['Hodges', 'Johnson', 'Valentine', 'Berra', 'Collins', 'Mendoza'])
    status_body = f"Game #{current_game}\nMgr: {mgr}\n\n" + "\n".join(l_rows) + f"\n\nP: {get_clean_name(sp_row['NAME'], master_names)}\nBullpen: " + ", ".join([get_clean_name(n['NAME'], master_names) for _, n in rp_rows.iterrows()])
    bench_body = f"Bench: {', '.join(bench_names)}"

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        main_p = client.
