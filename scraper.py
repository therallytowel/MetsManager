import pandas as pd
import requests
from bs4 import BeautifulSoup
import io

def scrape_mets_data():
    url = "https://www.baseball-reference.com/teams/NYM/bat.shtml"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    print("Scouting the Amazins... (Accessing Baseball-Reference)")
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    try:
        # Find the specific 'Standard Batting' table
        table = soup.find('table', {'id': 'players_standard_batting'})
        
        if table:
            df = pd.read_html(io.StringIO(str(table)))[0]
        else:
            # Fallback: Baseball-Ref sometimes comments out tables. Let's find it in the comments.
            import re
            comments = soup.find_all(string=lambda text: isinstance(text, pd.Series) or True)
            for comment in comments:
                if 'id="players_standard_batting"' in comment:
                    df = pd.read_html(io.StringIO(comment))[0]
                    break
        
        # Clean columns
        df.columns = [str(c).strip() for c in df.columns]
        
        # Map whatever position column they gave us to 'Pos Summary'
        possible_pos_cols = ['Pos Summary', 'Pos', 'Positions']
        for col in possible_pos_cols:
            if col in df.columns:
                df.rename(columns={col: 'Pos Summary'}, inplace=True)
                break

        # Final Cleanup
        df = df.dropna(subset=['Name'])
        df = df[~df['Name'].str.contains("Name|Total|Rank", na=False)]
        
        df.to_csv('mets_batters.csv', index=False, encoding='utf-8-sig')
        print(f"✅ Success! Created mets_batters.csv with {len(df)} players.")
        
    except Exception as e:
        print(f"❌ Scraper failed: {e}")

if __name__ == "__main__":
    scrape_mets_data()
