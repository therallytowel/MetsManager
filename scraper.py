import pandas as pd
import requests
import io
import time

def scrape_mets_data():
    # Using a modern header to ensure Baseball-Reference doesn't block the request
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
            # io.StringIO handles the HTML content for modern Pandas versions
            all_tables = pd.read_html(io.StringIO(response.text))
            
            # Find the specific table we need by checking for key columns
            df = None
            for table in all_tables:
                if category == 'batters' and 'Pos Summary' in table.columns:
                    df = table
                    break
                elif category == 'pitchers' and 'W' in table.columns and 'GS' in table.columns:
                    df = table
                    break
            
            # If the search failed, fall back to the first table
            if df is None:
                print(f"⚠️ Warning: Specific {category} table not found by headers. Using fallback.")
                df = all_tables[0]

            # 1. Clean player names (remove symbols like * or #)
            df['Name'] = df['Name'].str.replace(r'[*#?]', '', regex=True).str.strip()
            
            # 2. Drop "Team Totals" and non-player rows
            df = df[df['Name'] != 'Team Totals']
            df = df[df['Name'] != 'Name'] # Drops header-repeat rows
            
            # Save to CSV
            filename = f"mets_{category}.csv"
            df.to_csv(filename, index=False)
            print(f"✅ Created {filename}")
            
            # Polite 5-second pause
            if category == 'batters':
                time.sleep(5)
                
        except Exception as e:
            print(f"❌ Error scraping {category}: {e}")

if __name__ == "__main__":
    scrape_mets_data()
