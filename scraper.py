import pandas as pd
import requests
from bs4 import BeautifulSoup, Comment
import io
import re

def scrape_full_pool():
    urls = {
        "batters": "https://www.baseball-reference.com/teams/NYM/bat.shtml",
        "pitchers": "https://www.baseball-reference.com/teams/NYM/pitch.shtml"
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for key, url in urls.items():
        print(f"Scouting the FULL {key} register...")
        try:
            response = requests.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Baseball-Reference hides career tables in comments. This rips them out.
            comments = soup.find_all(string=lambda text: isinstance(text, Comment))
            
            table_html = ""
            table_id = f"players_career_{key}"
            
            for comment in comments:
                if table_id in comment:
                    table_html = comment
                    break
            
            if not table_html:
                print(f"⚠️ Could not find hidden table {table_id}. Trying secondary IDs...")
                # Fallback to any table if specific ID fails
                for comment in comments:
                    if "<table" in comment:
                        table_html = comment
                        break

            df = pd.read_html(io.StringIO(table_html), flavor='lxml')[0]
            
            # Force clean column names
            df.columns = [re.sub(r'\W+', '', str(c)) for c in df.columns]
            
            # Map the position column regardless of what B-Ref calls it
            if key == "batters":
                # It's usually 'PosSummary' or 'Pos' or the last column
                pos_col = next((c for c in df.columns if 'Pos' in c), df.columns[-1])
                df.rename(columns={pos_col: 'PosSummary'}, inplace=True)

            df = df.dropna(subset=['Name'])
            df = df[~df['Name'].str.contains("Name|Total|Rank", na=False)]
            
            df.to_csv(f'mets_{key}.csv', index=False, encoding='utf-8-sig')
            print(f"✅ Success! Saved {len(df)} {key}.")
            
        except Exception as e:
            print(f"❌ Scraper Error: {e}")

if __name__ == "__main__":
    scrape_full_pool()
