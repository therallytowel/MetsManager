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
                # HITTER CHECK: Must have 'AB' (At Bats) and 'Pos Summary'
                if category == 'batters':
                    if 'AB' in table.columns and 'Pos Summary' in table.columns:
                        df = table
                        break
                # PITCHER CHECK: Must have 'IP' (Innings Pitched)
                elif category == 'pitchers':
                    if 'IP' in table.columns and 'ERA' in table.columns:
                        df = table
                        break
            
            if df is None:
                print(f"⚠️ Warning: Could not isolate {category} table. Using fallback.")
                df = all_tables[0]

            # Clean names and remove totals
            df['Name'] = df['Name'].str.replace(r'[*#?]', '', regex=True).str.strip()
            df = df[df['Name'] != 'Team Totals']
            df = df[df['Name'] != 'Name']
            
            df.to_csv(f"mets_{category}.csv", index=False)
            print(f"✅ Created mets_{category}.csv")
            time.sleep(5)
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    scrape_mets_data()
