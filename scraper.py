import pandas as pd
import requests
from bs4 import BeautifulSoup
import io

def scrape_mets_data():
    # URL for all-time Mets players (Batting)
    url = "https://www.baseball-reference.com/teams/NYM/bat.shtml"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    print("Scouting the Amazins... (Accessing Baseball-Reference)")
    response = requests.get(url, headers=headers)
    
    # Extract table from HTML
    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table', {'id': 'players_standard_batting'})
    
    if not table:
        print("Error: Could not find the batting table.")
        return

    # Convert to DataFrame
    df = pd.read_html(io.StringIO(str(table)))[0]

    # Clean column names
    df.columns = [str(c).strip() for c in df.columns]
    
    # Filter out junk rows
    df = df[df['Name'].notna()]
    df = df[~df['Name'].str.contains("Name|Total|Rank", na=False)]

    # Ensure 'Pos Summary' is the name we use
    if 'Pos Summary' not in df.columns and 'Pos' in df.columns:
        df.rename(columns={'Pos': 'Pos Summary'}, inplace=True)

    # Save to CSV
    df.to_csv('mets_batters.csv', index=False, encoding='utf-8-sig')
    print(f"✅ Success! Created mets_batters.csv with {len(df)} players.")

if __name__ == "__main__":
    scrape_mets_data()
