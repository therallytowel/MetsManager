import pandas as pd
import os
import random
import datetime
import pytz
from atproto import Client
import re

def sanitize_encoding(text):
    replacements = {'Ã±': 'ñ', 'Ã©': 'é', 'Ã³': 'ó', 'Ã¡': 'á', 'Ã­': 'í', 'Ãº': 'ú', 'Ã‘': 'Ñ'}
    for broken, fixed in replacements.items():
        text = text.replace(broken, fixed)
    return text

def format_name(full_name):
    clean_name = sanitize_encoding(str(full_name))
    clean_name = re.sub(r'[*#?0-9]', '', clean_name).replace('HOF', '').strip()
    parts = clean_name.split()
    if len(parts) >= 2:
        suffixes = ['Jr.', 'Sr.', 'II', 'III', 'IV']
        if parts[-1] in suffixes and len(parts) >= 3:
            return f"{parts[-2]} {parts[-1]}, {parts[0][0]}"
        return f"{parts[-1]}, {parts[0][0]}"
    return clean_name

def post_lineup():
    game_file = "game_number.txt"
    current_game = 1
    if os.path.exists(game_file):
        with open(game_file, "r", encoding='utf-8-sig') as f:
            try: current_game = int(f.read().strip())
            except: pass

    try:
        batters_df = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
        pitchers_df = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
        batters_df.columns = [str(c).strip() for c in batters_df.columns]
        
        # DIAGNOSTIC: Print the first 5 rows and column names to see what's happening
        print("--- CSV DIAGNOSTIC ---")
        print(f"Columns found: {batters_df.columns.tolist()}")
        print(batters_df[['Name', 'Pos Summary']].head(10))
        print("----------------------")

        pos_col = 'Pos Summary' 
        if pos_col not in batters_df.columns:
            print(f"ERROR: Could not find '{pos_col}' column!")
            return
    except Exception as e:
        print(f"Error: {e}")
        return

    field_needs = [('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), ('7', 'LF'), ('8', 'CF'), ('9', 'RF')]
    final_roster = []
    used_names = set()

    for code, pos_name in field_needs:
        # The most aggressive search possible: just check if the string contains the digit
        mask = batters_df['Pos Summary'].astype(str).str.contains(code, na=False)
        qualified_pool = batters_df[mask & ~batters_df['Name'].isin(used_names)]
        
        if not qualified_pool.empty:
            selection = qualified_pool.sample(1).iloc[0]
            used_names.add(selection['Name'])
            obp = pd.to_numeric(selection['OBP'], errors='coerce') or 0
            slg = pd.to_numeric(selection['SLG'], errors='coerce') or 0
            final_roster.append({'Name': selection['Name'], 'Pos': pos_name, 'Val': (obp * 1.2) + slg})
        else:
            print(f"Scouting Error: No {pos_name} (Code {code}) found.")

    # DH
    dh_pool = batters_df[~batters_df['Name'].isin(used_names)]
    if not dh_pool.empty:
        selection = dh_pool.sample(1).iloc[0]
        final_roster.append({'Name': selection['Name'], 'Pos': 'DH', 'Val': 0})
        used_names.add(selection['Name'])

    # Batting Order & Pitching
    lineup_sorted = sorted(final_roster, key=lambda x: x['Val'], reverse=True)
    final_lineup_text = [f"{i+1}. {format_name(p['Name'])} - {p['Pos']}" for i, p in enumerate(lineup_sorted)]

    available_p = pitchers_df[~pitchers_df['Name'].str.contains('Totals|Rank|Name|HOF', na=False)]
    available_p = available_p[~available_p['Name'].isin(used_names)]
    sp_row = available_p.sample(1).iloc[0]
    sp_name = format_name(sp_row['Name'])
    used_names.add(sp_row['Name'])
    rp_names = [format_name(n) for n in available_p[~available_p['Name'].isin(used_names)].sample(4)['Name'].tolist()]

    # Construct & Post
    managers = ["Willie Randolph", "Davey Johnson", "Bobby Valentine", "Gil Hodges", "Terry Collins", "Buck Showalter"]
    status_text = f"Game #{current_game}\nManager: {random.choice(managers)}\n\n" + "\n".join(final_lineup_text) + f"\n\nP: {sp_name}\n\nBullpen:\n" + "\n".join(rp_names) + "\n\n#MetsSky"

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(status_text)
        with open(game_file, "w", encoding='utf-8-sig') as f: f.write(str(current_game + 1))
    except Exception as e: print(f"Post failed: {e}")

if __name__ == "__main__":
    post_lineup()
