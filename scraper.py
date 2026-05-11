import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import re

def scrape_full_franchise():
    urls = {
        "batters": "https://www.baseball-reference.com/teams/NYM/bat.shtml",
        "pitchers": "https://www.baseball-reference.com/teams/NYM/pitch.shtml"
    }
    headers = {"User-Agent": "Mozilla/5.0"}

    for key, url in urls.items():
        print(f"Scouting the ENTIRE {key} pool...")
        try:
            response = requests.get(url, headers=headers, timeout=20)
            # Career tables are hidden in HTML comments; this exposes them
            html_content = response.text.replace('', '')
            soup = BeautifulSoup(html_content, 'html.parser')
            
            table_id = f"players_career_{key}"
            table = soup.find('table', {'id': table_id})
            
            # Use 'lxml' to avoid dependency errors
            df = pd.read_html(io.StringIO(str(table)), flavor='lxml')[0]
            
            # Clean up headers
            df.columns = [re.sub(r'\W+', '', str(c)) for c in df.columns]
            
            if key == "batters":
                # Find the position summary column (usually the last one)
                pos_col = next((c for c in df.columns if 'Pos' in c), df.columns[-1])
                df.rename(columns={pos_col: 'PosSummary'}, inplace=True)

            # Drop headers that repeat mid-table and empty names
            df = df.dropna(subset=['Name'])
            df = df[~df['Name'].str.contains("Name|Total|Rank", na=False)]
            
            df.to_csv(f'mets_{key}.csv', index=False, encoding='utf-8-sig')
            print(f"✅ Success! {len(df)} players added to the pool.")
            
        except Exception as e:
            print(f"❌ Scraper Error: {e}")

if __name__ == "__main__":
    scrape_full_franchise()
