import pandas as pd
import os
import random
from atproto import Client
import re

def get_clean_name(name, all_names_list):
    # Fix the encoding symbols (Ã¡ -> á)
    try:
        if isinstance(name, str) and 'Ã' in name:
            name = name.encode('latin1').decode('utf-8')
    except:
        pass
    
    raw_clean = re.sub(r'[*#+?0-9]', '', str(name)).replace('HOF', '').strip()
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
        # Load with latin1 to catch those raw B-Ref characters
        batters = pd.read_csv('mets_batters.csv', encoding='latin1')
        pitchers = pd.read_csv('mets_pitchers.csv', encoding='latin1')
        
        # Clean headers
        batters.columns = [str(c).upper().strip() for c in batters.columns]
        pitchers.columns = [str(c).upper().strip() for c in pitchers.columns]

        # 🕵️‍♂️ HYBRID COLUMN LOCATOR
        def map_df(df, is_pitcher=False):
            cols = list(df.columns)
            # Find Name (usually index 1)
            name_col = next((c for c in cols if 'NAME' in c or 'PLAYER' in c), cols[1])
            # Find Pos (usually the very last column)
            pos_col = next((c for c in cols if 'POS' in c or 'SUMMARY' in c), cols[-1])
            
            if is_pitcher:
                # G is usually -3, GS is usually -2
                g_col = next((c for c in cols if c == 'G'), cols[-3])
                gs_col = next((c for c in cols if c == 'GS'), cols[-2])
                return df.rename(columns={name_col: 'NAME', pos_col: 'POS_SEARCH', g_col: 'G_COL', gs_col: 'GS_COL'})
            else:
                # OPS is usually -2
                ops_col = next((c for c in cols if 'OPS' in c), cols[-2])
                return df.rename(columns={name_col: 'NAME', pos_col: 'POS_SEARCH', ops_col: 'OPS'})

        batters = map_df(batters, is_pitcher=False)
        pitchers = map_df(pitchers, is_pitcher=True)

        master_names = pd.concat([batters['NAME'], pitchers['NAME']]).tolist()
        batters['POS_SEARCH'] = batters['POS_SEARCH'].astype(str).str.upper()
        pitchers['POS_SEARCH'] = pitchers['POS_SEARCH'].astype(str).str.upper()
        
    except Exception as e:
        print(f"❌ Mapping Error: {e}")
        return

    # Pitcher Logic
    all_p = pitchers[pitchers['POS_SEARCH'].str.contains('1', na=False)].copy()
    all_p['G_NUM'] = pd.to_numeric(all_p['G_COL'], errors='coerce').fillna(0)
    all_p['GS_NUM'] = pd.to_numeric(all_p['GS_COL'], errors='coerce').fillna(0)
    
    starter_pool = all_p[all_p['GS_NUM'] > 0]
    reliever_pool = all_p[all_p['G_NUM'] > all_p['GS_NUM']]

    # Fallback for relievers
    if reliever_pool.empty:
        reliever_pool = all_p[all_p['GS_NUM'] == 0]
    if reliever_pool.empty: # Final safety
        reliever_pool = all_p

    # Hitter Logic
    h_pool = batters[batters['POS_SEARCH'].str.contains(r'[2-9]', na=False)]
    slots = [('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), ('7|O', 'LF'), ('8|O', 'CF'), ('9|O', 'RF')]
    final_roster = []
    used_names = set()

    for code, label in slots:
        mask = h_pool['POS_SEARCH'].str.contains(code, na=False)
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
        try: v_dh = float(dh_sel['OPS'])
        except: v_dh = 0.0
        final_roster.append({'Name': dh_sel['NAME'], 'Pos': 'DH', 'Val': v_dh})

    sp_row = starter_pool.sample(1).iloc[0]
    final_rp_pool = reliever_pool[reliever_pool['NAME'] != sp_row['NAME']]
    rp_rows = final_rp_pool.sample(min(4, len(final_rp_pool)))

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

    print("--- POST PREVIEW ---")
    print(status_body)
    print("--------------------")

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(status_body)
        with open(game_file, "w") as f: f.write(str(current_game + 1))
        print(f"✅ Posted Successfully.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    post_lineup()
