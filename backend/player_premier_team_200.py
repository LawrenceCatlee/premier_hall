import requests
from bs4 import BeautifulSoup
from player_name_normalizer import (
    normalize_player_name,
    clean_player_name,
    clean_text
)
from player_name_mapper import standardize_player_name
from pulselive_data import get_pulselive_player_index
import pandas as pd
import re
import time
import os

def scrape_team_players(team_name, url):
    """
    爬取单个球队的出场数>=180的球员信息，包含player_id匹配
    """
    print(f"\n正在爬取 {team_name} 的数据...")
    
    # 获取Pulselive球员索引用于player_id匹配
    print("加载Pulselive球员索引...")
    pl_players_df = get_pulselive_player_index().copy()

    # 只保留 Pulselive 中 appearances >= 180 的球员
    if 'appearances' not in pl_players_df.columns:
        raise KeyError("Pulselive 索引中没有 appearances 列，无法按 appearances>=180 过滤")

    pl_players_df['appearances'] = pd.to_numeric(pl_players_df['appearances'], errors='coerce')
    pl_players_df = pl_players_df[pl_players_df['appearances'] >= 180].copy()

    print(f"Pulselive 过滤后剩余 {len(pl_players_df)} 名球员")

    pl_name_to_id = dict(zip(
        pl_players_df['player_name'].str.lower().str.strip(),
        pl_players_df['player_id']
    ))
    
    # 设置请求头，模拟浏览器访问
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    try:
        # 发送请求
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # 解析HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 查找表格
        table = soup.find('table', class_='items')
        if not table:
            table = soup.find('table')
        
        if not table:
            print(f"未找到 {team_name} 的数据表格")
            return []
        
        # 存储结果和已处理的球员名字，避免重复
        players_data = []
        processed_players = set()
        
        # 查找所有行（跳过表头）
        rows = table.find_all('tr')[1:]  # 跳过第一行表头
        
        for row in rows:
            try:
                # 获取所有td单元格
                cells = row.find_all('td')
                
                # 跳过没有图片的行（这些通常是排名行或其他行）
                if len(cells) < 2:
                    continue
                
                # 查找包含球员图片的单元格
                player_img = None
                player_name = ""
                player_cell_index = -1
                
                for i, cell in enumerate(cells):
                    img = cell.find('img', alt=True)
                    if img and img.get('alt'):
                        player_img = img
                        player_name = img.get('alt', '').strip()
                        player_cell_index = i
                        break
                
                if not player_img or not player_name:
                    continue
                
                # 避免重复处理同一个球员
                if player_name in processed_players:
                    continue
                processed_players.add(player_name)
                
                # 应用姓名标准化映射
                standardized_name = standardize_player_name(player_name)
                
                # 匹配player_id
                player_id = None
                name_variants = [
                    standardized_name.lower(),
                    player_name.lower(),
                    clean_player_name(player_name).lower()
                ]
                
                for variant in name_variants:
                    if variant in pl_name_to_id:
                        player_id = pl_name_to_id[variant]
                        break
                
                # 判断是否退役并获取当前效力球队
                is_retired = False
                current_team = None
                
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    if 'Retired' in cell_text:
                        is_retired = True
                        break
                
                # 如果没有退役，查找当前效力球队
                if not is_retired:
                    # 现役球员的当前效力球队通常在单元格1或单元格4中
                    # 单元格1格式可能是: "球员名字球队名"，单元格4只有球队名
                    for cell_idx in [1, 4]:
                        if cell_idx < len(cells):
                            cell_text = cells[cell_idx].get_text(strip=True)
                            
                            # 如果是单元格1，需要从"球员名字球队名"中提取球队名
                            if cell_idx == 1:
                                # 移除球员名字，获取剩余部分作为球队名
                                if cell_text.startswith(player_name):
                                    potential_team = cell_text[len(player_name):].strip()
                                    if (potential_team and 
                                        len(potential_team) > 2 and
                                        'Without Club' not in potential_team):
                                        current_team = potential_team
                                        break
                            # 如果是单元格4，直接使用
                            elif cell_idx == 4:
                                if (cell_text and 
                                    len(cell_text) > 2 and
                                    'Without Club' not in cell_text and
                                    cell_text != player_name):
                                    current_team = cell_text.strip()
                                    break
                
                # 提取出场数
                appearances = 0
                
                # 从球员单元格之后开始查找出场数
                for i in range(player_cell_index + 1, len(cells)):
                    cell_text = cells[i].get_text(strip=True)
                    # 寻找出场数（通常是较大的数字）
                    if cell_text.isdigit() and int(cell_text) >= 50:
                        appearances = int(cell_text)
                        break
                
                # 只保存出场数>=180的球员（捕获所有在英超有一定出场的球队）
                if appearances >= 180:
                    player_info = {
                        'player_id': player_id,  # 添加player_id
                        'team': team_name,
                        'player_name': player_name,
                        'standardized_name': standardized_name,  # 添加标准化姓名
                        'appearances': appearances,
                        'current_team': current_team,
                        'is_retired': 'yes' if is_retired else 'no'
                    }
                    players_data.append(player_info)
                    
                    id_status = f"ID: {player_id}" if player_id else "ID: 未匹配"
                    print(f"找到: {player_name} - {appearances}场 - {id_status} - 当前效力: {current_team if current_team else '未知'} - {'已退役' if is_retired else '现役'}")
            
            except Exception as e:
                print(f"处理 {team_name} 行数据时出错: {e}")
                continue
        
        return players_data
            
    except requests.exceptions.RequestException as e:
        print(f"请求 {team_name} 出错: {e}")
        return []
    except Exception as e:
        print(f"解析 {team_name} 出错: {e}")
        return []

