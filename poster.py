import pandas as pd
import os
import random
import datetime
import pytz
from atproto import Client
import re

def sanitize_encoding(text):
    """Fixes common mangled UTF-8 characters from web scraping."""
    replacements = {
        'Ã±': 'ñ', 'Ã©': 'é', 'Ã³': 'ó', 'Ã¡': 'á', 'Ã­': 'í', 
        'Ãº': 'ú', 'Ã‘': 'Ñ', 'Ã': 'í', 'Ã\xa0': 'à'
    }
    for broken, fixed in replacements.items():
        text = text.replace(broken, fixed)
    return text

def format_name(full_name):
    """Cleans technical markers while preserving Jr., Sr., and accents."""
    clean_name = sanitize_encoding(str(full_name))
    # Remove B-Ref artifacts like *, #, ?, and numbers
    clean_name = re.sub(r'[*#?0-9]', '', clean_name)
    # Remove Hall of Fame markers
    clean_name = clean_name.replace('HOF', '').strip()
    
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
    if os.path.exists(game_file):
        with open(game_file, "r", encoding='utf-8-sig') as f:
            try:
                current_game = int(f.read().strip())
            except:
                current_game = 1
    else:
        current_game = 1

    # Time-zone check for NYC (11am - 10pm window)
    ny_tz = pytz.timezone('America/New_York')
    ny_now = datetime.datetime.now(ny_tz)
    if ny_now.hour not in range(11, 23):
        return 

    managers = [
        "George Bamberger", "Yogi Berra", "Mickey Callaway", "Terry Collins",
        "Mike Cubbage", "Joe Frazier", "Dallas Green", "Bud Harrelson",
        "Gil Hodges", "Frank Howard", "Art Howe", "Davey Johnson",
        "Jerry Manuel", "Roy McMillan", "Carlos Mendoza", "Salty Parker",
        "Willie Randolph", "Luis Rojas", "Buck Showalter", "Casey Stengel",
        "Jeff Torborg", "Joe Torre", "Bobby Valentine", "Wes Westrum"
    ]
    selected_manager = random.choice(managers)

    try:
        batters_df = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
        pitchers_df = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
        
        # Clean up column names
        batters_df.columns = [str(c).replace('\xa0', ' ').strip() for c in batters_df.columns]
        pos_col = next((n for n in ['Pos Summary', 'Pos', 'Positions'] if n in batters_df.columns), None)
        if not pos_col: return
        batters_df.rename(columns={pos_col: 'Pos Summary'}, inplace=True)
    except Exception as e:
        print(f"Error loading CSVs: {e}")
        return

    # --- THE DEEP SCOUT RECRUITMENT ---
    # 2=C, 3=1B, 4=2B, 5=3B, 6=SS, 7=LF, 8=CF, 9=RF
    field_needs = [
        ('2', 'C'), ('3', '1B'), ('4', '2B'), ('5', '3B'), 
        ('6', 'SS'), ('7', 'LF'), ('8', 'CF'), ('9', 'RF')
    ]
    
    final_roster = []
    used_names = set()

    for code, pos_name in field_needs:
        # Regex: Find code as a single digit or surrounded by non-digits (like / or *)
        # (?: ) is a non-capturing group to prevent pandas UserWarnings
        pattern = rf'(?:^|[^0-9]){code}(?:[^0-9]|$)'
        
        qualified_pool = batters_df[
            batters_df['Pos Summary'].astype(str).str.contains(pattern, regex=True, na=False)
        ]
        qualified_pool = qualified_pool[~qualified_pool['Name'].isin(used_names)]
        
        # Draw from qualified pool
        if not qualified_pool.empty:
            selection = qualified_pool.sample(1).iloc[0]
            used_names.add(selection['Name'])
            
            obp = pd.to_numeric(selection['OBP'], errors='coerce') or 0
            slg = pd.to_numeric(selection['SLG'], errors='coerce') or 0
            val = (obp * 1.2) + slg
            
            final_roster.append({'Name': selection['Name'], 'Pos': pos_name, 'Val': val})
        else:
            # MANAGER'S EMERGENCY BACKUP: Broad search if strict regex fails
            fallback_pool = batters_df[batters_df['Pos Summary'].astype(str).str.contains(code, na=False)]
            fallback_pool = fallback_pool[~fallback_pool['Name'].isin(used_names)]
            
            if not fallback_pool.empty:
                selection = fallback_pool.sample(1).iloc[0]
                used_names.add(selection['Name'])
                final_roster.append({'Name': selection['Name'], 'Pos': pos_name, 'Val': -1})
            else:
                print(f"Scouting Error: No {pos_name} found in database.")

    # Pick 1 DH from remaining position players
    dh_pool = batters_df[~batters_df['Name'].isin(used_names)]
    if not dh_pool.empty:
        selection = dh_pool.sample(1).iloc[0]
        obp = pd.to_numeric(selection['OBP'], errors='coerce') or 0
        slg = pd.to_numeric(selection['SLG'], errors='coerce') or 0
        final_roster.append({'Name': selection['Name'], 'Pos': 'DH', 'Val': (obp * 1.2) + slg})
        used_names.add(selection['Name'])

    # Sort 1-9 based on Hitting Value
    lineup_sorted = sorted(final_roster, key=lambda x: x['Val'], reverse=True)

    final_lineup_text = []
    for i, player in enumerate(lineup_sorted, 1):
        p_name = format_name(player['Name'])
        final_lineup_text.append(f"{i}. {p_name} - {player['Pos']}")

    # --- PITCHING & BULLPEN ---
    available_p = pitchers_df[~pitchers_df['Name'].str.contains('Totals|Rank|Name|HOF', na=False)]
    available_p = available_p[~available_p['Name'].isin(used_names)]
    
    sp_row = available_p.sample(1).iloc[0]
    sp_name = format_name(sp_row['Name'])
    used_names.add(sp_row['Name'])
    
    rp_pool = available_p[~available_p['Name'].isin(used_names)].sample(min(4, len(available_p)-1))
    rp_names = [format_name(n) for n in rp_pool['Name'].tolist()]

    # --- CONSTRUCT POST ---
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
        print(f"✅ Success: Game #{current_game} posted.")
        with open(game_file, "w", encoding='utf-8-sig') as f:
            f.write(str(current_game + 1))
    except Exception as e:
        print(f"❌ Post failed: {e}")

if __name__ == "__main__":
    post_lineup()
