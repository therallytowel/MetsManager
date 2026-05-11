import pandas as pd
import os
import random
from atproto import Client
import re

def format_name(full_name):
    """Cleans B-Ref markers and returns 'Last, F.' format."""
    # Remove HOF (+), Active (*), and digits
    clean_name = re.sub(r'[*#+?0-9]', '', str(full_name)).replace('HOF', '').strip()
    # Remove bracketed info or nicknames in quotes
    clean_name = re.sub(r'[\(\"\'].*?[\)\"\']', '', clean_name).strip()
    parts = clean_name.split()
    if len(parts) >= 2:
        return f"{parts[-1]}, {parts[0][0]}"
    return clean_name

def post_lineup():
    game_file = "game_number.txt"
    current_game = 1
    if os.path.exists(game_file):
        with open(game_file, "r") as f:
            try: current_game = int(f.read().strip())
            except: pass

    try:
        batters_df = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
        pitchers_df = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
        batters_df.columns = [re.sub(r'\s+', ' ', str(c).strip()) for c in batters_df.columns]
        pos_col = 'Pos Summary'
    except Exception as e:
        print(f"❌ Data Error: {e}")
        return

    # 1. RECRUIT FIELDERS (2=C, 3=1B, 4=2B, 5=3B, 6=SS, 7=LF, 8=CF, 9=RF)
    field_needs = [('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), ('7', 'LF'), ('8', 'CF'), ('9', 'RF')]
    final_roster = []
    used_names = set()

    for code, pos_label in field_needs:
        # THE FIX: Look for the specific number OR the generic 'OF' for outfield spots
        if code in ['7', '8', '9']:
            mask = (batters_df[pos_col].astype(str).str.contains(code, na=False)) | \
                   (batters_df[pos_col].astype(str).str.fullmatch('OF', na=False))
        else:
            mask = batters_df[pos_col].astype(str).str.contains(code, na=False)
            
        pool = batters_df[mask & ~batters_df['Name'].isin(used_names)]

        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used_names.add(sel['Name'])
            # Career OPS for sorting the lineup
            val = pd.to_numeric(sel['OPS'], errors='coerce') or 0.000
            final_roster.append({'Name': sel['Name'], 'Pos': pos_label, 'Val': val})
        else:
            print(f"🚫 Failed to find a historical {pos_label}. Aborting.")
            return

    # 2. RECRUIT DH (Best remaining hitter)
    dh_pool = batters_df[~batters_df['Name'].isin(used_names)]
    sel_dh = dh_pool.sample(1).iloc[0]
    final_roster.append({'Name': sel_dh['Name'], 'Pos': 'DH', 'Val': pd.to_numeric(sel_dh['OPS'], errors='coerce') or 0.000})

    # 3. RECRUIT PITCHERS
    sp_row = pitchers_df.sample(1).iloc[0]
    used_names.add(sp_row['Name'])
    rp_rows = pitchers_df[~pitchers_df['Name'].isin(used_names)].sample(4)

    # 4. FORMAT & POST
    # Sort lineup by OPS (Val) descending
    lineup_sorted = sorted(final_roster, key=lambda x: x['Val'], reverse=True)
    lineup_text = [f"{i+1}. {format_name(p['Name'])} - {p['Pos']}" for i, p in enumerate(lineup_sorted)]
    
    mgr = random.choice(['Gil Hodges', 'Davey Johnson', 'Bobby Valentine', 'Casey Stengel', 'Yogi Berra', 'Terry Collins'])
    
    status_text = (
        f"Game #{current_game}\n"
        f"Manager: {mgr}\n\n"
        + "\n".join(lineup_text) + 
        f"\n\nP: {format_name(sp_row['Name'])}\n\nBullpen:\n" + 
        "\n".join([format_name(n) for n in rp_rows['Name']]) + 
        "\n\n#MetsSky #LGM"
    )

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(status_text)
        with open(game_file, "w") as f: f.write(str(current_game + 1))
        print(f"✅ Success: Game #{current_game} posted!")
    except Exception as e:
        print(f"❌ Bluesky Error: {e}")

if __name__ == "__main__":
    post_lineup()
