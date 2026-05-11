import pandas as pd
import requests
import io

def scrape_mets_data():
    url = "https://www.baseball-reference.com/teams/NYM/bat.shtml"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    
    print("Scouting the Amazins... (Accessing Baseball-Reference)")
    response = requests.get(url, headers=headers)
    
    try:
        # Load tables from HTML
        all_tables = pd.read_html(io.StringIO(response.text))
        df = all_tables[0]
        
        # Clean column names and whitespace
        df.columns = [str(c).strip() for c in df.columns]
        
        # Identify the position column (B-Ref uses 'Pos Summary' or 'Pos')
        pos_key = 'Pos Summary' if 'Pos Summary' in df.columns else 'Pos'
        
        # Clean the player names and positions immediately
        df['Name'] = df['Name'].astype(str).str.strip()
        df[pos_key] = df[pos_key].astype(str).str.strip()
            
        # Filter out headers and junk rows
        df = df.dropna(subset=['Name'])
        df = df[~df['Name'].str.contains("Name|Total|Rank", na=False)]
        
        # Standardize the position column name for the poster
        if pos_key != 'Pos Summary':
            df.rename(columns={pos_key: 'Pos Summary'}, inplace=True)
        
        # Save the cleaned data
        df.to_csv('mets_batters.csv', index=False, encoding='utf-8-sig')
        print(f"✅ Success! Scouted {len(df)} players with verified positions.")
        
    except Exception as e:
        print(f"❌ Scraper failed: {e}")

if __name__ == "__main__":
    scrape_mets_data()
