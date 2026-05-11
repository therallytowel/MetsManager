# 1. RECRUIT FIELDERS (C, 1B, 2B, 3B, SS, LF, CF, RF)
    # Each tuple is (Numerical Code, Letter Code, Position Name)
    field_needs = [
        ('2', 'C', 'C'), 
        ('3', '1B', '1B'), 
        ('4', '2B', '2B'), 
        ('5', '3B', '3B'), 
        ('6', 'SS', 'SS'), 
        ('7', 'LF', 'LF'), 
        ('8', 'CF', 'CF'), 
        ('9', 'RF', 'RF')
    ]
    final_roster = []
    used_names = set()

    for num_code, let_code, pos_name in field_needs:
        # We look for the Number OR the Letter code (e.g., '7' or 'LF')
        mask = (batters_df[pos_col].str.contains(num_code, na=False) | 
                batters_df[pos_col].str.contains(let_code, na=False))
        
        qualified_pool = batters_df[mask & ~batters_df['Name'].isin(used_names)]
        
        if not qualified_pool.empty:
            selection = qualified_pool.sample(1).iloc[0]
            used_names.add(selection['Name'])
            
            # Calculate hitting value for batting order
            obp = pd.to_numeric(selection['OBP'], errors='coerce') or 0
            slg = pd.to_numeric(selection['SLG'], errors='coerce') or 0
            final_roster.append({'Name': selection['Name'], 'Pos': pos_name, 'Val': (obp * 1.2) + slg})
        else:
            print(f"⚠️ SCOUTING REPORT: No player found for {pos_name}")

    # 2. RECRUIT DH (Strictly No Pitchers)
    # We exclude anyone whose position contains 'P'
    dh_pool = batters_df[~batters_df['Name'].isin(used_names) & 
                         ~batters_df[pos_col].str.contains('P', na=False)]
    
    if not dh_pool.empty:
        selection = dh_pool.sample(1).iloc[0]
        used_names.add(selection['Name'])
        obp = pd.to_numeric(selection['OBP'], errors='coerce') or 0
        slg = pd.to_numeric(selection['SLG'], errors='coerce') or 0
        final_roster.append({'Name': selection['Name'], 'Pos': 'DH', 'Val': (obp * 1.2) + slg})
