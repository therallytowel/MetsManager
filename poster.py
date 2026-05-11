import pandas as pd
import os
import random
from atproto import Client, models
import re

def get_clean_name(name, all_names_list):
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
    all_p['GS_NUM'] = pd.to_numeric(all_p['GS_COL'], errors='coerce').fillna(0)
    sp_row = all_p[all_p['GS_NUM'] > 0].sample(1).iloc[0]
    rp_rows = all_p[all_p['NAME'] != sp_row['NAME']].sample(min(4, len(all_p)-1))

    # 2. Hitter Selection
    h_pool = batters[~batters['NAME'].isin(pitcher_names_set)].copy()
    h_pool['PRIMARY_POS'] = h_pool['POS_SEARCH'].astype(str).str[0]
    
    slots = [('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), ('7', 'LF'), ('8', 'CF'), ('9', 'RF')]
    starters = []
    used_names = set()

    for code, label in slots:
        pool = h_pool[(h_pool['PRIMARY_POS'] == code) & (~h_pool['NAME'].isin(used_names))]
        if pool.empty:
            pool = h_pool[(h_pool['POS_SEARCH'].str.contains(code)) & (~h_pool['NAME'].isin(used_names))]
        
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used_names.add(sel['NAME'])
            starters.append({
                'Name': sel['NAME'], 'Pos': label, 
                'OPS': pd.to_numeric(sel['OPS'], errors='coerce') or 0.0, 
                'OBP': pd.to_numeric(sel['OBP'], errors='coerce') or 0.0, 
                'G': pd.to_numeric(sel['G_COL'], errors='coerce') or 0.0
            })

    # Fill DH from anyone left
    dh_pool = h_pool[~h_pool['NAME'].isin(used_names)]
    if not dh_pool.empty:
        sel = dh_pool.sample(1).iloc[0]
        used_names.add(sel['NAME'])
        starters.append({
            'Name': sel['NAME'], 'Pos': 'DH', 
            'OPS': pd.to_numeric(sel['OPS'], errors='coerce') or 0.0, 
            'OBP': pd.to_numeric(sel['OBP'], errors='coerce') or 0.0, 
            'G': pd.to_numeric(sel['G_COL'], errors='coerce') or 0.0
        })

    # 3. Manager Brain Sorting
    l_pool = sorted(starters, key=lambda x: (x['OBP'] * 0.7 + (x['G']/162) * 0.3), reverse=True)
    c_pool = sorted(starters, key=lambda x: x['OPS'], reverse=True)
    
    # Initialize with actual Player objects instead of None to prevent subscript errors
    final_order = []
    assigned = set()
    
    # 1-2
    if l_pool:
        p1 = l_pool[0]; final_order.append(p1); assigned.add(p1['Name'])
    for s in l_pool[1:]:
        if s['Name'] not in assigned and len(final_order) < 2:
            final_order.append(s); assigned.add(s['Name'])

    # 3-4-5
    for s in c_pool:
        if s['Name'] not in assigned and len(final_order) < 5:
            final_order.append(s); assigned.add(s['Name'])

    # 6-9
    for s in starters:
        if s['Name'] not in assigned and len(final_order) < 9:
            final_order.append(s); assigned.add(s['Name'])

    # Safety check: Ensure we have exactly 9
    if len(final_order) < 9:
        print("⚠️ Lineup incomplete, skipping post."); return

    l_rows = [f"{i+1} {get_clean_name(p['Name'], master_names)} {p['Pos']}" for i, p in enumerate(final_order)]

    # 4. Bench
    bench_pool = h_pool[~h_pool['NAME'].isin(used_names)]
    bench_names = [get_clean_name(n['NAME'], master_names) for _, n in bench_pool.sample(min(5, len(bench_pool))).iterrows()]

    mgr = random.choice(['Hodges', 'Johnson', 'Valentine', 'Berra', 'Collins', 'Mendoza'])
    status_body = f"Game #{current_game}\nMgr: {mgr}\n\n" + "\n".join(l_rows) + f"\n\nP: {get_clean_name(sp_row['NAME'], master_names)}\nBullpen: " + ", ".join([get_clean_name(n['NAME'], master_names) for _, n in rp_rows.iterrows()])
    bench_body = f"Bench: {', '.join(bench_names)}"

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        main_p = client.send_post(status_body)
        root = models.ComAtprotoRepoStrongRef.Main(cid=main_p.cid, uri=main_p.uri)
        client.send_post(text=bench_body, reply_to=models.AppBskyFeedPost.ReplyRef(parent=root, root=root))
        with open(game_file, "w") as f: f.write(str(current_game + 1))
        print(f"✅ Success. Game #{current_game} is live.")
    except Exception as e: print(f"❌ Error: {e}")

if __name__ == "__main__":
    post_lineup()
