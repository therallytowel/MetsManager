import pandas as pd
import os
import random
import datetime
import pytz
from atproto import Client
import re

def sanitize_encoding(text):
    """Fixes mangled UTF-8 characters from web scraping."""
    replacements = {'Ã±': 'ñ', 'Ã©': 'é', 'Ã³': 'ó', 'Ã¡': 'á', 'Ã­': 'í', 'Ãº': 'ú', 'Ã‘': 'Ñ'}
    for broken, fixed in replacements.items():
        text = text.replace(broken, fixed)
    return text

def format_name(full_name):
    """Cleans technical markers while preserving Jr., Sr., and accents."""
    clean_name = sanitize_encoding(str(full_name))
    # Remove B-Ref artifacts like *, #, ?, and numbers
    clean_name = re.sub(r'[*#?0-9]', '', clean_name).replace('HOF', '').strip()
    
    parts = clean_name.split()
    if len(parts) >= 2:
        suffixes = ['Jr.', 'Sr.', 'II', 'III', 'IV']
        if parts[-1] in suffixes and len(parts) >= 3:
            # Format: Surname Suffix, FirstInitial
            return f"{parts[-2]} {parts[-1]}, {parts[0][0]}"
        # Format: Surname, FirstInitial
        return f"{parts[-1]}, {parts[0][0]}"
    return clean_name

def post_lineup():
    game_file = "game_number.txt"
    current_game = 1
    if os.path.exists(game_file):
        with open(game_file, "r", encoding='utf-8-sig') as f:
            try:
                current_game = int(f.read().strip())
            except:
                current_game = 1

    # NYC Time Window Check (11am - 10pm)
    ny_tz = pytz.timezone('America/New_York')
    ny_now = datetime.datetime.now(ny_tz)
    if ny_now.hour not in range(11, 23):
        print(f"Skipping: Current hour {ny_now.hour} is outside the posting window.")
        return 

    try:
        batters_df = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
        pitchers_df = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
        
        # Clean column names (handles the \xa0 non-breaking space issue)
        batters_df.columns = [str(c).replace('\xa0', ' ').strip() for c in batters_df.columns]
        pitchers_df.columns = [str(c).replace('\xa0', ' ').strip() for c in pitchers_df.columns]
        
        pos_col = next((n for n in ['Pos Summary', 'Pos', 'Positions'] if n in batters_df.columns), 'Pos Summary')
        batters_df[pos_col] = batters_df[pos_col].astype(str).str.strip()
    except Exception as e:
        print(f"❌ File Error: {e}")
        return

    # 1. RECRUIT FIELDERS (2=C, 3=1B, 4=2B, 5=3B, 6=SS, 7=LF, 8=CF, 9=RF)
    field_needs = [('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), ('6', 'SS'), ('7', 'LF'), ('8', 'CF'), ('9', 'RF')]
    final_roster = []
    used_names = set()

    for code, pos_name in field_needs:
        # Search for the position code anywhere in the summary string
        mask = batters_df[pos_col].str.contains(code, na=False)
        pool = batters_df[mask & ~batters_df['Name'].isin(used_names)]
        
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used_names.add(sel['Name'])
            
            obp = pd.to_numeric(sel['OBP'], errors='coerce') or 0
            slg = pd.to_numeric(sel['SLG'], errors='coerce') or 0
            val = (obp * 1.2) + slg # Hitting value for order sorting
            
            final_roster.append({'Name': sel['Name'], 'Pos': pos_name, 'Val': val})
        else:
            print(f"⚠️ SCOUTING REPORT: No player found for {pos_name} (Code {code})")

    # 2. RECRUIT DH (Strictly No Pitchers)
    dh_pool = batters_df[~batters_df['Name'].isin(used_names) & ~batters_df[pos_col].str.contains('P', na=False)]
    if not dh_pool.empty:
        sel = dh_pool.sample(1).iloc[0]
        used_names.add(sel['Name'])
        obp = pd.to_numeric(sel['OBP'], errors='coerce') or 0
        slg = pd.to_numeric(sel['SLG'], errors='coerce') or 0
        final_roster.append({'Name': sel['Name'], 'Pos': 'DH', 'Val': (obp * 1.2) + slg})

    # ABORT if we don't have a full 9-man lineup
    if len(final_roster) < 9:
        print(f"🚫 POST ABORTED: Roster only has {len(final_roster)}/9 players.")
        return

    # 3. RECRUIT PITCHERS
    true_pitchers = pitchers_df[~pitchers_df['Name'].str.contains('Totals|Rank|Name|HOF', na=False)]
    true_pitchers = true_pitchers[~true_pitchers['Name'].isin(used_names)]
    
    if true_pitchers.empty:
        print("❌ POST ABORTED: No pitchers found in pitchers_df.")
        return

    # Select Starter
    sp_row = true_pitchers.sample(1).iloc[0]
    sp_name = format_name(sp_row['Name'])
    used_names.add(sp_row['Name'])
    
    # Select Bullpen (up to 4)
    rp_pool = true_pitchers[~true_pitchers['Name'].isin(used_names)].sample(min(4, len(true_pitchers)-1))
    rp_names = [format_name(n) for n in rp_pool['Name'].tolist()]

    # 4. FORMAT BATTING ORDER & POST
    lineup_sorted = sorted(final_roster, key=lambda x: x['Val'], reverse=True)
    final_lineup_text = [f"{i+1}. {format_name(p['Name'])} - {p['Pos']}" for i, p in enumerate(lineup_sorted)]
    
    managers = ["Bobby Valentine", "Gil Hodges", "Davey Johnson", "Buck Showalter", "Willie Randolph", "Casey Stengel", "Terry Collins"]
    selected_manager = random.choice(managers)
    
    status_text = (
        f"Game #{current_game}\n"
        f"Manager: {selected_manager}\n\n"
        + "\n".join(final_lineup_text) + 
        f"\n\nP: {sp_name}\n\n"
        f"Bullpen:\n" + "\n".join(rp_names) + 
        "\n\n#MetsSky"
    )

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(status_text)
        with open(game_file, "w", encoding='utf-8-sig') as f:
            f.write(str(current_game + 1))
        print(f"✅ Success: Game #{current_game} posted!")
    except Exception as e:
        print(f"❌ ATPROTO ERROR: {e}")

if __name__ == "__main__":
    post_lineup()
