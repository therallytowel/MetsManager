import pandas as pd
import os
import random
from atproto import Client, models
import re

def get_clean_name(name, all_names_list):
    name_str = str(name)
    # The "Triple-Threat" Encoding Fix
    replacements = {
        'ÃƒÂ­': 'í', 'ÃƒÂ±': 'ñ', 'ÃƒÂ³': 'ó', 'ÃƒÂ¡': 'á', 'ÃƒÂ©': 'é', 
        'ÃƒÂº': 'ú', 'Ã¡': 'á', 'Ã©': 'é', 'Ã­': 'í', 'Ã³': 'ó', 
        'Ãº': 'ú', 'Ã±': 'ñ', 'Ã‘': 'Ñ', 'Ã': 'Í'
    }
    for bad, good in replacements.items():
        name_str = name_str.replace(bad, good)
    
    raw_clean = re.sub(r'[*#+?0-9]', '', name_str).replace('HOF', '').strip()
    parts = raw_clean.split()
    if not parts: return raw_clean
    
    last_name = parts[-1]
    first_initial = parts[0][0]

    all_lasts = [re.sub(r'[*#+?0-9]', '', str(n)).strip().split()[-1] for n in all_names_list if isinstance(n, str) and n.strip()]
    if all_lasts.count(last_name) > 1:
        return f"{first_initial}. {last_name}"
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

        # Map core columns
        def map_df(df, is_pitcher=False):
            cols = list(df.columns)
            name_col = next((c for c in cols if 'NAME' in c or 'PLAYER' in c), cols[1])
            pos_col = next((c for c in cols if 'POS' in c or 'SUMMARY' in c), cols[-1])
            if is_pitcher:
                g_col = next((c for c in cols if c == 'G'), cols[-3])
                gs_col = next((c for c in cols if c == 'GS'), cols[-2])
                return df.rename(columns={name_col: 'NAME', pos_col: 'POS_SEARCH', g_col: 'G_COL', gs_col: 'GS_COL'})
            else:
                ops_col = next((c for c in cols if 'OPS' in c), cols[-2])
                obp_col = next((c for c in cols if 'OBP' in c), cols[-3])
                g_col = next((c for c in cols if c == 'G'), cols[4]) # Reliability
                return df.rename(columns={name_col: 'NAME', pos_col: 'POS_SEARCH', ops_col: 'OPS', obp_col: 'OBP', g_col: 'G_COL'})

        batters = map_df(batters, is_pitcher=False)
        pitchers = map_df(pitchers, is_pitcher=True)
        master_names = pd.concat([batters['NAME'], pitchers['NAME']]).tolist()
        
    except Exception as e:
        print(f"❌ Mapping Error: {e}")
        return

    # 1. Pitcher Selection (Strict No-Hitter Rule)
    all_p = pitchers[pitchers['POS_SEARCH'].astype(str).str.contains('1', na=False)].copy()
    all_p['G_NUM'] = pd.to_numeric(all_p['G_COL'], errors='coerce').fillna(0)
    all_p['GS_NUM'] = pd.to_numeric(all_p['GS_COL'], errors='coerce').fillna(0)
    pitcher_names_set = set(all_p['NAME'].unique())

    sp_row = all_p[all_p['GS_NUM'] > 0].sample(1).iloc[0]
    reliever_pool = all_p[(all_p['G_NUM'] > all_p['GS_NUM']) & (all_p['NAME'] != sp_row['NAME'])]
    if reliever_pool.empty: reliever_pool = all_p[all_p['GS_NUM'] == 0]
    rp_rows = reliever_pool.sample(min(4, len(reliever_pool)))

    # 2. Selecting Starters
    h_pool = batters[(batters['POS_SEARCH'].astype(str).str.contains(r'[2-9]', na=False)) & (~batters['NAME'].isin(pitcher_names_set))]
    
    slots = [('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), ('7|O', 'LF'), ('8|O', 'CF'), ('9|O', 'RF')]
    starters = []
    used_names = set()

    for code, label in slots:
        mask = h_pool['POS_SEARCH'].astype(str).str.contains(code, na=False)
        pool = h_pool[mask & ~h_pool['NAME'].isin(used_names)]
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used_names.add(sel['NAME'])
            starters.append({'Name': sel['NAME'], 'Pos': label, 'OPS': float(sel['OPS']), 'OBP': float(sel['OBP']), 'G': float(sel['G_COL'])})

    dh_pool = h_pool[~h_pool['NAME'].isin(used_names)]
    if not dh_pool.empty:
        dh_sel = dh_pool.sample(1).iloc[0]
        used_names.add(dh_sel['NAME'])
        starters.append({'Name': dh_sel['NAME'], 'Pos': 'DH', 'OPS': float(dh_sel['OPS']), 'OBP': float(dh_sel['OBP']), 'G': float(dh_sel['G_COL'])})

    # 3. MANAGER BRAIN BATTING ORDER
    # Sort for various roles
    leadoff_pool = sorted(starters, key=lambda x: (x['OBP'] * 0.7 + (x['G']/162) * 0.3), reverse=True)
    cleanup_pool = sorted(starters, key=lambda x: x['OPS'], reverse=True)
    
    final_order = [None] * 9
    assigned = set()

    # Leadoff & #2 (OBP Kings)
    final_order[0] = leadoff_pool[0]; assigned.add(leadoff_pool[0]['Name'])
    for s in leadoff_pool[1:]:
        if s['Name'] not in assigned:
            final_order[1] = s; assigned.add(s['Name']); break

    # #3, #4, #5 (The Power)
    power_spots = [2, 3, 4]
    for spot in power_spots:
        for s in cleanup_pool:
            if s['Name'] not in assigned:
                final_order[spot] = s; assigned.add(s['Name']); break

    # #6-#9 (The Rest)
    remaining = [s for s in starters if s['Name'] not in assigned]
    for i in range(9):
        if final_order[i] is None:
            if remaining:
                pick = remaining.pop(0)
                final_order[i] = pick

    l_rows = [f"{i+1} {get_clean_name(p['Name'], master_names)} {p['Pos']}" for i, p in enumerate(final_order)]

    # 4. Bench
    bench_pool = h_pool[~h_pool['NAME'].isin(used_names)]
    bench_names = [get_clean_name(n['NAME'], master_names) for _, n in bench_pool.sample(min(5, len(bench_pool))).iterrows()]

    # Post Prep
    mgr = random.choice(['Hodges', 'Johnson', 'Valentine', 'Berra', 'Collins', 'Mendoza'])
    status_body = f"Game #{current_game}\nMgr: {mgr}\n\n" + "\n".join(l_rows) + f"\n\nP: {get_clean_name(sp_row['NAME'], master_names)}\nBullpen: " + ", ".join([get_clean_name(n['NAME'], master_names) for _, n in rp_rows.iterrows()])
    if len(status_body) > 300: status_body = status_body[:297] + "..."
    bench_body = f"Bench: {', '.join(bench_names)}"

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        main_p = client.send_post(status_body)
        root = models.ComAtprotoRepoStrongRef.Main(cid=main_p.cid, uri=main_p.uri)
        client.send_post(text=bench_body, reply_to=models.AppBskyFeedPost.ReplyRef(parent=root, root=root))
        with open(game_file, "w") as f: f.write(str(current_game + 1))
        print(f"✅ Posted Successfully.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    post_lineup()
