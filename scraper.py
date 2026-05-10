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
            all_tables = pd.read_html(io.StringIO(response.text))
            
            df = None
            for table in all_tables:
                cols = table.columns.tolist()
                
                if category == 'batters':
                    # A true batter table MUST have AB and HR, and NOT have IP (Innings Pitched)
                    if 'AB' in cols and 'HR' in cols and 'IP' not in cols:
                        df = table
                        print(f"Found the real Batting table with {len(table)} rows.")
                        break
                
                elif category == 'pitchers':
                    # A pitcher table MUST have IP and ERA
                    if 'IP' in cols and 'ERA' in cols:
                        df = table
                        print(f"Found the real Pitching table with {len(table)} rows.")
                        break
            
            if df is None:
                print(f"⚠️ Warning: Could not find specific {category} table. Falling back.")
                df = all_tables[0]

            # Clean names and remove totals
            df['Name'] = df['Name'].str.replace(r'[*#?]', '', regex=True).str.strip()
            df = df[~df['Name'].isin(['Team Totals', 'Name', 'Totals', 'Rank'])]
            
            # Standardize Position column
            if 'Pos Summary' not in df.columns and 'Pos' in df.columns:
                df.rename(columns={'Pos': 'Pos Summary'}, inplace=True)
            
            df.to_csv(f"mets_{category}.csv", index=False)
            print(f"✅ Saved mets_{category}.csv")
            time.sleep(2)
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    scrape_mets_data()
