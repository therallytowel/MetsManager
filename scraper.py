import pandas as pd
import requests
import io

def scrape_mets_data():
    url = "https://www.baseball-reference.com/teams/NYM/bat.shtml"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    print("Scouting the Amazins...")
    response = requests.get(url, headers=headers)
    
    try:
        # 1. Grab the table
        all_tables = pd.read_html(io.StringIO(response.text))
        df = all_tables[0]
        
        # 2. Clean the column names
        df.columns = [str(c).strip() for c in df.columns]
        
        # 3. Target the Position Summary
        # B-Ref stores position history in 'Pos Summary' or 'Pos'
        pos_key = 'Pos Summary' if 'Pos Summary' in df.columns else 'Pos'
        
        # 4. THE FIX: Explicitly tag Outfielders
        # We look for 7, 8, or 9 in the summary and add 'LF', 'CF', 'RF' to the text
        def clarify_pos(row):
            pos_str = str(row[pos_key])
            output = pos_str
            if '7' in pos_str: output += " LF"
            if '8' in pos_str: output += " CF"
            if '9' in pos_str: output += " RF"
            return output

        df['Pos Summary'] = df.apply(clarify_pos, axis=1)
            
        # 5. Filter out the noise
        df = df.dropna(subset=['Name'])
        df = df[~df['Name'].str.contains("Name|Total|Rank", na=False)]
        
        # 6. Save it
        df.to_csv('mets_batters.csv', index=False, encoding='utf-8-sig')
        print(f"✅ Success! Scoped {len(df)} players with verified positions.")
    except Exception as e:
        print(f"❌ Scraper failed: {e}")

if __name__ == "__main__":
    scrape_mets_data()
