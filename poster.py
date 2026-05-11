import pandas as pd
import os
import random
from atproto import Client
import re

def format_name(name):
    # Pure cleanup
    clean = re.sub(r'[*#+?0-9]', '', str(name)).strip()
    parts = clean.split()
    return f"{parts[-1]}, {parts[0][0]}" if len(parts) >= 2 else clean

def post_lineup():
    game_file = "game_number.txt"
    current_game = 1
    if os.path.exists(game_file):
        with open(game_file, "r") as f:
            try: current_game = int(f.read().strip())
            except: pass

    try:
        batters = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
        # We'll use a curated list of pitchers if the scraper failed
        pitchers = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
    except Exception as e:
        print(f"❌ Load Error: {e}")
        return

    # THE POSITIONS (Looking for actual letters: C, 1B, 2B, 3B, SS, LF, CF, RF)
    slots = [('C', 'C'), ('1B', '1B'), ('2B', '2B'), ('3B', '3B'), ('SS', 'SS'), ('LF', 'LF'), ('CF', 'CF'), ('RF', 'RF')]
    final_roster = []
    used = set()

    for pos_code, pos_label in slots:
        # Strict matching: PosSummary must contain the letters
        mask = batters['PosSummary'].astype(str).str.contains(pos_code, na=False)
        pool = batters[mask & ~batters['Name'].isin(used)]
        
        if not pool.empty:
            sel = pool.sample(1).iloc[0]
            used.add(sel['Name'])
            final_roster.append({'Name': sel['Name'], 'Pos': pos_label})
        else:
            # NO RANDOS: We stop the script if a position can't be filled legitimately
            print(f"🚫 DATA GAP: No legitimate '{pos_label}' found in the legends pool. Post cancelled.")
            return

    # DH (One more legend)
    dh_pool = batters[~batters['Name'].isin(used)]
    sel_dh = dh_pool.sample(1).iloc[0]
    final_roster.append({'Name': sel_dh['Name'], 'Pos': 'DH'})

    # Pitchers
    sp = pitchers.sample(1).iloc[0]
    rp = pitchers[pitchers['Name'] != sp['Name']].sample(4)

    # Sort & Post
    # (Since this is a legends pool, order is randomized for variety)
    random.shuffle(final_roster)
    lineup_txt = [f"{i+1}. {format_name(p['Name'])} - {p['Pos']}" for i, p in enumerate(final_roster)]
    
    mgr = random.choice(['Gil Hodges', 'Davey Johnson', 'Bobby Valentine', 'Casey Stengel'])
    body = (f"Game #{current_game} (Legends Edition)\n"
            f"Manager: {mgr}\n\n" + 
            "\n".join(lineup_txt) + 
            f"\n\nP: {format_name(sp['Name'])}\n\n"
            f"Bullpen:\n" + "\n".join([format_name(n['Name']) for _, n in rp.iterrows()]) + 
            "\n\n#MetsSky #LGM")

    try:
        client = Client()
        client.login(os.environ.get('BSKY_HANDLE'), os.environ.get('BSKY_PASSWORD'))
        client.send_post(body)
        with open(game_file, "w") as f: f.write(str(current_game + 1))
        print(f"✅ Success: Posted Game #{current_game} with 100% Legitimate Mets.")
    except Exception as e:
        print(f"❌ Posting Error: {e}")

if __name__ == "__main__":
    post_lineup()
