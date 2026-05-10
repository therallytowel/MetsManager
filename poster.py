try:
        batters_df = pd.read_csv('mets_batters.csv')
        pitchers_df = pd.read_csv('mets_pitchers.csv')
        
        # Standardize position column if needed
        if 'Pos Summary' not in batters_df.columns and 'Pos' in batters_df.columns:
            batters_df.rename(columns={'Pos': 'Pos Summary'}, inplace=True)
            
        # Filter pitchers
        if 'Pos Summary' in batters_df.columns:
            batters_df = batters_df[batters_df['Pos Summary'] != 'P'].copy()
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    # 2. Lineup Selection Logic
    lineup_sample = batters_df.sample(min(9, len(batters_df))).copy()
    
    # Handle missing columns gracefully
    if 'Pos Summary' in lineup_sample.columns:
        lineup_sample['PRIMARY_POS'] = lineup_sample['Pos Summary'].apply(get_primary_pos)
        lineup_sample['POS_COUNT'] = lineup_sample['Pos Summary'].astype(str).str.len()
    else:
        lineup_sample['PRIMARY_POS'] = 'DH'
        lineup_sample['POS_COUNT'] = 1
