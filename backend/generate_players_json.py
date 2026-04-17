#!/usr/bin/env python3
"""
生成前端需要的 players.json 文件
"""

import pandas as pd
import json
from pathlib import Path

def load_data():
    """加载所有数据文件"""
    data_dir = Path('data')
    
    # 主球员数据
    df = pd.read_csv(data_dir / 'premier_league_players_merged_final.csv')
    
    # 中文名称
    with open(data_dir / 'player_chinese_names.json', 'r', encoding='utf-8') as f:
        chinese_names = json.load(f)
    
    # 成就数据
    achievements_data = {
        'appearances_250': pd.read_csv(data_dir / 'epl_players_appearances_230plus.csv'),
        'goals_100': pd.read_csv(data_dir / 'pl_100_goals_club.csv'),
        'clean_sheets_100': pd.read_csv(data_dir / 'pl_100_clean_sheets_gk.csv'),
        'golden_boots': pd.read_csv(data_dir / 'pl_golden_boot_winners.csv'),
        'golden_gloves': pd.read_csv(data_dir / 'pl_golden_glove_winners.csv'),
        'player_of_season': pd.read_csv(data_dir / 'pl_player_of_season_winners.csv'),
        'three_plus_titles': pd.read_csv(data_dir / 'pl_players_3plus_titles.csv')
    }
    
    return df, chinese_names, achievements_data

def process_achievements(player_data, achievements_data):
    """处理球员成就数据"""
    achievements = {}
    
    # 250+ 出场
    for _, row in achievements_data['appearances_250'].iterrows():
        player_id = row['player_id']
        if player_id not in achievements:
            achievements[player_id] = []
        achievements[player_id].append({
            'type': '出场250次',
            'detail': f"{row['total_appearances']}场"
        })
    
    # 100+ 进球
    for _, row in achievements_data['goals_100'].iterrows():
        player_id = row['player_id']
        if player_id not in achievements:
            achievements[player_id] = []
        achievements[player_id].append({
            'type': '100',
            'detail': f"{row['Premier League total goals']}0"
        })
    
    # 100+ 零封
    for _, row in achievements_data['clean_sheets_100'].iterrows():
        player_id = row['player_id']
        if player_id not in achievements:
            achievements[player_id] = []
        achievements[player_id].append({
            'type': '100',
            'detail': f"{row['Premier League total clean sheets']}"
        })
    
    # 金靴奖
    for _, row in achievements_data['golden_boots'].iterrows():
        player_id = row['player_id']
        if player_id not in achievements:
            achievements[player_id] = []
        achievements[player_id].append({
            'type': '',
            'detail': str(row['Season'])
        })
    
    # 金手套奖
    for _, row in achievements_data['golden_gloves'].iterrows():
        player_id = row['player_id']
        if player_id not in achievements:
            achievements[player_id] = []
        achievements[player_id].append({
            'type': '金手套奖',
            'detail': str(row['season'])
        })
    
    # 年度最佳球员
    for _, row in achievements_data['player_of_season'].iterrows():
        player_id = row['player_id']
        if player_id not in achievements:
            achievements[player_id] = []
        achievements[player_id].append({
            'type': '年度最佳',
            'detail': str(row['season'])
        })
    
    # 3+ 冠军
    for _, row in achievements_data['three_plus_titles'].iterrows():
        player_id = row['player_id']
        if player_id not in achievements:
            achievements[player_id] = []
        achievements[player_id].append({
            'type': '三冠王',
            'detail': row['clubs']
        })
    
    return achievements

def generate_players_json():
    """生成最终的 players.json 文件"""
    print("Loading data...")
    df, chinese_names, achievements_data = load_data()
    
    print("Processing achievements...")
    achievements = process_achievements(df, achievements_data)
    
    print("Generating players data...")
    players = []
    
    for _, row in df.iterrows():
        player_id = row['player_id']
        
        # 中文名称
        cn_name = chinese_names.get(str(player_id), {}).get('name_cn', row['name'])
        
        # 俱乐部列表
        clubs = []
        if pd.notna(row['clubs']):
            clubs = [club.strip() for club in str(row['clubs']).split(',') if club.strip()]
        
        # 球员状态
        if row['is_retired']:
            player_status = 'retired'
        elif row['total_appearances'] >= 250:
            player_status = 'hall_of_fame'
        else:
            player_status = 'active_pl'
        
        player = {
            'id': player_id,
            'name_en': row['name'],
            'name_cn': cn_name,
            'nationality': row['nationality'],
            'position': row.get('position', ''),
            'clubs': clubs,
            'total_appearances': row['total_appearances'],
            'player_status': player_status,
            'achievements': achievements.get(player_id, [])
        }
        
        # 添加其他统计数据
        if 'goals' in row and pd.notna(row['goals']):
            player['goals'] = int(row['goals'])
        if 'clean_sheets' in row and pd.notna(row['clean_sheets']):
            player['clean_sheets'] = int(row['clean_sheets'])
        
        players.append(player)
    
    # 保存到前端目录
    output_path = Path('../frontend/public/data/players.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(players, f, ensure_ascii=False, indent=2)
    
    print(f"Generated {len(players)} players to {output_path}")
    print("Done!")

if __name__ == "__main__":
    generate_players_json()
