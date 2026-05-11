import pandas as pd
import requests
import io

def scrape_mets_data():
    url = "https://www.baseball-reference.com/teams/NYM/bat.shtml"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    print("Scouting the Amazins...")
    response = requests.get(url, headers=headers)
    
    # We use a trick here: read_html can find tables directly from the text
    # We are looking for the one with 'All-Time' data or the main roster
    try:
        all_tables = pd.read_html(io.StringIO(response.text))
        # Usually the main batting table is the first or second one
        df = all_tables[0]
        
        # Clean column names
        df.columns = [str(c).strip() for c in df.columns]
        
        # If 'Pos Summary' is missing, check 'Pos'
        if 'Pos Summary' not in df.columns and 'Pos' in df.columns:
            df.rename(columns={'Pos': 'Pos Summary'}, inplace=True)
            
        # Drop rows that don't have a name
        df = df.dropna(subset=['Name'])
        df = df[~df['Name'].str.contains("Name|Total|Rank", na=False)]
        
        df.to_csv('mets_batters.csv', index=False, encoding='utf-8-sig')
        print(f"✅ Success! Found {len(df)} players.")
        print(f"Columns found: {list(df.columns)}")
    except Exception as e:
        print(f"❌ Scraper failed: {e}")

if __name__ == "__main__":
    scrape_mets_data()
