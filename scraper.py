import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import re

def scrape_mets_franchise():
    # These URLs lead to the full list of every player in Mets history
    urls = {
        "batters": "https://www.baseball-reference.com/teams/NYM/bat.shtml",
        "pitchers": "https://www.baseball-reference.com/teams/NYM/pitch.shtml"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    for key, url in urls.items():
        print(f"Scouting the FULL {key} pool...")
        try:
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code != 200:
                print(f"❌ Denied! B-Ref returned status {response.status_code}")
                continue

            # We use a broader search for the table since they rotate IDs to stop bots
            soup = BeautifulSoup(response.text, 'html.parser')
            # Look for ANY table in the page source (including commented ones)
            all_html = response.text.replace('', '')
            
            # Use lxml as it's the most robust parser available
            dfs = pd.read_html(io.StringIO(all_html), flavor='lxml')
            
            # Find the biggest table (that's our player list)
            df = max(dfs, key=len)
            
            # Clean headers
            df.columns = [re.sub(r'\W+', '', str(c)) for c in df.columns]
            
            # Ensure 'Name' and 'Pos' exist
            if 'Name' not in df.columns:
                df.rename(columns={df.columns[1]: 'Name'}, inplace=True)
            
            # Map the Position Summary column
            pos_col = next((c for c in df.columns if 'Pos' in c), df.columns[-1])
            df.rename(columns={pos_col: 'PosSummary'}, inplace=True)

            # Cleanup
            df = df.dropna(subset=['Name'])
            df = df[~df['Name'].str.contains("Name|Total|Rank", na=False)]
            
            df.to_csv(f'mets_{key}.csv', index=False, encoding='utf-8-sig')
            print(f"✅ Success! Saved {len(df)} {key} to the pool.")
            
        except Exception as e:
            print(f"❌ Scraper Error: {e}")

if __name__ == "__main__":
    scrape_mets_franchise()
