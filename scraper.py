import pandas as pd
import requests
from bs4 import BeautifulSoup, Comment
import io
import re

def scrape_mets_history():
    urls = {
        "batters": "https://www.baseball-reference.com/teams/NYM/bat.shtml",
        "pitchers": "https://www.baseball-reference.com/teams/NYM/pitch.shtml"
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for key, url in urls.items():
        print(f"Scouting ALL {key} in Mets history...")
        try:
            response = requests.get(url, headers=headers, timeout=20)
            # Franchise career tables are hidden in comments
            html_content = response.text.replace('', '')
            soup = BeautifulSoup(html_content, 'html.parser')
            
            table_id = "players_career_batting" if key == "batters" else "players_career_pitching"
            table = soup.find('table', {'id': table_id})
            
            if not table:
                tables = soup.find_all('table')
                table = max(tables, key=lambda x: len(x.find_all('tr')))

            df = pd.read_html(io.StringIO(str(table)))[0]

            # Standardize Column Names
            df.columns = [re.sub(r'\s+', ' ', str(c).strip()) for c in df.columns]
            
            # Map position column - career tables often use the last column for summary
            if key == "batters":
                # Ensure the column used for positions is named 'Pos Summary'
                pos_key = next((c for c in df.columns if 'Pos' in c), df.columns[-1])
                df.rename(columns={pos_key: 'Pos Summary'}, inplace=True)

            # Cleanup
            df = df.dropna(subset=['Name'])
            df = df[~df['Name'].str.contains("Name|Total|Rank", na=False)]
            
            df.to_csv(f'mets_{key}.csv', index=False, encoding='utf-8-sig')
            print(f"✅ Success! Saved {len(df)} total {key}.")
            
        except Exception as e:
            print(f"❌ Scraper Error on {key}: {e}")

if __name__ == "__main__":
    scrape_mets_history()
