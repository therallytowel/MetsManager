import pandas as pd
import random
from atproto import Client
import os
import unicodedata
from datetime import datetime, date
import pytz
import httpx
from PIL import Image, ImageDraw, ImageFont

def solve_defense(players, required_positions):
    if not players: return {}
    current_player = players[0]
    remaining_players = players[1:]
    eligible_pos = [p for p in required_positions if p in current_player['EligiblePositions']]
    if 'DH' in required_positions: eligible_pos.append('DH')
    random.shuffle(eligible_pos)
    for pos in eligible_pos:
        result = solve_defense(remaining_players, [p for p in required_positions if p != pos])
        if result is not None:
            result[current_player['Player']] = pos
            return result
    return None

def calculate_amazin_index(lineup, starter_row, bp_rows, mgr_name):
    avg_ops = sum([float(p.get('OPS', 0.720)) for p in lineup]) / 9
    hitting_score = max(0, min((avg_ops - 0.600) * 160, 40))
    s_era = float(starter_row.get('ERA+', 100))
    bp_list = bp_rows.to_dict('records') if hasattr(bp_rows, 'to_dict') else bp_rows
    bp_era = sum([float(p.get('ERA+', 100)) for p in bp_list]) / len(bp_list)
    pitching_score = max(0, min(((s_era - 100) * 0.4) + ((bp_era - 100) * 0.2) + 20, 40))
    total_asg = sum([int(p.get('ASG', 0)) for p in lineup]) + int(starter_row.get('ASG', 0))
    return round(max(15, min(hitting_score + pitching_score + min(total_asg * 0.5, 10) + 10, 100)))

def get_status_label(score):
    if score >= 88: return "World Series Favorites 🏆"
    elif score >= 78: return "The 1986 Vibes 🍏"
    elif score >= 68: return "Solid Wild Card Contender ⚾️"
    elif score >= 55: return "The '73 Ya Gotta Believe Era 🏗️"
    else: return "Panic Citi 😱"

