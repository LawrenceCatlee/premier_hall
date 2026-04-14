import datetime
import json
import pandas as pd
import os
from pathlib import Path
import glob
from typing import Dict, List, Optional
import re

def load_all_data_files(data_dir: str = "data") -> Dict[str, pd.DataFrame]:
    """
    加载所有相关的数据文件
    """
    data_files = {}
    data_path = Path(data_dir)
    
    # 加载pulselive基础表
    pulselive_file = data_path / "pulselive_player_index_appearances.csv"
    if pulselive_file.exists():
        try:
            df = pd.read_csv(pulselive_file)
            data_files["pulselive_base"] = df
            print(f"加载 pulselive_base: {len(df)} 行数据")
        except Exception as e:
            print(f"加载 pulselive_base 失败: {e}")
    
    # 加载所有pl开头的文件
    pl_files = list(data_path.glob("pl*.csv"))
    for file_path in pl_files:
        file_name = file_path.stem
        try:
            df = pd.read_csv(file_path)
            data_files[file_name] = df
            print(f"加载 {file_name}: {len(df)} 行数据")
        except Exception as e:
            print(f"加载 {file_name} 失败: {e}")
    
    # 加载premier_league_players_multi_team.csv
    multi_team_file = data_path / "premier_league_players_multi_team.csv"
    if multi_team_file.exists():
        try:
            df = pd.read_csv(multi_team_file)
            data_files["premier_league_players_multi_team"] = df
            print(f"加载 premier_league_players_multi_team: {len(df)} 行数据")
        except Exception as e:
            print(f"加载 premier_league_players_multi_team 失败: {e}")
    
    return data_files

def standardize_player_names(df: pd.DataFrame, name_column: str) -> pd.DataFrame:
    """
    标准化球员姓名，便于匹配
    """
    df = df.copy()
    # 创建标准化姓名列
    df['standardized_name'] = df[name_column].astype(str).str.strip().str.lower()
    # 移除特殊字符
    df['standardized_name'] = df['standardized_name'].str.replace(r'[^\w\s]', '', regex=True)
    # 移除多余空格
    df['standardized_name'] = df['standardized_name'].str.replace(r'\s+', ' ', regex=True)
    # 处理特殊字符替换
    df['standardized_name'] = df['standardized_name'].str.replace('æ', 'ae', regex=False)
    df['standardized_name'] = df['standardized_name'].str.replace('ø', 'o', regex=False)
    df['standardized_name'] = df['standardized_name'].str.replace('ß', 'ss', regex=False)
    df['standardized_name'] = df['standardized_name'].str.replace('ij', 'y', regex=False)
    return df

