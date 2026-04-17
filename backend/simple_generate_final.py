#!/usr/bin/env python3
import pandas as pd
import json
from pathlib import Path

def generate_simple_players_json():
    """Generate a simple players.json for frontend"""
    
    # Load main player data
    df = pd.read_csv('data/premier_league_players_merged_final.csv')
    
    # Load Chinese names
    with open('data/player_chinese_names.json', 'r', encoding='utf-8') as f:
        chinese_names = json.load(f)
    
    # Load achievements data
    appearances = pd.read_csv('data/epl_players_appearances_230plus.csv')
    goals = pd.read_csv('data/pl_100_goals_club.csv')
    clean_sheets = pd.read_csv('data/pl_100_clean_sheets_gk.csv')
    golden_boots = pd.read_csv('data/pl_golden_boot_winners.csv')
    golden_gloves = pd.read_csv('data/pl_golden_glove_winners.csv')
    player_of_season = pd.read_csv('data/pl_player_of_season_winners.csv')
    three_titles = pd.read_csv('data/pl_players_3plus_titles.csv')
    
    players = []
    
    for _, row in df.iterrows():
        player_id = row['player_id']
        
        # Get Chinese name
        cn_name = chinese_names.get(str(player_id), {}).get('name_cn', row['player_name'])
        
        # Parse clubs - fix: split by Chinese semicolon
        clubs = []
        if pd.notna(row['xlsx_clubs']):
            clubs = [club.strip() for club in str(row['xlsx_clubs']).split(';') if club.strip()]
        
        # Determine player status
        if row['multi_is_retired'] == 'yes':
            player_status = 'retired'
        elif row['appearances'] >= 250:
            player_status = 'hall_of_fame'
        else:
            player_status = 'active_pl'
        
        # Collect achievements
        achievements = []
        
        # 250+ appearances
        if player_id in appearances['player_id'].values:
            app_row = appearances[appearances['player_id'] == player_id].iloc[0]
            achievements.append({
                'type': '250+ Appearances',
                'detail': f"{app_row['total_appearances']} apps"
            })
        
        # 100+ goals
        if player_id in goals['player_id'].values:
            goal_row = goals[goals['player_id'] == player_id].iloc[0]
            achievements.append({
                'type': '100+ Goals',
                'detail': f"{goal_row['Premier League total goals']} goals"
            })
        
        # 100+ clean sheets
        if player_id in clean_sheets['player_id'].values:
            cs_row = clean_sheets[clean_sheets['player_id'] == player_id].iloc[0]
            achievements.append({
                'type': '100+ Clean Sheets',
                'detail': f"{cs_row['Premier League total clean sheets']} clean sheets"
            })
        
        # Golden boots
        player_golden_boots = golden_boots[golden_boots['player_id'] == player_id]
        for _, gb_row in player_golden_boots.iterrows():
            achievements.append({
                'type': 'Golden Boot',
                'detail': str(gb_row['Season'])
            })
        
        # Golden gloves
        player_gg = golden_gloves[golden_gloves['player_id'] == player_id]
        for _, gg_row in player_gg.iterrows():
            achievements.append({
                'type': 'Golden Glove', 
                'detail': str(gg_row['Season'])
            })
        
        # Player of season
        player_pos = player_of_season[player_of_season['player_id'] == player_id]
        for _, pos_row in player_pos.iterrows():
            achievements.append({
                'type': 'Player of the Year',
                'detail': str(pos_row['Season'])
            })
        
        # 3+ titles
        if player_id in three_titles['player_id'].values:
            title_row = three_titles[three_titles['player_id'] == player_id].iloc[0]
            achievements.append({
                'type': 'Multiple Champion',
                'detail': str(title_row['clubs'])
            })
        
        player = {
            'id': player_id,
            'name_en': row['player_name'],
            'name_cn': cn_name,
            'nationality': row['nationality'],
            'position': row.get('position', ''),
            'clubs': clubs,
            'total_appearances': row['appearances'],
            'player_status': player_status,
            'achievements': achievements,
            # Add missing fields that frontend expects
            'goals': int(row['100goalsclub_Premier League total goals']) if pd.notna(row.get('100goalsclub_Premier League total goals')) else None,
            'clean_sheets': int(row['100cleansheetsgk_Premier League total clean sheets']) if pd.notna(row.get('100cleansheetsgk_Premier League total clean sheets')) else None,
            'single_club_appearances': None,  # Would need to calculate from multi_team data
            'single_club_name': None  # Would need to determine from multi_team data
        }
        
        players.append(player)
    
    # Save to frontend public directory
    output_path = Path('../frontend/public/data/players.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(players, f, ensure_ascii=False, indent=2)
    
    print(f"Generated {len(players)} players to {output_path}")

if __name__ == "__main__":
    generate_simple_players_json()
