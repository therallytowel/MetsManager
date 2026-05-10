import pandas as pd
import requests
import io
import time

def scrape_mets_data():
    # We use a User-Agent header so Baseball-Reference doesn't block the request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }
    
    urls = {
        'batters': "https://www.baseball-reference.com/teams/NYM/bat.shtml",
        'pitchers': "https://www.baseball-reference.com/teams/NYM/pitch.shtml"
    }
    
    for category, url in urls.items():
        print(f"Connecting to Baseball-Reference for {category}...")
        try:
            response = requests.get(url, headers=headers, timeout=30)
            # read_html returns a list of dataframes; the first one [0] is the cumulative stats
            df = pd.read_html(io.StringIO(response.text))[0]
            
            # 1. Clean player names (remove *, #, ?, and extra spaces)
            df['Name'] = df['Name'].str.replace(r'[*#?]', '', regex=True).str.strip()
            
            # 2. Filter out 'Team Totals' or header rows that don't have a Rank (Rk)
            df = df[df['Rk'].notna()]
            
            # Save to CSV
            filename = f"mets_{category}.csv"
            df.to_csv(filename, index=False)
            print(f"✅ Success! Created {filename}")
            
            # Wait 5 seconds before the next request to be respectful of the server
            if category == 'batters':
                time.sleep(5)
                
        except Exception as e:
            print(f"❌ Error scraping {category}: {e}")

if __name__ == "__main__":
    scrape_mets_data()