def merge_pl_files(base_df: pd.DataFrame, data_files: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    基于player_id左合并所有pl文件
    """
    print("\n基于player_id左合并所有pl文件...")
    
    merged_df = base_df.copy()
    print(f"基础表: {len(merged_df)} 行")
    
    # 合并所有pl开头的文件
    for file_name, df in data_files.items():
        if not file_name.startswith('pl') or file_name == 'pulselive_base':
            continue
        
        if 'player_id' in df.columns:
            print(f"合并 {file_name}...")
            
            # 特殊处理pl_100_clean_sheets_gk.csv的列名映射
            if file_name == 'pl_100_clean_sheets_gk':
                df = df.rename(columns={'Clean sheets': 'Apps'})  # 将Clean sheets映射为Apps
            
            # 保留原始列名，添加前缀避免冲突
            prefix = file_name.replace('pl', '').replace('_', '')
            df_renamed = df.rename(columns={
                col: f"{prefix}_{col}" if col != 'player_id' else col 
                for col in df.columns if col != 'player_id'
            })
            
            # 左连接合并（不去重，保留所有记录用于后续合并多次获奖）
            merged_df = pd.merge(
                merged_df, 
                df_renamed, 
                on='player_id', 
                how='left'
            )
            print(f"  合并后: {len(merged_df)} 行")
        else:
            print(f"  跳过 {file_name} (没有player_id列)")
    
    return merged_df

def consolidate_awards(df: pd.DataFrame) -> pd.DataFrame:
    """
    合并同一球员多次获得的荣誉
    """
    print("\n合并多次获得的荣誉...")
    
    # 找出所有荣誉相关的列
    award_columns = [col for col in df.columns if any(keyword in col.lower() for keyword in ['season', 'year', 'winner'])]
    
    print(f"找到荣誉相关列: {award_columns}")
    
    for col in award_columns:
        if col in df.columns:
            print(f"处理列: {col}")
            # 检查是否是seasons列（需要特殊处理）
            if 'seasons' in col.lower():
                # 对于seasons列，直接合并所有内容，不提取年份
                def merge_seasons(group):
                    seasons = group[col].dropna().astype(str)
                    if len(seasons) > 1:
                        # 合并多个seasons记录，用逗号分隔
                        unique_seasons = []
                        for season in seasons:
                            season_str = str(season).strip()
                            if season_str and season_str != 'nan':
                                unique_seasons.append(season_str)
                        
                        # 去重并排序
                        unique_seasons = list(dict.fromkeys(unique_seasons))  # 保持顺序去重
                        return ', '.join(unique_seasons)
                    elif len(seasons) == 1:
                        season_str = str(seasons.iloc[0]).strip()
                        return season_str if season_str and season_str != 'nan' else None
                    else:
                        return None
                
                try:
                    # 使用apply处理整个分组
                    merged_seasons = df.groupby('player_id').apply(
                        lambda group: merge_seasons(group), 
                        include_groups=False
                    )
                    df[col] = df['player_id'].map(merged_seasons)
                    print(f"已合并 {col} 列")
                except Exception as e:
                    print(f"合并 {col} 列时出错: {e}")
            else:
                # 对于其他荣誉列，使用原有逻辑
                def merge_awards(group):
                    # 获取非空的获奖记录
                    awards = group[col].dropna().astype(str)
                    if len(awards) > 1:
                        # 合并多个获奖年份，用逗号分隔
                        unique_awards = []
                        for award in awards:
                            award_str = str(award).strip()
                            if award_str and award_str != 'nan':
                                # 处理年份范围（如1992–93）
                                if '–' in award_str:
                                    # 提取起始年份
                                    start_year = award_str.split('–')[0]
                                    unique_awards.append(start_year)
                                else:
                                    unique_awards.append(award_str)
                        
                        # 去重并排序
                        unique_awards = sorted(set(unique_awards))
                        return ', '.join(unique_awards)
                    elif len(awards) == 1:
                        award_str = str(awards.iloc[0]).strip()
                        if '–' in award_str:
                            # 处理年份范围
                            start_year = award_str.split('–')[0]
                            return start_year
                        return award_str
                    else:
                        return None
                
                try:
                    # 使用apply处理整个分组
                    merged_awards = df.groupby('player_id').apply(
                        lambda group: merge_awards(group), 
                        include_groups=False
                    )
                    df[col] = df['player_id'].map(merged_awards)
                    print(f"已合并 {col} 列")
                except Exception as e:
                    print(f"合并 {col} 列时出错: {e}")
    
    return df

def merge_multi_team_data(base_df: pd.DataFrame, multi_team_df: pd.DataFrame) -> pd.DataFrame:
    """
    基于球员姓名合并multi_team数据，包含所有详细信息
    """
    print("\n基于球员姓名合并multi_team数据...")
    
    # 标准化两个表的姓名
    base_df = standardize_player_names(base_df, 'player_name')
    multi_team_df = standardize_player_names(multi_team_df, 'player_name')
    
    # 为multi_team表的列添加前缀，但保留所有列
    multi_team_renamed = multi_team_df.rename(columns={
        col: f"multi_{col}" if col != 'standardized_name' else col 
        for col in multi_team_df.columns
    })
    
    print(f"multi_team数据列: {multi_team_renamed.columns.tolist()}")
    
    # 基于标准化姓名合并，保留所有multi_team的数据
    merged_df = pd.merge(
        base_df, 
        multi_team_renamed, 
        on='standardized_name', 
        how='left'
    )
    
    print(f"合并multi_team后: {len(merged_df)} 行")
    
    # 移除临时列
    merged_df = merged_df.drop(columns=['standardized_name'])
    
    return merged_df

def merge_golden_boot_data(base_df: pd.DataFrame, data_files: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    专门合并金靴奖数据，保留赛季和进球数
    """
    print("\n专门合并金靴奖数据...")
    
    if "pl_golden_boot_winners" not in data_files:
        print("未找到金靴奖数据文件")
        return base_df
    
    golden_boot_df = data_files["pl_golden_boot_winners"].copy()
    print(f"金靴奖原始数据: {len(golden_boot_df)} 行")
    
    # 重命名列，只保留需要的列
    golden_boot_clean = golden_boot_df[['player_id', 'Season', 'Goals']].copy()
    golden_boot_clean = golden_boot_clean.rename(columns={
        'Season': 'golden_boot_season',
        'Goals': 'golden_boot_goals'
    })
    
    # 按player_id分组，合并多次获奖
    def merge_golden_boot(group):
        seasons = group['golden_boot_season'].dropna().astype(str)
        goals = group['golden_boot_goals'].dropna().astype(str)
        
        if len(seasons) > 1:
            # 处理多个赛季
            season_list = []
            goal_list = []
            
            for season, goal in zip(seasons, goals):
                season_str = str(season).strip()
                goal_str = str(goal).strip()
                
                if season_str and season_str != 'nan' and goal_str and goal_str != 'nan':
                    # 处理年份范围
                    if '–' in season_str:
                        start_year = season_str.split('–')[0]
                        season_list.append(start_year)
                    else:
                        season_list.append(season_str)
                    goal_list.append(goal_str)
            
            return ', '.join(season_list), ', '.join(goal_list)
        elif len(seasons) == 1:
            season_str = str(seasons.iloc[0]).strip()
            goal_str = str(goals.iloc[0]).strip()
            
            if '–' in season_str:
                start_year = season_str.split('–')[0]
                return start_year, goal_str
            return season_str, goal_str
        else:
            return None, None
    
    # 分组合并
    merged_results = golden_boot_clean.groupby('player_id').apply(
        lambda group: merge_golden_boot(group), 
        include_groups=False
    )
    
    # 创建合并后的DataFrame
    merged_golden_boot = pd.DataFrame({
        'player_id': merged_results.index,
        'golden_boot_season': [result[0] if result else None for result in merged_results],
        'golden_boot_goals': [result[1] if result else None for result in merged_results]
    })
    
    print(f"合并后金靴奖数据: {len(merged_golden_boot)} 行")
    
    # 与基础表合并
    final_df = pd.merge(base_df, merged_golden_boot, on='player_id', how='left')
    print(f"合并金靴奖后总数据: {len(final_df)} 行")
    
    # 显示有金靴奖的球员示例
    with_golden_boot = final_df[final_df['golden_boot_season'].notna()]
    if len(with_golden_boot) > 0:
        print(f"有金靴奖记录的球员数: {len(with_golden_boot)}")
        print("金靴奖球员示例:")
        examples = with_golden_boot[['player_name', 'golden_boot_season', 'golden_boot_goals']].head(5)
        print(examples.to_string(index=False))
    
    return final_df

def remove_duplicate_players(df: pd.DataFrame) -> pd.DataFrame:
    """
    去除重复的球员记录
    """
    print("\n去除重复的球员记录...")
    
    original_count = len(df)
    
    # 基于player_id去重
    if 'player_id' in df.columns:
        df = df.drop_duplicates(subset=['player_id'], keep='first')
        print(f"基于player_id去重: {original_count} -> {len(df)} 行")
    else:
        # 如果没有player_id，基于标准化姓名去重
        df = standardize_player_names(df, 'player_name')
        df = df.drop_duplicates(subset=['standardized_name'], keep='first')
        df = df.drop(columns=['standardized_name'])
        print(f"基于姓名去重: {original_count} -> {len(df)} 行")
    
    return df

def create_final_merged_dataset(data_files: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    创建最终合并的数据集
    """
    print("=" * 80)
    print("开始合并数据...")
    print("=" * 80)
    
    # 第一步：以pulselive为基础表
    if "pulselive_base" not in data_files:
        print("未找到基础表 pulselive_base")
        return pd.DataFrame()
    
    base_df = data_files["pulselive_base"].copy()
    print(f"基础表 (pulselive): {len(base_df)} 行")
    
    # 第二步：左合并所有pl文件
    merged_df = merge_pl_files(base_df, data_files)
    
    # 第三步：合并多次获得的荣誉
    merged_df = consolidate_awards(merged_df)
    
    # 第四步：合并multi_team数据
    if "premier_league_players_multi_team" in data_files:
        merged_df = merge_multi_team_data(merged_df, data_files["premier_league_players_multi_team"])
    
    # 第五步：专门合并金靴奖数据
    merged_df = merge_golden_boot_data(merged_df, data_files)
    
    # 第六步：去除重复记录
    merged_df = remove_duplicate_players(merged_df)
    
    # 数据清理和整理
    print("\n数据清理和整理...")
    
    # 定义需要移除的列
    columns_to_remove = [
        'goldenglovewinners_Player', 'goldenglovewinners_Club',
        '100cleansheetsgk_Rank', '100cleansheetsgk_Percent', '100cleansheetsgk_Club(s)', '100cleansheetsgk_Ref.',
        'ayerofseasonwinners_Position', 'ayerofseasonwinners_Nationality',
        'team10y20yawardxi_position', 'team10y20yawardxi_player',
        '100goalsclub_Ratio', '100goalsclub_First', '100goalsclub_Last', '100goalsclub_Club(s)',
        'ayers3ustitles_nationality'
    ]
    
    # 移除不需要的列
    columns_to_keep = []
    seen_columns = set()
    
    for col in merged_df.columns:
        if col in columns_to_remove:
            continue
        # 保留player_id和核心列
        if col in ['player_id', 'player_name', 'appearances']:
            columns_to_keep.append(col)
            continue
        
        # 保留所有multi_开头的列
        if col.startswith('multi_'):
            columns_to_keep.append(col)
            continue
        
        # 对于其他列，检查是否与已保留的列重复
        base_col = col.split('_')[-1] if '_' in col else col
        if base_col not in seen_columns:
            columns_to_keep.append(col)
            seen_columns.add(base_col)
    
    merged_df = merged_df[columns_to_keep]
    print(f"清理后保留的列数: {len(merged_df.columns)}")
    
    # 添加英超年度最佳球员获奖年份列
    if 'ayerofseasonwinners_Season' in merged_df.columns:
        merged_df = merged_df.rename(columns={'ayerofseasonwinners_Season': 'yearofseasonwinners'})
        print("已添加 yearofseasonwinners 列")
    
    # 按出场数排序
    if 'appearances' in merged_df.columns:
        merged_df = merged_df.sort_values('appearances', ascending=False)
    
    print(f"最终数据集: {len(merged_df)} 行, {len(merged_df.columns)} 列")
    
    return merged_df

def save_merged_data(merged_df: pd.DataFrame, output_dir: str = "data",
                     frontend_json_path: Optional[Path] = None,
                     dob_df: Optional[pd.DataFrame] = None) -> None:
    """
    保存合并后的数据，并导出前端 players.json。

    Parameters
    ----------
    frontend_json_path : 目标 JSON 路径，默认写到 ../frontend/public/data/players.json
    dob_df : 从 pulselive_data.fetch_player_dob_batch 返回的 DOB 表
    """
    if merged_df.empty:
        print("没有数据可保存")
        return

    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # 保存完整 CSV
    full_file = output_path / "premier_league_players_merged_final.csv"
    merged_df.to_csv(full_file, index=False, encoding='utf-8-sig')
    print(f"完整数据已保存到: {full_file}")

    # 保存 Excel
    try:
        excel_file = output_path / "premier_league_players_merged_final.xlsx"
        merged_df.to_excel(excel_file, index=False, engine='openpyxl')
        print(f"Excel数据已保存到: {excel_file}")
    except ImportError:
        print("提示: 安装openpyxl可以导出Excel文件: pip install openpyxl")
    except Exception as e:
        print(f"保存Excel文件时出错: {e}")

    # 保存前端简化 CSV
    frontend_df = create_frontend_dataset(merged_df)
    frontend_file = output_path / "premier_league_players_frontend_final.csv"
    frontend_df.to_csv(frontend_file, index=False, encoding='utf-8-sig')
    print(f"前端数据已保存到: {frontend_file}")

    # 导出前端 players.json
    if frontend_json_path is None:
        # 默认：相对于 backend/ 找 frontend/public/data/players.json
        frontend_json_path = Path(__file__).parent.parent / "frontend" / "public" / "data" / "players.json"
    export_players_json(merged_df, Path(frontend_json_path), dob_df=dob_df)

CLUB_MAP = {
    'Manchester United': '曼联', 'Arsenal': '阿森纳', 'Chelsea': '切尔西',
    'Liverpool': '利物浦', 'Manchester City': '曼城', 'Tottenham Hotspur': '热刺',
    'Everton': '埃弗顿', 'Newcastle United': '纽卡斯尔', 'Aston Villa': '阿斯顿维拉',
    'Blackburn Rovers': '布莱克本', 'Leeds United': '利兹联', 'West Ham United': '西汉姆',
    'Leicester City': '莱斯特城', 'Southampton': '南安普顿', 'Middlesbrough': '米德尔斯堡',
    'Bolton Wanderers': '博尔顿', 'Fulham': '富勒姆', 'Sunderland': '桑德兰',
    'West Bromwich Albion': '西布罗姆维奇', 'Stoke City': '斯托克城',
    'Birmingham City': '伯明翰', 'Charlton Athletic': '查尔顿', 'Coventry City': '考文垂',
    'Swansea City': '斯旺西', 'Crystal Palace': '水晶宫', 'Wigan Athletic': '威根竞技',
    'Norwich City': '诺维奇', 'Burnley': '伯恩利', 'Wolverhampton Wanderers': '狼队',
    'Sheffield Wednesday': '谢周三', 'Nottingham Forest': '诺丁汉森林',
    'Portsmouth': '朴茨茅斯', 'Ipswich Town': '伊普斯威奇', 'Derby County': '德比郡',
    'Sheffield United': '谢菲尔德联', 'Bradford City': '布拉德福德',
    'Queens Park Rangers': '女王公园巡游者', 'Wimbledon': '温布尔顿',
    'Oldham Athletic': '奥尔德姆', 'Nottingham': '诺丁汉',
    'Brighton & Hove Albion': '布莱顿', 'Watford': '沃特福德',
    'Huddersfield Town': '哈德斯菲尔德', 'Cardiff City': '卡迪夫城',
    'Bournemouth': '伯恩茅斯', 'Brentford': '布伦特福德', 'Luton Town': '卢顿',
}


def _v(row, col, default=None):
    """Safe column access that returns default if column missing or value is NaN."""
    val = row.get(col, default)
    if val is None:
        return default
    try:
        import math
        if math.isnan(float(val)):
            return default
    except (TypeError, ValueError):
        pass
    return val


def _parse_achievements(row) -> List[str]:
    achievements = []
    apps = float(_v(row, 'appearances', 0) or 0)
    clean_sheets = float(_v(row, '100cleansheetsgk_Premier League total clean sheets', 0) or 0)
    goals = float(_v(row, '100goalsclub_Premier League total goals', 0) or 0)
    titles = float(_v(row, 'ayers3ustitles_titles', 0) or 0)
    golden_boot = _v(row, 'golden_boot_season')
    golden_glove = _v(row, 'goldenglovewinners_Season')
    pots = _v(row, 'ayerofseasonwinners_Club')
    team_xi = _v(row, 'team10y20yawardxi_award')
    team1 = _v(row, 'multi_team1', '')
    team2 = _v(row, 'multi_team2', '')
    team3 = _v(row, 'multi_team3', '')
    team1_apps = float(_v(row, 'multi_team1_appearances', 0) or 0)
    team2_apps = float(_v(row, 'multi_team2_appearances', 0) or 0)
    team3_apps = float(_v(row, 'multi_team3_appearances', 0) or 0)

    if apps >= 250:
        achievements.append('出场250次')
    if clean_sheets >= 100:
        achievements.append('百大零封')
    if goals >= 100:
        achievements.append('百球')
    if titles >= 3:
        achievements.append('三冠王')
    if golden_boot and str(golden_boot).strip():
        achievements.append('金靴奖')
    if golden_glove and str(golden_glove).strip():
        achievements.append('金手套奖')
    if pots and str(pots).strip():
        achievements.append('年度最佳')
    if team_xi and str(team_xi).strip():
        achievements.append('最佳阵容')
    is_single = team1 and str(team1).strip() and \
                (not team2 or not str(team2).strip() or team2_apps == 0) and \
                (not team3 or not str(team3).strip() or team3_apps == 0)
    if is_single and team1_apps >= 200:
        achievements.append('单队200场')
    return list(dict.fromkeys(achievements))


def _parse_clubs(row) -> List[str]:
    clubs = []
    for team_col, apps_col in [
        ('multi_team1', 'multi_team1_appearances'),
        ('multi_team2', 'multi_team2_appearances'),
        ('multi_team3', 'multi_team3_appearances'),
    ]:
        team = _v(row, team_col, '')
        apps = float(_v(row, apps_col, 0) or 0)
        if team and str(team).strip() and (team_col == 'multi_team1' or apps > 0):
            mapped = CLUB_MAP.get(str(team).strip(), str(team).strip())
            if mapped not in clubs:
                clubs.append(mapped)
    if not clubs:
        titles_club = _v(row, 'ayers3ustitles_clubs', '')
        if titles_club and str(titles_club).strip():
            first = str(titles_club).split(',')[0]
            first = re.sub(r'\s*\(\d+\)$', '', first).strip()
            clubs.append(CLUB_MAP.get(first, first))
    return clubs


def _single_club_apps(row) -> Optional[float]:
    team1 = _v(row, 'multi_team1', '')
    team2 = _v(row, 'multi_team2', '')
    team3 = _v(row, 'multi_team3', '')
    team1_apps = float(_v(row, 'multi_team1_appearances', 0) or 0)
    team2_apps = float(_v(row, 'multi_team2_appearances', 0) or 0)
    team3_apps = float(_v(row, 'multi_team3_appearances', 0) or 0)
    is_single = team1 and str(team1).strip() and \
                (not team2 or not str(team2).strip() or team2_apps == 0) and \
                (not team3 or not str(team3).strip() or team3_apps == 0)
    return team1_apps if is_single else None


def export_players_json(merged_df: pd.DataFrame, output_path: Path, dob_df: Optional[pd.DataFrame] = None) -> None:
    """
    Convert the merged DataFrame into the JSON format consumed by the frontend
    and write it to output_path.

    JSON shape per player:
      id, name_en, name_cn, total_appearances, single_club_appearances,
      goals, clean_sheets, premier_league_titles, clubs, achievements,
      is_active, is_hall_of_fame, nationality, position, birth_date
    """
    # Build player_id -> dob lookup
    dob_lookup: Dict[int, str] = {}
    if dob_df is not None and not dob_df.empty:
        for _, r in dob_df.iterrows():
            pid = int(r['player_id'])
            dob_lookup[pid] = str(r.get('birth_date', '') or '')

    today = datetime.date.today()

    def calc_age(birth_date_str: str) -> Optional[int]:
        if not birth_date_str:
            return None
        try:
            bd = datetime.date.fromisoformat(birth_date_str)
            return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        except ValueError:
            return None

    players = []
    row_dict = merged_df.to_dict(orient='records')
    for row in row_dict:
        player_id = int(_v(row, 'player_id', 0) or 0)
        name = str(_v(row, 'player_name', '') or '').strip()
        if not name:
            continue

        total_apps = _v(row, 'appearances')
        total_apps = float(total_apps) if total_apps else None

        clean_sheets_val = _v(row, '100cleansheetsgk_Premier League total clean sheets')
        clean_sheets_val = float(clean_sheets_val) if clean_sheets_val else None

        goals_val = _v(row, '100goalsclub_Premier League total goals')
        goals_val = float(goals_val) if goals_val else None

        titles_val = _v(row, 'ayers3ustitles_titles')
        titles_val = float(titles_val) if titles_val else None

        is_retired = str(_v(row, 'multi_is_retired', 'no') or 'no').strip().lower()
        is_active = is_retired != 'yes'

        birth_date = dob_lookup.get(player_id, '')

        players.append({
            'id': player_id,
            'name_en': name,
            'name_cn': name,
            'total_appearances': total_apps,
            'single_club_appearances': _single_club_apps(row),
            'goals': goals_val,
            'clean_sheets': clean_sheets_val,
            'premier_league_titles': titles_val,
            'clubs': _parse_clubs(row),
            'achievements': _parse_achievements(row),
            'is_active': is_active,
            'is_hall_of_fame': False,
            'nationality': str(_v(row, 'nationality', '') or ''),
            'position': str(_v(row, 'position', '') or ''),
            'birth_date': birth_date,
            'age': calc_age(birth_date),
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(players, f, ensure_ascii=False, separators=(',', ':'))
    print(f"players.json saved: {len(players)} players → {output_path}")


def create_frontend_dataset(merged_df: pd.DataFrame) -> pd.DataFrame:
    """
    创建前端展示用的简化数据集
    """
    # 选择前端需要的核心字段
    core_columns = [
        'player_id', 'player_name', 'appearances'
    ]
    
    # 确保列存在
    available_columns = [col for col in core_columns if col in merged_df.columns]
    frontend_df = merged_df[available_columns].copy()
    
    # 添加一些有用的衍生字段
    if 'appearances' in frontend_df.columns:
        frontend_df['appearances_category'] = pd.cut(
            frontend_df['appearances'],
            bins=[0, 200, 300, 400, 500, float('inf')],
            labels=['200-299', '300-399', '400-499', '500-599', '600+'],
            right=False
        )
    
    # 按出场数排序
    frontend_df = frontend_df.sort_values('appearances', ascending=False)
    
    return frontend_df

def main():
    """
    主函数
    """
    print("=" * 80)
    print("英超球员数据合并脚本 (简化版)")
    print("=" * 80)

    # 加载所有数据文件
    data_files = load_all_data_files()

    if not data_files:
        print("未找到任何数据文件")
        return

    # 确保 pulselive 索引包含 nationality / position
    # 若缓存只有 3 列，从 pulselive_data 模块重建
    pulselive_base = data_files.get("pulselive_base", pd.DataFrame())
    if "nationality" not in pulselive_base.columns or "position" not in pulselive_base.columns:
        print("pulselive 索引缺少 nationality/position，尝试重建缓存...")
        try:
            from pulselive_data import refresh_player_cache
            data_files["pulselive_base"] = refresh_player_cache()
        except Exception as e:
            print(f"重建失败，继续使用现有缓存: {e}")

    # 创建合并数据集
    merged_df = create_final_merged_dataset(data_files)

    if merged_df.empty:
        print("数据合并失败")
        return

    # 批量获取球员出生日期（利用已有 player_id）
    dob_df = None
    if "player_id" in merged_df.columns:
        try:
            from pulselive_data import fetch_player_dob_batch
            player_ids = merged_df["player_id"].dropna().astype(int).tolist()
            dob_df = fetch_player_dob_batch(player_ids)
        except Exception as e:
            print(f"获取球员出生日期失败（将继续，birth_date 置空）: {e}")

    # 保存合并数据 + 导出 players.json
    save_merged_data(merged_df, dob_df=dob_df)
    
    print("\n" + "=" * 80)
    print("数据合并完成!")
    print("=" * 80)
    
    # 显示统计信息
    print(f"\n最终数据集统计:")
    print(f"总球员数: {len(merged_df)}")
    if 'appearances' in merged_df.columns:
        print(f"出场数范围: {merged_df['appearances'].min()} - {merged_df['appearances'].max()}")
    
    print(f"\n数据列: {len(merged_df.columns)}")
    print("主要列名:")
    for col in merged_df.columns[:15]:  # 显示前15列
        print(f"  - {col}")
    if len(merged_df.columns) > 15:
        print(f"  ... 还有 {len(merged_df.columns) - 15} 列")
    
    # 检查重复球员
    print(f"\n重复球员检查:")
    if 'player_name' in merged_df.columns:
        duplicate_names = merged_df[merged_df.duplicated(subset=['player_name'], keep=False)]
        if not duplicate_names.empty:
            print(f"发现 {len(duplicate_names)} 个重复的球员姓名")
            print("重复球员示例:", duplicate_names['player_name'].head(5).tolist())
        else:
            print("未发现重复球员")

if __name__ == "__main__":
    main()