def scrape_all_premier_league_teams():
    """
    爬取所有英超球队的球员数据
    """
    # 读取球队链接
    try:
        teams_df = pd.read_excel('data/Team_transfer_link.xlsx', header=None)
        teams_df.columns = ['team_name', 'url']
        
        # 过滤掉空行
        teams_df = teams_df.dropna()
        
        print(f"找到 {len(teams_df)} 支球队")
        
    except Exception as e:
        print(f"读取球队链接文件出错: {e}")
        return None
    
    all_players_data = []
    
    for index, row in teams_df.iterrows():
        team_name = row['team_name']
        url = row['url']
        
        # 爬取该球队的球员数据
        players_data = scrape_team_players(team_name, url)
        all_players_data.extend(players_data)
        
        # 添加延迟避免请求过于频繁
        time.sleep(2)
        
        print(f"已完成 {team_name}，找到 {len(players_data)} 名符合条件的球员")
    
    # 按球员名字分组，为每个球员分配最多3支球队
    return process_players_data(all_players_data)

def process_players_data(all_players_data):
    """
    处理球员数据，按球员名字分组并分配最多3支球队，包含player_id处理
    """
    # 按球员名字分组
    players_dict = {}
    
    for player in all_players_data:
        player_name = player['player_name']
        player_id = player['player_id']
        standardized_name = player['standardized_name']
        team_name = player['team']
        appearances = player['appearances']
        current_team = player['current_team']
        is_retired = player['is_retired']
        
        if player_name not in players_dict:
            players_dict[player_name] = {
                'player_id': player_id,  # 添加player_id
                'player_name': player_name,
                'standardized_name': standardized_name,  # 添加标准化姓名
                'teams': []
            }
        
        # 判断球员是否现在在该球队
        is_in_team = check_current_team(current_team, team_name, is_retired)
        
        players_dict[player_name]['teams'].append({
            'team_name': team_name,
            'appearances': appearances,
            'is_in_team': is_in_team,
            'is_retired': is_retired
        })
    
    # 为每个球员生成最终数据
    final_players_data = []
    
    for player_name, player_data in players_dict.items():
        # 按出场数降序排序球队
        teams = sorted(player_data['teams'], key=lambda x: x['appearances'], reverse=True)
        
        # 提取所有效力过的球队名称
        all_teams = [team['team_name'] for team in teams]
        total_appearances = sum(team['appearances'] for team in teams)
        
        team_data = {
            'player_id': player_data['player_id'],  # 添加player_id作为第一列
            'player_name': player_name,
            'standardized_name': player_data['standardized_name'],  # 添加标准化姓名
            'all_teams': ', '.join(all_teams),  # 所有效力过的球队
            'total_appearances': total_appearances,  # 总出场数
            'team1': '',
            'team1_appearances': 0,
            'is_in_team1': 'no',
            'team2': '',
            'team2_appearances': 0,
            'is_in_team2': 'no',
            'team3': '',
            'team3_appearances': 0,
            'is_in_team3': 'no',
            'is_retired': 'no'
        }
        
        # 填充球队信息
        for i, team in enumerate(teams[:3]):
            if i == 0:
                team_data['team1'] = team['team_name']
                team_data['team1_appearances'] = team['appearances']
                team_data['is_in_team1'] = team['is_in_team']
                team_data['is_retired'] = team['is_retired']
            elif i == 1:
                team_data['team2'] = team['team_name']
                team_data['team2_appearances'] = team['appearances']
                team_data['is_in_team2'] = team['is_in_team']
            elif i == 2:
                team_data['team3'] = team['team_name']
                team_data['team3_appearances'] = team['appearances']
                team_data['is_in_team3'] = team['is_in_team']
        
        final_players_data.append(team_data)
    
    # 创建DataFrame并按第一支球队出场数降序排列
    df = pd.DataFrame(final_players_data)
    df = df.sort_values('total_appearances', ascending=False).reset_index(drop=True)
    return df