def create_story_image(lineup, defense, starter, bp_rows, bench, mgr, score, status, game_num):
    # Colors
    mets_blue = (12, 35, 64, 255)
    mets_orange = (252, 76, 2, 255)
    white = (255, 255, 255, 255)
    
    # 1. Load Templates (Use custom if exists, otherwise fallback to plain)
    try: img1 = Image.open("template_lineup.png").convert("RGBA")
    except FileNotFoundError: img1 = Image.new("RGBA", (1080, 1920), mets_blue)
        
    try: img2 = Image.open("template_depth.png").convert("RGBA")
    except FileNotFoundError: img2 = Image.new("RGBA", (1080, 1920), mets_blue)

    # 2. Setup Fonts
    font_paths = ["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    font_title = font_sub = font_body = ImageFont.load_default()
    for path in font_paths:
        if os.path.exists(path):
            font_title = ImageFont.truetype(path, 42)
            font_sub = ImageFont.truetype(path, 34)
            font_body = ImageFont.truetype(path, 38)
            break

    # 3. Draw Lineup Card
    canvas1 = ImageDraw.Draw(img1)
    canvas1.text((100, 150), f"GAME #{game_num}", font=font_sub, fill=white)
    canvas1.text((100, 250), f"AMAZIN' INDEX: {score}/100", font=font_title, fill=white)
    canvas1.text((100, 390), f"SKIPPER: {mgr.upper()}", font=font_title, fill=mets_orange)
    
    y = 530
    for i, p in enumerate(lineup):
        name = p['Player'].upper()
        pos = defense[name.title() if 'Mazzilli' in name or 'Piazza' in name else name.title()]
        canvas1.text((100, y), f"{i+1}", font=font_body, fill=mets_orange)
        canvas1.text((180, y), name, font=font_body, fill=white)
        canvas1.text((750, y), f"({pos})", font=font_body, fill=white)
        y += 105
    canvas1.text((100, 1570), f"SP: {starter['Name'].upper()}", font=font_title, fill=mets_orange)
    img1.save("today_story_card_1.png")

    # 4. Draw Depth Card
    canvas2 = ImageDraw.Draw(img2)
    y = 380
    bp_list = bp_rows.to_dict('records') if hasattr(bp_rows, 'to_dict') else bp_rows
    for p in bp_list:
        canvas2.text((160, y), p.get('Name', 'Pitcher').upper(), font=font_body, fill=white)
        y += 110
    y += 150
    for b in bench:
        canvas2.text((160, y), b['Player'].upper(), font=font_body, fill=white)
        y += 110
    img2.save("today_story_card_2.png")

def generate_lineup():
    pos_df = pd.read_csv('Mets_Positional_History - Mets_Positional_History.csv', encoding='utf-8-sig')
    bat_df = pd.read_csv('mets_batters.csv', encoding='utf-8-sig')
    pitchers_df = pd.read_csv('mets_pitchers.csv', encoding='utf-8-sig')
    
    field_pos = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF']
    for p in field_pos: pos_df[p] = pd.to_numeric(pos_df[p], errors='coerce').fillna(0)
    pos_master = pos_df.groupby('Player')[field_pos].sum().reset_index()
    pos_master['EligiblePositions'] = pos_master.apply(lambda r: [p for p in field_pos if r[p] > 0], axis=1)
    
    bat_df = bat_df.rename(columns={'Name': 'Player'})
    bat_df['G'] = pd.to_numeric(bat_df['G'], errors='coerce').fillna(1)
    master_batters = pd.merge(pos_master, bat_df, on='Player', how='inner')
    
    pitchers_df['ERA+'] = pd.to_numeric(pitchers_df['ERA+'].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(100)
    p_stats = pitchers_df.groupby('Name').agg({'GS': 'sum', 'G': 'sum', 'ERA+': 'mean', 'ASG': 'max'}).reset_index()
    
    et = pytz.timezone('America/New_York')
    today = datetime.now(et).date()
    game_num = (today - date(2026, 5, 15)).days + 1
    
    all_sampled = master_batters[~master_batters['Player'].isin(p_stats['Name'].tolist())].sample(14, weights='G').to_dict('records')
    lineup_pool, bench = all_sampled[:9], all_sampled[9:]
    defense_map = solve_defense(lineup_pool, field_pos + ['DH'])
    
    starter_row = p_stats[p_stats['GS'] > 0].sample(1, weights='G').iloc[0]
    bp_rows = p_stats[p_stats['Name'] != starter_row['Name']].sample(4, weights='G').to_dict('records')
    mgr = random.choice(["Gil Hodges", "Davey Johnson", "Bobby Valentine", "Terry Collins", "Buck Showalter", "Carlos Mendoza"])
    
    score = calculate_amazin_index(lineup_pool, starter_row, bp_rows, mgr)
    create_story_image(lineup_pool, defense_map, starter_row, bp_rows, bench, mgr, score, get_status_label(score), game_num)
    return lineup_pool, defense_map, starter_row, bp_rows, bench, mgr, score

def post_to_bluesky():
    try:
        lineup, defense, starter, bp_rows, bench, mgr, score = generate_lineup()
        game_num = (datetime.now(pytz.timezone('America/New_York')).date() - date(2026, 5, 15)).days + 1
        
        client = Client(base_url='https://bsky.social')
        client.login(os.environ['BSKY_HANDLE'], os.environ['BSKY_PASSWORD'])
        
        root = client.send_post(f"Game #{game_num}\nAmazin' Index: {score}/100\nMgr: {mgr}\n\n" + "\n".join([f"{i+1} {p['Player']} {defense[p['Player']]}" for i, p in enumerate(lineup)]) + f"\nP: {starter['Name']}")
        client.send_post(f"Bullpen: {', '.join([p['Name'] for p in bp_rows])}\n\nBench: {', '.join([b['Player'] for b in bench])}", reply_to={'root': root, 'parent': root})
    except Exception as e: print(f"Post failed: {e}")

if __name__ == "__main__": post_to_bluesky()
