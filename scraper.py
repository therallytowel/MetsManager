import pandas as pd
import requests
from bs4 import BeautifulSoup
import io
import re

def scrape_mets_data():
    url = "https://www.baseball-reference.com/teams/NYM/bat.shtml"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    print("Scouting the Amazins... (Accessing Baseball-Reference)")
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    df = pd.DataFrame() # Initialize empty so we don't get the 'referenced before assignment' error

    try:
        # Look for the table in the clear HTML first
        table = soup.find('table', {'id': 'players_standard_batting'})
        
        if table:
            df = pd.read_html(io.StringIO(str(table)))[0]
        else:
            # If it's hidden in comments (typical for B-Ref), hunt it down
            comments = soup.find_all(string=lambda text: isinstance(text, str))
            for comment in comments:
                if 'id="players_standard_batting"' in comment:
                    # Clean up the comment markers before reading
                    clean_html = comment.replace('', '')
                    df = pd.read_html(io.StringIO(clean_html))[0]
                    break
        
        if df.empty:
            print("❌ Failed to find the batting table in HTML or comments.")
            return

        # CLEANING: Remove invisible characters (\xa0) from column names immediately
        df.columns = [re.sub(r'\s+', ' ', str(c).strip()) for c in df.columns]
        
        # Filter out headers and junk
        df = df.dropna(subset=['Name'])
        df = df[~df['Name'].str.contains("Name|Total|Rank", na=False)]
        
        df.to_csv('mets_batters.csv', index=False, encoding='utf-8-sig')
        print(f"✅ Success! Created mets_batters.csv with {len(df)} players.")
        
    except Exception as e:
        print(f"❌ Scraper failed: {e}")

if __name__ == "__main__":
    scrape_mets_data()
