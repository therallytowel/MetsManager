import pandas as pd
import os
import random
from atproto import Client
import re

def clean_name(name):
    # Strip B-Ref markers but keep accents
    clean = re.sub(r'[*#+?0-9]', '', str(name)).replace('HOF', '').strip()
    parts = clean.split()
    if len(parts) >= 2:
        return f"{parts[0][0]}. {parts[-1]}"
    return clean

def post_lineup():
    game_file = "game_number.txt"
    current_game = 1
    if os.path.exists(game_file):
        with open(game_file, "r") as f:
            try: current_game = int(f.read().strip())
            except: pass

    try:
        # Load with utf-8-sig for accents
        batters = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
        pitchers = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
        
        # Clean header whitespace
        batters.columns = [str(c).upper().strip() for c in batters.columns]
        pitchers.columns = [str(c).upper().strip() for c in pitchers.columns]

        # Map Batter columns by index
        batters = batters.rename(columns={
            batters.columns[1]: 'NAME', 
            batters.columns[-1]: 'POS_SEARCH',
            batters.columns[-2]: 'OPS'
        })
        
        # Map Pitcher columns by index (1=Name, -3=G, -2=GS, -1=PosSummary)
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

    # --- FIXED PITCHER LOGIC ---
    # 1. Filter for primary pitchers
    all_pitchers = pitchers[pitchers['POS_SEARCH'].str.startswith('1', na=False)].copy()
    
    # 2. Convert G and GS to numeric safely
    all_pitchers['G_NUM'] = pd.to_numeric(all_pitchers['G_COL'], errors='coerce').fillna(0)
    all_pitchers['GS_NUM'] = pd.to_numeric(all_pitchers['GS_COL'], errors='coerce').fillna(0)

    # Starter Pool: Anyone with at least 1 Start
    starter_pool = all_pitchers[all_pitchers['GS_NUM'] > 0]
    
    # Reliever Pool: Only people who appeared in relief (Games > Starts)
    reliever_pool = all_pitchers[all_pitchers['G_NUM'] > all_pitchers['GS_NUM']]

    # --- HITTER LOGIC ---
    real_hitter_pool = batters[batters['POS_SEARCH'].str.contains(r'[2-9]', na=False)]

    slots = [('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), ('7|O', 'LF'), ('8|O', 'CF'), ('9|O', 'RF')]
    final_roster = []
    used_names = set()

    for code, label in slots:
        mask = real_hitter_pool['POS_SEARCH'].str.contains(code, na=False)
        pool = real_hitter_pool[mask & ~real_hitter_pool['NAME'].isin(used_names)]
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used_names.add(sel['NAME'])
            val = pd.to_numeric(sel['OPS'], errors='coerce') or 0.0
            final_roster.append({'Name': sel['NAME'], 'Pos': label, 'Val': val})

    dh_pool = real_hitter_pool[~real_hitter_pool['NAME'].isin(used_names)]
    if not dh_pool.empty:
        dh_sel = dh_pool.sample(1).iloc[0]
        final_roster.append({'Name': dh_sel['NAME'], 'Pos': 'DH', 'Val': pd.to_numeric(dh_sel['OPS'], errors='coerce') or 0.0})

    # --- SELECT PITCHERS ---
    sp_row = starter_pool.sample(1).iloc[0]
    
    # Filter for relievers, excluding the current starter
    final_rp_pool = reliever_pool[reliever_pool['NAME'] != sp_row['NAME']]
    
    # Sample up to 4 relievers
    rp_rows = final_rp_pool.sample(min(4, len(final_rp_pool)))

    # --- FORMAT & POST ---
    order = sorted(final_roster, key=lambda x: x['Val'], reverse=True)
    lineup_rows = [f"{i+1} {clean_name(p['Name'])} {p['Pos']}" for i, p in enumerate(order)]
    mgr = random.choice(['Hodges', 'Johnson', 'Valentine', 'Berra', 'Collins', 'Mendoza'])

    status_body = (
        f"Game #{current_game}\nMgr: {mgr}\n\n"
        + "\n".join(lineup_rows) + 
        f"\n\nP: {clean_name(sp_row['NAME'])}\n"
        f"Bullpen: " + ", ".join([clean_name(n['NAME']) for _, n in rp_rows.iterrows()])
    )

    if len(status_body) > 300:
        status_body = status_body[:300]

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(status_body)
        with open(game_file, "w") as f: f.write(str(current_game + 1))
        print(f"✅ Success! Game #{current_game} posted with a true Bullpen.")
    except Exception as e:
        print(f"❌ Bluesky Error: {e}")

if __name__ == "__main__":
    post_lineup()
