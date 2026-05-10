import pandas as pd
import requests
import io
import time

def scrape_mets_data():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    urls = {
        'batters': "https://www.baseball-reference.com/teams/NYM/bat.shtml",
        'pitchers': "https://www.baseball-reference.com/teams/NYM/pitch.shtml"
    }
    
    for category, url in urls.items():
        print(f"Connecting to Baseball-Reference for {category}...")
        try:
            response = requests.get(url, headers=headers, timeout=30)
            # Use thousands and decimal parameters to help pandas parse correctly
            all_tables = pd.read_html(io.StringIO(response.text))
            
            df = None
            for table in all_tables:
                # BATTER CHECK: Must have 'Name' and either 'Pos Summary' or 'Pos'
                if category == 'batters':
                    cols = table.columns.tolist()
                    if 'Name' in cols and any('Pos' in c for c in cols):
                        df = table
                        break
                # PITCHER CHECK: Must have 'IP'
                elif category == 'pitchers':
                    if 'IP' in table.columns:
                        df = table
                        break
            
            if df is None:
                df = all_tables[0]

            # Clean column names (sometimes they are MultiIndex)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(-1)

            # Clean names and remove totals
            df['Name'] = df['Name'].str.replace(r'[*#?]', '', regex=True).str.strip()
            df = df[~df['Name'].isin(['Team Totals', 'Name', 'Totals'])]
            
            # Standardize Position column name
            if 'Pos Summary' not in df.columns and 'Pos' in df.columns:
                df.rename(columns={'Pos': 'Pos Summary'}, inplace=True)
            
            df.to_csv(f"mets_{category}.csv", index=False)
            print(f"✅ Created mets_{category}.csv")
            time.sleep(2)
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    scrape_mets_data()
