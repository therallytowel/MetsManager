import pandas as pd
import requests
from bs4 import BeautifulSoup, Comment
import io
import re

def scrape_mets_data():
    url = "https://www.baseball-reference.com/teams/NYM/bat.shtml"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    print("Scouting the Amazins... (Accessing Baseball-Reference)")
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    df = pd.DataFrame()

    try:
        # 1. Search for the table hidden inside HTML comments
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            if 'id="players_standard_batting"' in comment:
                # We found the hidden table! Convert the comment string back into a searchable soup object
                comment_soup = BeautifulSoup(comment, 'html.parser')
                table = comment_soup.find('table', {'id': 'players_standard_batting'})
                if table:
                    df = pd.read_html(io.StringIO(str(table)))[0]
                    break
        
        # 2. Fallback: If not in comments, check the visible HTML
        if df.empty:
            table = soup.find('table', {'id': 'players_standard_batting'})
            if table:
                df = pd.read_html(io.StringIO(str(table)))[0]

        if df.empty:
            print("❌ Failure: Could not locate the batting table in comments or HTML.")
            return

        # 3. CLEANING: Remove invisible characters (\xa0) and non-breaking spaces
        df.columns = [re.sub(r'\s+', ' ', str(c).strip()) for c in df.columns]
        
        # 4. Standardize the Position Column Name
        # Looking for 'Pos Summary' or 'Pos'
        pos_options = [c for c in df.columns if 'Pos' in c]
        if pos_options:
            df.rename(columns={pos_options[0]: 'Pos Summary'}, inplace=True)

        # 5. Filter out headers/junk
        df = df.dropna(subset=['Name'])
        df = df[~df['Name'].str.contains("Name|Total|Rank", na=False)]
        
        df.to_csv('mets_batters.csv', index=False, encoding='utf-8-sig')
        print(f"✅ Success! Created mets_batters.csv with {len(df)} players.")
        print(f"Columns: {list(df.columns)}")
        
    except Exception as e:
        print(f"❌ Scraper Error: {e}")

if __name__ == "__main__":
    scrape_mets_data()
