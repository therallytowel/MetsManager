import pandas as pd
import os
import random
from atproto import Client
import re

def get_clean_name(name, all_names_list):
    """Fixes encoding and applies Smart Name logic."""
    name_str = str(name)
    replacements = {
        'Ã¡': 'á', 'Ã©': 'é', 'Ã­': 'í', 'Ã³': 'ó', 'Ãº': 'ú',
        'Ã±': 'ñ', 'Ã': 'Á', 'Ã‰': 'É', 'Ã': 'Í', 'Ã“': 'Ó',
        'Ãš': 'Ú', 'Ã‘': 'Ñ'
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

        def map_df(df, is_pitcher=False):
            cols = list(df.columns)
            name_col = next((c for c in cols if 'NAME' in c or 'PLAYER' in c), cols[1])
            pos_col = next((c for c in cols if 'POS' in c or 'SUMMARY' in c), cols[-1])
            if is_pitcher:
                g_col = next((c for c in cols if c == 'G'), cols[-3])
                gs_col = next((c for c in cols if c == 'GS'), cols[-2])
                return df.rename(columns={name_col: 'NAME', pos_col: 'POS_SEARCH', g_col: 'G_COL', gs_col: 'GS_COL'})
            else:
                ops_col = next((c for c in cols if 'OPS' in c or 'OBP' in c), cols[-2])
                return df.rename(columns={name_col: 'NAME', pos_col: 'POS_SEARCH', ops_col: 'OPS'})

        batters = map_df(batters, is_pitcher=False)
        pitchers = map_df(pitchers, is_pitcher=True)
        master_names = pd.concat([batters['NAME'], pitchers['NAME']]).tolist()
        
    except Exception as e:
        print(f"❌ Mapping Error: {e}")
        return

    # 1. Pitcher Selection & The 'No-Fly Zone' for Hitters
    all_p = pitchers[pitchers['POS_SEARCH'].astype(str).str.contains('1', na=False)].copy()
    all_p['G_NUM'] = pd.to_numeric(all_p['G_COL'], errors='coerce').fillna(0)
    all_p['GS_NUM'] = pd.to_numeric(all_p['GS_COL'], errors='coerce').fillna(0)
    
    # This set identifies anyone who is primarily a pitcher
    pitcher_names_set = set(all_p['NAME'].unique())

    starter_pool = all_p[all_p['GS_NUM'] > 0]
    reliever_pool = all_p[all_p['G_NUM'] > all_p['GS_NUM']]
    if reliever_pool.empty: reliever_pool = all_p[all_p['GS_NUM'] == 0]

    sp_row = starter_pool.sample(1).iloc[0]
    final_rp_pool = reliever_pool[reliever_pool['NAME'] != sp_row['NAME']]
    rp_rows = final_rp_pool.sample(min(4, len(final_rp_pool)))

    # 2. Hitter Pool (Exclude ANYONE in the Pitcher File)
    # This ensures both the lineup AND the bench are strictly position players
    h_pool = batters[
        (batters['POS_SEARCH'].astype(str).str.contains(r'[2-9]', na=False)) & 
        (~batters['NAME'].isin(pitcher_names_set))
    ]
    
    slots = [('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), ('7|O', 'LF'), ('8|O', 'CF'), ('9|O', 'RF')]
    final_roster = []
    used_names = set()

    for code, label in slots:
        mask = h_pool['POS_SEARCH'].astype(str).str.contains(code, na=False)
        pool = h_pool[mask & ~h_pool['NAME'].isin(used_names)]
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used_names.add(sel['NAME'])
            try: val = float(sel['OPS'])
            except: val = 0.0
            final_roster.append({'Name': sel['NAME'], 'Pos': label, 'Val': val})

    dh_pool = h_pool[~h_pool['NAME'].isin(used_names)]
    if not dh_pool.empty:
        dh_sel = dh_pool.sample(1).iloc[0]
        used_names.add(dh_sel['NAME'])
        try: v_dh = float(dh_sel['OPS'])
        except: v_dh = 0.0
        final_roster.append({'Name': dh_sel['NAME'], 'Pos': 'DH', 'Val': v_dh})

    # 3. Bench Selection (5 hitters NOT in the lineup and NOT pitchers)
    bench_pool = h_pool[~h_pool['NAME'].isin(used_names)]
    bench_rows = bench_pool.sample(min(5, len(bench_pool)))
    bench_names = [get_clean_name(n['NAME'], master_names) for _, n in bench_rows.iterrows()]

    # Formatting
    order = sorted(final_roster, key=lambda x: x['Val'], reverse=True)
    l_rows = [f"{i+1} {get_clean_name(p['Name'], master_names)} {p['Pos']}" for i, p in enumerate(order)]
    mgr = random.choice(['Hodges', 'Johnson', 'Valentine', 'Berra', 'Collins', 'Mendoza'])
    bp_names = [get_clean_name(n['NAME'], master_names) for _, n in rp_rows.iterrows()]

    status_body = (
        f"Game #{current_game}\nMgr: {mgr}\n\n"
        + "\n".join(l_rows) + 
        f"\n\nP: {get_clean_name(sp_row['NAME'], master_names)}\n"
        f"Bullpen: " + ", ".join(bp_names)
    )

    if len(status_body) > 300:
        status_body = status_body[:297] + "..."

    bench_body = f"Bench: {', '.join(bench_names)}"

    print("--- POST PREVIEW ---")
    print(status_body)
    print(f"THREAD: {bench_body}")
    print("--------------------")

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        
        # Post Lineup
        root_post = client.send_post(status_body)
        
        # Post Bench Thread
        client.send_post(
            text=bench_body,
            reply_to={'root': root_post, 'parent': root_post}
        )
        
        with open(game_file, "w") as f: f.write(str(current_game + 1))
        print(f"✅ Posted Successfully.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    post_lineup()
