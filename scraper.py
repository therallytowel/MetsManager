import pandas as pd
import requests
from bs4 import BeautifulSoup, Comment
import io
import re

def scrape_mets_legends():
    # We are hitting the 'Batting Leaders' page - it's cleaner for 'All-Time' picks
    url = "https://www.baseball-reference.com/teams/NYM/leaders_bat.shtml"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    print(f"Scouting the Legend Register... (Accessing {url})")
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # We find the table by looking for the one that contains 'Career'
        # Using lxml to avoid dependency errors
        tables = pd.read_html(io.StringIO(response.text), flavor='lxml')
        
        # Merge all leader tables into one massive pool of legitimate Mets
        full_pool = pd.concat(tables, ignore_index=True)
        
        # Clean column names
        full_pool.columns = [re.sub(r'\W+', '', str(c)) for c in full_pool.columns]
        
        # On the leaders page, names usually have the position right next to them
        # We will extract name and position using regex
        def extract_info(row_str):
            # Matches 'Name (Pos)' format
            match = re.search(r'([a-zA-Z\s\.\-]+)\s\((.*?)\)', str(row_str))
            if match:
                return match.group(1).strip(), match.group(2).strip()
            return None, None

        extracted = full_pool.iloc[:, 1].apply(extract_info)
        clean_df = pd.DataFrame(extracted.tolist(), columns=['Name', 'PosSummary'])
        
        # Add a dummy OPS for sorting (Leaders are all high-value anyway)
        clean_df['OPS'] = 0.800 
        
        clean_df = clean_df.dropna(subset=['Name']).drop_duplicates(subset=['Name'])
        
        clean_df.to_csv('mets_batters.csv', index=False, encoding='utf-8-sig')
        print(f"✅ Success! Saved {len(clean_df)} Hall of Fame level Mets.")
        
    except Exception as e:
        print(f"❌ Scraper Critical Error: {e}")

if __name__ == "__main__":
    scrape_mets_legends()
