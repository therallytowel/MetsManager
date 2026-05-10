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
            # io.StringIO handles the HTML string for pandas
            all_tables = pd.read_html(io.StringIO(response.text))
            
            df = None
            for table in all_tables:
                cols = table.columns.tolist()
                
                if category == 'batters':
                    # Logic: Must have AB (At Bats) and NOT have IP (Innings Pitched)
                    # This ensures we don't accidentally grab a pitching table
                    if 'AB' in cols and 'IP' not in cols:
                        df = table
                        break
                
                elif category == 'pitchers':
                    # Logic: Must have IP and ERA
                    if 'IP' in cols and 'ERA' in cols:
                        df = table
                        break
            
            # Fallback if specific logic fails
            if df is None:
                df = all_tables[0]

            # --- DATA CLEANING ---
            # Remove the characters B-Ref uses for lefties/switch hitters
            # We keep the name string intact otherwise (preserving suffixes like Jr./Sr.)
            df['Name'] = df['Name'].str.replace(r'[*#?]', '', regex=True).str.strip()
            
            # Remove rows that are just sub-headers or team totals
            df = df[~df['Name'].isin(['Team Totals', 'Name', 'Totals', 'Rank'])]
            
            # Standardize Position column name for the poster.py "hunt"
            if 'Pos Summary' not in df.columns and 'Pos' in df.columns:
                df.rename(columns={'Pos': 'Pos Summary'}, inplace=True)
            
            # CRITICAL: Save with utf-8-sig encoding.
            # This handles accents (like Canó) correctly in Windows-based CSV viewers.
            df.to_csv(f"mets_{category}.csv", index=False, encoding='utf-8-sig')
            print(f"✅ Successfully saved mets_{category}.csv")
            
            # Polite delay between requests
            time.sleep(2)
                
        except Exception as e:
            print(f"❌ Error scraping {category}: {e}")

if __name__ == "__main__":
    scrape_mets_data()
