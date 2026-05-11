import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import re

def scrape_mets_history():
    urls = {
        "batters": "https://www.baseball-reference.com/teams/NYM/bat.shtml",
        "pitchers": "https://www.baseball-reference.com/teams/NYM/pitch.shtml"
    }
    headers = {"User-Agent": "Mozilla/5.0"}

    for key, url in urls.items():
        print(f"Scouting ALL {key}...")
        try:
            response = requests.get(url, headers=headers, timeout=20)
            # Rip the table out of the comments
            html_content = response.text.replace('', '')
            soup = BeautifulSoup(html_content, 'html.parser')
            
            table_id = f"players_career_{key}"
            table = soup.find('table', {'id': table_id})
            
            if not table:
                # Career tables sometimes have simpler IDs
                table = soup.find('table', {'id': key})

            df = pd.read_html(io.StringIO(str(table)))[0]
            
            # Clean up column names (remove spaces/dots)
            df.columns = [re.sub(r'\W+', '', str(c)) for c in df.columns]
            
            # Ensure we have a Position column
            # On the career page, it's usually the last column
            if key == "batters":
                df.rename(columns={df.columns[-1]: 'PosSummary'}, inplace=True)

            df = df.dropna(subset=['Name'])
            df = df[~df['Name'].str.contains("Name|Total|Rank", na=False)]
            
            df.to_csv(f'mets_{key}.csv', index=False, encoding='utf-8-sig')
            print(f"✅ Saved {len(df)} {key}.")
            
        except Exception as e:
            print(f"❌ Scraper Error: {e}")

if __name__ == "__main__":
    scrape_mets_history()
