import pandas as pd
import os
import random
from atproto import Client
import re

def get_clean_name(name, all_names_list):
    """
    If a last name is shared by multiple players, use 'F. Last'.
    Otherwise, use just 'Last'.
    """
    # 1. Clean B-Ref markers
    raw_clean = re.sub(r'[*#+?0-9]', '', str(name)).replace('HOF', '').strip()
    parts = raw_clean.split()
    if not parts:
        return raw_clean
    
    last_name = parts[-1]
    first_initial = parts[0][0]

    # 2. Check if this last name appears more than once in the dataset
    # We strip markers from the full list to compare fairly
    all_lasts = [re.sub(r'[*#+?0-9]', '', str(n)).replace('HOF', '').strip().split()[-1] 
                 for n in all_names_list if isinstance(n, str)]
    
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
        batters = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
        pitchers = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
        
        # Build a master list of all names to check for duplicates
        master_names = pd.concat([batters.iloc[:, 1], pitchers.iloc[:, 1]]).tolist()

        # Clean headers
        batters.columns = [str(c).upper().strip() for c in batters.columns]
        pitchers.columns = [str(c).upper().strip() for c in pitchers.columns]

        # Map by index
        batters = batters.rename(columns={
            batters.columns[1]: 'NAME', 
            batters.columns[-1]: 'POS_SEARCH',
            batters.columns[-2]: 'OPS'
        })
        
        pitchers = pitchers.rename(columns={
            pitchers.columns[1]: 'NAME',
            pitchers.columns[-3]: 'G_COL',
            pitchers.columns[-2]: 'GS_COL',
            pitchers.columns[-1]: 'POS_SEARCH'
        })

        batters['POS_SEARCH'] = batters['POS_SEARCH'].astype(str).str.upper()
        pitchers['POS_SEARCH'] = pitchers['POS_SEARCH'].astype(str).str.upper()
        
    except Exception as e:
        print(f"❌ Load Error: {e}")
        return

    # Filter Logic
    all_p = pitchers[pitchers['POS_SEARCH'].str.startswith('1', na=False)].copy()
    all_p['G_NUM'] = pd.to_numeric(all_p['G_COL'], errors='coerce').fillna(0)
    all_p['GS_NUM'] = pd.to_numeric(all_p['GS_COL'], errors='coerce').fillna(0)

    starter_pool = all_p[all_p['GS_NUM'] > 0]
    reliever_pool = all_p[all_p['G_NUM'] > all_p['GS_NUM']]

    hitter_pool = batters[batters['POS_SEARCH'].str.contains(r'[2-9]', na=False)]
    slots = [('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), ('7|O', 'LF'), ('8|O', 'CF'), ('9|O', 'RF')]
    final_roster = []
    used_names = set()

    for code, label in slots:
        mask = hitter_pool['POS_SEARCH'].str.contains(code, na=False)
        pool = hitter_pool[mask & ~hitter_pool['NAME'].isin(used_names)]
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used_names.add(sel['NAME'])
            try:
                val = float(sel['OPS']) if pd.notnull(sel['OPS']) else 0.0
            except:
                val = 0.0
            final_roster.append({'Name': sel['NAME'], 'Pos': label, 'Val': val})

    dh_pool = hitter_pool[~hitter_pool['NAME'].isin(used_names)]
    if not dh_pool.empty:
        dh_sel = dh_pool.sample(1).iloc[0]
        try:
            val = float(dh_sel['OPS']) if pd.notnull(dh_sel['OPS']) else 0.0
        except:
            val = 0.0
        final_roster.append({'Name': dh_sel['NAME'], 'Pos': 'DH', 'Val': val})

    # Select Pitchers
    sp_row = starter_pool.sample(1).iloc[0]
    final_rp_pool = reliever_pool[reliever_pool['NAME'] != sp_row['NAME']]
    rp_rows = final_rp_pool.sample(min(4, len(final_rp_pool)))

    # --- FORMATTING WITH THE SMART NAME CHECK ---
    order = sorted(final_roster, key=lambda x: x['Val'], reverse=True)
    lineup_rows = [f"{i+1} {get_clean_name(p['Name'], master_names)} {p['Pos']}" for i, p in enumerate(order)]
    mgr = random.choice(['Hodges', 'Johnson', 'Valentine', 'Berra', 'Collins', 'Mendoza'])

    status_body = (
        f"Game #{current_game}\nMgr: {mgr}\n\n"
        + "\n".join(lineup_rows) + 
        f"\n\nP: {get_clean_name(sp_row['NAME'], master_names)}\n"
        f"Bullpen: " + ", ".join([get_clean_name(n['NAME'], master_names) for _, n in rp_rows.iterrows()])
    )

    if len(status_body) > 300:
        status_body = status_body[:297] + "..."

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(status_body)
        with open(game_file, "w") as f: f.write(str(current_game + 1))
        print(f"✅ Success! Game #{current_game} is live with Smart Names.")
    except Exception as e:
        print(f"❌ Bluesky Error: {e}")

if __name__ == "__main__":
    post_lineup()