def check_current_team(current_team, page_team, is_retired):
    """
    检查球员是否现在在该球队效力
    """
    # 如果球员已退役，返回否
    if is_retired == 'yes':
        return 'no'
    
    # 如果没有当前效力球队信息，返回否
    if not current_team:
        return 'no'
    
    # 检查当前效力球队是否与页面球队一致
    # 需要处理球队名称的标准化（去除多余空格、统一大小写等）
    current_team_clean = current_team.strip().lower()
    page_team_clean = page_team.strip().lower()
    
    # 简单的字符串匹配，可以根据需要扩展
    if current_team_clean == page_team_clean:
        return 'yes'
    else:
        return 'no'

def main():
    print("=" * 80)
    print("英超所有球队球员数据爬取脚本 (出场数>=10，捕获所有效力球队)")
    print("=" * 80)
    
    # 爬取所有球队数据
    df = scrape_all_premier_league_teams()
    
    if df is not None and not df.empty:
        print("\n" + "=" * 80)
        print("爬取结果汇总:")
        print("=" * 80)
        print(f"总共找到 {len(df)} 名符合条件的球员")
        print("\n按第一支球队出场数排序的前20名球员:")
        print(df.head(20).to_string(index=False))
        
        # 统计各球队球员数量
        team1_counts = df['team1'].value_counts()
        print(f"\n各球队作为主要球队的球员数量:")
        for team, count in team1_counts.head(10).items():
            print(f"{team}: {count}人")
        
        # 统计多球队球员
        multi_team_players = df[(df['team2'] != '') & (df['team2_appearances'] >= 10)]
        print(f"\n在多支球队都有>=10场出场的球员数量: {len(multi_team_players)}人")
        
        # 统计现役vs退役
        active_players = df[df['is_retired'] == 'no']
        retired_players = df[df['is_retired'] == 'yes']
        print(f"现役球员: {len(active_players)}人")
        print(f"退役球员: {len(retired_players)}人")
        
        # 确保data目录存在
        os.makedirs('data', exist_ok=True)
        
        # 保存到CSV文件
        output_file = 'data/premier_league_players_multi_team.csv'
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n数据已保存到: {output_file}")
        
        # 保存到Excel文件
        try:
            excel_file = 'data/premier_league_players_multi_team.xlsx'
            df.to_excel(excel_file, index=False, engine='openpyxl')
            print(f"数据已保存到: {excel_file}")
        except ImportError:
            print("提示: 安装openpyxl可以导出Excel文件: pip install openpyxl")
        except Exception as e:
            print(f"保存Excel文件时出错: {e}")
    else:
        print("未能获取数据，请检查网络连接或网页结构是否变化")

if __name__ == "__main__":
    main()