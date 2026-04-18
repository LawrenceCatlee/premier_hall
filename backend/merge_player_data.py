import datetime
import json
import pandas as pd
import os
from pathlib import Path
import glob
from typing import Dict, List, Optional, Set
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
    
    # 加载所有pl_开头的文件（注意下划线，避免匹配 player_status_all.csv）
    pl_files = list(data_path.glob("pl_*.csv"))
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

    # 加载 ChatGPT 爬取的中文名 xlsx（player_id + player_name_zh）
    cn_xlsx = data_path / "premier_league_players_name_Chinese.xlsx"
    if cn_xlsx.exists():
        try:
            df = pd.read_excel(cn_xlsx, usecols=["player_id", "player_name_zh"])
            df["player_id"] = pd.to_numeric(df["player_id"], errors="coerce")
            df = df.dropna(subset=["player_id"])
            df["player_id"] = df["player_id"].astype(int)
            data_files["xlsx_cn_names"] = df
            print(f"加载 xlsx_cn_names: {len(df)} 行数据")
        except Exception as e:
            print(f"加载 xlsx_cn_names 失败: {e}")

    # 加载 ChatGPT 爬取的历史俱乐部 xlsx（player_id + 效力英超球队）
    clubs_xlsx = data_path / "premier_league_players_history_clubs.xlsx"
    if clubs_xlsx.exists():
        try:
            df = pd.read_excel(clubs_xlsx, usecols=["player_id", "效力英超球队"])
            df["player_id"] = pd.to_numeric(df["player_id"], errors="coerce")
            df = df.dropna(subset=["player_id"])
            df["player_id"] = df["player_id"].astype(int)
            df = df.rename(columns={"效力英超球队": "xlsx_clubs"})
            data_files["xlsx_history_clubs"] = df
            print(f"加载 xlsx_history_clubs: {len(df)} 行数据")
        except Exception as e:
            print(f"加载 xlsx_history_clubs 失败: {e}")

    # 加载 250.py 输出的 clubs 列（currentTeam + previousTeam）
    clubs_250_file = data_path / "epl_players_appearances_230plus.csv"
    if clubs_250_file.exists():
        try:
            df = pd.read_csv(clubs_250_file, usecols=lambda c: c in ("player_id", "clubs"))
            df = df.rename(columns={"clubs": "profile_clubs"})
            data_files["epl_250_clubs"] = df
            print(f"加载 epl_250_clubs: {len(df)} 行数据")
        except Exception as e:
            print(f"加载 epl_250_clubs 失败: {e}")

    # 加载 scrape_player_status.py 输出的全量退役状态（is_retired / current_team 唯一权威来源）
    status_file = data_path / "player_status_all.csv"
    if status_file.exists():
        try:
            df = pd.read_csv(status_file, usecols=["player_id", "is_retired", "current_team"])
            df["player_id"] = pd.to_numeric(df["player_id"], errors="coerce").dropna().astype(int)
            data_files["player_status_all"] = df
            print(f"加载 player_status_all: {len(df)} 行数据")
        except Exception as e:
            print(f"加载 player_status_all 失败: {e}")

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
        if not file_name.startswith('pl_') or file_name == 'pulselive_base':
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
    基于球员id合并multi_team数据，包含所有详细信息
    """
    print("\n基于球员id合并multi_team数据...")
    
    # 标准化两个表的姓名
    base_df = standardize_player_names(base_df, 'player_name')
    multi_team_df = standardize_player_names(multi_team_df, 'player_name')
    
    # 为multi_team表的列添加前缀，但保留所有列
    multi_team_renamed = multi_team_df.rename(columns={
        col: f"multi_{col}" if col != 'standardized_name' and col != 'player_id' else col 
        for col in multi_team_df.columns
    })
    
    print(f"multi_team数据列: {multi_team_renamed.columns.tolist()}")
    
    # 基于标准化姓名合并，保留所有multi_team的数据
    merged_df = pd.merge(
        base_df, 
        multi_team_renamed, 
        on='player_id', 
        how='left'
    )
    
    print(f"合并multi_team后: {len(merged_df)} 行")
    
    # 移除临时列
    merged_df = merged_df.drop(columns=['standardized_name_x', 'standardized_name_y'], errors='ignore')
    
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

    # 第六步：合并 250.py 的 profile_clubs（currentTeam + previousTeam）
    if "epl_250_clubs" in data_files:
        clubs_df = data_files["epl_250_clubs"].dropna(subset=["player_id"]).copy()
        clubs_df["player_id"] = clubs_df["player_id"].astype(int)
        merged_df = pd.merge(merged_df, clubs_df, on="player_id", how="left")
        print(f"合并 profile_clubs 后: {len(merged_df)} 行")

    # 第六步B：合并 scrape_player_status.py 全量退役状态
    # 存在时作为唯一权威来源，is_retired / current_team 取代全部旧状态列
    if "player_status_all" in data_files:
        ps_df = data_files["player_status_all"].copy()
        ps_df["player_id"] = ps_df["player_id"].astype(int)
        for col in ("current_team", "is_retired"):
            if col in merged_df.columns:
                merged_df = merged_df.drop(columns=[col])
        merged_df = pd.merge(merged_df, ps_df, on="player_id", how="left")
        print(f"合并 player_status_all 后: {len(merged_df)} 行")

    # 第七步A：合并 ChatGPT xlsx 历史俱乐部（优先于 Transfermarkt multi_all_teams）
    if "xlsx_history_clubs" in data_files:
        hc_df = data_files["xlsx_history_clubs"].copy()
        hc_df["player_id"] = hc_df["player_id"].astype(int)
        merged_df = pd.merge(merged_df, hc_df, on="player_id", how="left")
        print(f"合并 xlsx_history_clubs 后: {len(merged_df)} 行")

    # 第七步B：合并 ChatGPT xlsx 中文名（player_id 级别，补充 JSON 映射）
    if "xlsx_cn_names" in data_files:
        cn_df = data_files["xlsx_cn_names"].copy()
        cn_df["player_id"] = cn_df["player_id"].astype(int)
        merged_df = pd.merge(merged_df, cn_df, on="player_id", how="left")
        print(f"合并 xlsx_cn_names 后: {len(merged_df)} 行")

    # 第七步：去除重复记录
    merged_df = remove_duplicate_players(merged_df)
    
    # 数据清理和整理
    print("\n数据清理和整理...")
    
    # 定义需要移除的列
    columns_to_remove = {
        'goldenglovewinners_Player', 'goldenglovewinners_Club',
        '100cleansheetsgk_Rank', '100cleansheetsgk_Percent', '100cleansheetsgk_Club(s)', '100cleansheetsgk_Ref.',
        '100cleansheetsgk_player name', '100cleansheetsgk_Premier League appearances',
        'ayerofseasonwinners_Player', 'ayerofseasonwinners_Position', 'ayerofseasonwinners_Nationality',
        'team10y20yawardxi_position', 'team10y20yawardxi_player',
        '100goalsclub_Ratio', '100goalsclub_First', '100goalsclub_Last', '100goalsclub_Club(s)', '100goalsclub_player name',
        '100goalsclub_Premier League appearances',
        'ayers3ustitles_nationality', 'ayers3ustitles_player',
        'goldenbootwinners_Player', 'goldenbootwinners_Club',
        # multi_ columns that are redundant
        'multi_player_name', 'multi_total_appearances',
        # stale columns that appear when player_status_all was wrongly processed by merge_pl_files
        'ayerstatusall_is_retired', 'ayerstatusall_current_team',
    }

    # multi_ columns we want to keep (the rest are excluded above)
    multi_keep = {
        'multi_team1', 'multi_team1_appearances', 'multi_is_in_team1',
        'multi_team2', 'multi_team2_appearances', 'multi_is_in_team2',
        'multi_team3', 'multi_team3_appearances', 'multi_is_in_team3',
    }

    # 移除不需要的列
    columns_to_keep = []
    seen_columns = set()

    for col in merged_df.columns:
        if col in columns_to_remove:
            continue
        # 保留player_id和核心列（含 profile_clubs/ayerofseasonwinners_Season，防止被 base_col 去重逻辑误删）
        if col in ['player_id', 'player_name', 'appearances', 'profile_clubs',
                   'ayerofseasonwinners_Season', 'xlsx_clubs', 'player_name_zh',
                   'is_retired', 'current_team']:
            columns_to_keep.append(col)
            continue

        # multi_ 列：只保留白名单里的
        if col.startswith('multi_'):
            if col in multi_keep:
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

    # 删除：appearances < 180 且指定荣誉/球队信息列全部为空 的行
    check_cols = [
        'goldenglovewinners_Season',
        'goldenglovewinners_Clean sheets',
        '100cleansheetsgk_Premier League total clean sheets',
        'yearofseasonwinners',
        'ayerofseasonwinners_Club',
        'team10y20yawardxi_award',
        '100goalsclub_Premier League total goals',
        'goldenbootwinners_Goals',
        'ayers3ustitles_titles',
        'ayers3ustitles_clubs',
        'ayers3ustitles_seasons',
        'multi_team1',
        'multi_team1_appearances',
        'multi_is_in_team1',
        'multi_team2',
        'multi_team2_appearances',
        'multi_is_in_team2',
        'multi_team3',
        'multi_team3_appearances',
        'multi_is_in_team3',
        'golden_boot_season',
        'golden_boot_goals',
    ]

    existing_check_cols = [col for col in check_cols if col in merged_df.columns]

    if 'appearances' in merged_df.columns and existing_check_cols:
        appearances_num = pd.to_numeric(merged_df['appearances'], errors='coerce')

        # 把空字符串、纯空格也视为缺失值
        check_block = merged_df[existing_check_cols].replace(r'^\s*$', pd.NA, regex=True)

        delete_mask = appearances_num.lt(180) & check_block.isna().all(axis=1)

        print(f"删除前: {len(merged_df)} 行")
        print(f"满足条件待删除: {delete_mask.sum()} 行")

        merged_df = merged_df.loc[~delete_mask].copy()

        print(f"删除后: {len(merged_df)} 行")
    
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

    # 内部处理列（不写入任何输出）
    output_exclude = {'multi_all_teams', 'info_club', 'retired', 'profile_clubs'}

    # 保存完整 CSV
    csv_cols = [c for c in merged_df.columns if c not in output_exclude]
    full_file = output_path / "premier_league_players_merged_final.csv"
    merged_df[csv_cols].to_csv(full_file, index=False, encoding='utf-8-sig')
    print(f"完整数据已保存到: {full_file}")

    # 保存 Excel（同样排除内部列）
    try:
        excel_file = output_path / "premier_league_players_merged_final.xlsx"
        excel_cols = [c for c in merged_df.columns if c not in output_exclude]
        merged_df[excel_cols].to_excel(excel_file, index=False, engine='openpyxl')
        print(f"Excel数据已保存到: {excel_file}")
    except ImportError:
        print("提示: 安装openpyxl可以导出Excel文件: pip install openpyxl")
    except Exception as e:
        print(f"保存Excel文件时出错: {e}")

    # 导出前端 players.json
    if frontend_json_path is None:
        # 默认：相对于 backend/ 找 frontend/public/data/players.json
        frontend_json_path = Path(__file__).parent.parent / "frontend" / "public" / "data" / "players.json"
    export_players_json(merged_df, Path(frontend_json_path), dob_df=dob_df)

# 英超球员官方中文译名映射（用于 players.json 的 name_cn 字段）
# 键为 Pulselive 标准英文姓名（小写），值为中文译名
PLAYER_CN_NAME_MAP: Dict[str, str] = {
    # ── 出场榜顶端 ──────────────────────────────────────────────
    'gareth barry': '加雷斯·巴里',
    'ryan giggs': '瑞安·吉格斯',
    'james milner': '詹姆斯·米尔纳',
    'frank lampard': '弗兰克·兰帕德',
    'david james': '大卫·詹姆斯',
    'gary speed': '加里·斯皮德',
    'emile heskey': '埃米尔·赫斯基',
    'sol campbell': '索尔·坎贝尔',
    'paul scholes': '保罗·斯科尔斯',
    'jamie carragher': '杰米·卡拉格',
    'wayne rooney': '韦恩·鲁尼',
    'steven gerrard': '史蒂文·杰拉德',
    'john terry': '约翰·特里',
    'andy cole': '安迪·科尔',
    'andrew cole': '安迪·科尔',
    'alan shearer': '艾伦·希勒',
    'michael owen': '迈克尔·欧文',
    'robbie fowler': '罗比·福勒',
    'peter schmeichel': '彼得·舒梅切尔',
    'petr cech': '彼得·切赫',
    'david seaman': '大卫·西曼',
    'mark schwarzer': '马克·施瓦泽',
    'brad friedel': '布拉德·弗里德尔',
    'shay given': '谢·吉文',
    'tim howard': '蒂姆·霍华德',
    'paul robinson': '保罗·罗宾逊',
    'ashley cole': '阿什利·科尔',
    'gary neville': '加里·内维尔',
    'phil neville': '菲尔·内维尔',
    'nicky butt': '尼基·巴特',
    'roy keane': '罗伊·基恩',
    'david beckham': '大卫·贝克汉姆',
    'patrick vieira': '帕特里克·维埃拉',
    'robert pires': '罗伯特·皮雷斯',
    'freddie ljungberg': '弗雷迪·云加贝里',
    'thierry henry': '蒂埃里·亨利',
    'dennis bergkamp': '丹尼斯·伯格坎普',
    'nicolas anelka': '尼古拉斯·阿内尔卡',
    'tony adams': '托尼·亚当斯',
    'martin keown': '马丁·基翁',
    'nigel winterburn': '奈杰尔·温特伯恩',
    'lee dixon': '李·迪克森',
    'ray parlour': '雷·帕洛尔',
    'dwight yorke': '德怀特·约克',
    'ruud van nistelrooij': '鲁德·范尼斯特尔罗伊',
    'ole gunnar solskjaer': '奥莱·冈纳·索尔斯克亚',
    'robin van persie': '罗宾·范佩西',
    'dimitar berbatov': '迪米塔尔·贝尔巴托夫',
    'carlos tevez': '卡洛斯·特维斯',
    'cristiano ronaldo': '克里斯蒂亚诺·罗纳尔多',
    'michael carrick': '迈克尔·卡里克',
    'ashley young': '阿什利·杨',
    'wes brown': '韦斯·布朗',
    'john o\'shea': '约翰·奥谢',
    'rio ferdinand': '里奥·费迪南德',
    'didier drogba': '迪迪埃·德罗巴',
    'eden hazard': '伊甸·阿扎尔',
    'john obi mikel': '约翰·奥比·米克尔',
    'fernando torres': '费尔南多·托雷斯',
    'peter crouch': '彼得·克劳奇',
    'teddy sheringham': '泰迪·谢林汉姆',
    'dion dublin': '狄翁·都柏林',
    'les ferdinand': '莱斯·费迪南德',
    'ledley king': '莱德利·金',
    'robbie keane': '罗比·基恩',
    'jermain defoe': '贾梅因·德福',
    'darren bent': '达伦·本特',
    'darren anderton': '达伦·安德顿',
    'michael dawson': '迈克尔·道森',
    'leighton baines': '利顿·贝恩斯',
    'leon osman': '莱昂·奥斯曼',
    'tim cahill': '蒂姆·卡希尔',
    'phil jagielka': '菲利普·雅吉尔卡',
    'seamus coleman': '谢默斯·科尔曼',
    'mikel arteta': '米克尔·阿尔特塔',
    'kevin campbell': '凯文·坎贝尔',
    'sami hyypia': '萨米·许佩亚',
    'jamie redknapp': '杰米·雷德克纳普',
    'martin skrtel': '马丁·斯克特尔',
    'daniel agger': '丹尼尔·阿格',
    'lucas leiva': '卢卡斯·莱瓦',
    'kolo toure': '科洛·图雷',
    'bacary sagna': '巴卡里·萨尼亚',
    'william gallas': '威廉·加拉斯',
    'mikael silvestre': '米卡埃尔·西尔韦斯特雷',
    'sylvain distin': '西尔万·迪斯汀',
    'matthew le tissier': '马修·勒蒂西尔',
    'matt le tissier': '马修·勒蒂西尔',
    'nigel martyn': '奈杰尔·马丁',
    'sander westerveld': '桑德·韦斯特韦尔德',
    'dean kiely': '迪安·基利',
    'scott carson': '斯科特·卡森',
    'ben foster': '本·福斯特',
    'robert green': '罗伯特·格林',
    'stephen warnock': '史蒂芬·沃诺克',
    'martin laursen': '马丁·劳森',
    'olof mellberg': '奥洛夫·梅尔贝里',
    'gareth southgate': '加雷斯·索斯盖特',
    'ugo ehiogu': '乌戈·埃霍古',
    'alan wright': '艾伦·莱特',
    'mark bosnich': '马克·博斯尼奇',
    'peter enckelman': '彼得·恩克尔曼',
    'darius vassell': '达里亚斯·瓦塞尔',
    'dion dublin': '狄翁·都柏林',
    'tommy johnson': '汤米·约翰逊',
    'paul merson': '保罗·默森',
    'lee hendrie': '李·亨德里',
    'ian taylor': '伊恩·泰勒',
    'tommy elphick': '汤米·埃尔菲克',
    'marc albrighton': '马克·阿尔布莱顿',
    'shinji okazaki': '冈崎慎司',
    'riyad mahrez': '里亚德·马赫雷斯',
    'jamie vardy': '杰米·瓦尔迪',
    'kasper schmeichel': '卡斯帕·舒梅切尔',
    'christian fuchs': '克里斯蒂安·富克斯',
    'danny drinkwater': '丹尼·德林克沃特',
    'wes morgan': '韦斯·摩根',
    'robert huth': '罗伯特·胡特',
    'son heung-min': '孙兴慜',
    'harry kane': '哈里·凯恩',
    'hugo lloris': '乌戈·洛里斯',
    'jan vertonghen': '扬·弗托根',
    'toby alderweireld': '托比·阿尔德韦勒尔德',
    'kieran trippier': '基兰·特里皮尔',
    'dele alli': '德莱·阿利',
    'christian eriksen': '克里斯蒂安·埃里克森',
    'vincent kompany': '文森特·孔帕尼',
    'yaya toure': '亚亚·图雷',
    'david silva': '大卫·席尔瓦',
    'sergio aguero': '塞尔希奥·阿奎罗',
    'ilkay gundogan': '伊尔卡伊·居恩多安',
    'ilkay gündogan': '伊尔卡伊·居恩多安',
    'raheem sterling': '拉希姆·斯特林',
    'kevin de bruyne': '凯文·德布劳内',
    'fernandinho': '费尔南迪尼奥',
    'nicolas otamendi': '尼古拉斯·奥塔门迪',
    'kyle walker': '凯尔·沃克',
    'pablo zabaleta': '巴勃罗·萨瓦莱塔',
    'james milner': '詹姆斯·米尔纳',
    'joe hart': '乔·哈特',
    'james mcnulty': '詹姆斯·麦克纳尔蒂',
    'jordan henderson': '乔丹·亨德森',
    'virgil van dijk': '维吉尔·范戴克',
    'alisson becker': '阿利松·贝克尔',
    'trent alexander-arnold': '特伦特·亚历山大-阿诺德',
    'andy robertson': '安迪·罗伯逊',
    'sadio mane': '萨迪奥·马内',
    'mohamed salah': '穆罕默德·萨拉赫',
    'roberto firmino': '罗伯托·菲尔米诺',
    'xabi alonso': '沙比·阿隆索',
    'dirk kuijt': '德克·库伊特',
    'pepe reina': '佩佩·雷纳',
    'paul konchesky': '保罗·坤切斯基',
    'jamie redknapp': '杰米·雷德克纳普',
    'cesc fabregas': '塞斯克·法布雷加斯',
    'samir nasri': '萨米尔·纳斯里',
    'gael clichy': '加埃尔·克利希',
    'thomas vermaelen': '托马斯·弗梅伦',
    'per mertesacker': '佩尔·默特萨克',
    'laurent koscielny': '洛朗·科西尔尼',
    'nacho monreal': '纳乔·蒙雷亚尔',
    'santi cazorla': '桑蒂·卡索拉',
    'alexis sanchez': '阿莱克西斯·桑切斯',
    'mesut ozil': '梅苏特·厄齐尔',
    'pierre-emerick aubameyang': '皮埃尔-埃梅里克·奥巴姆扬',
    'alexandre lacazette': '亚历山大·拉卡泽特',
    'granit xhaka': '格拉尼特·贾卡',
    'bernd leno': '贝恩德·莱诺',
    'hector bellerin': '埃克托尔·贝列林',
    'rob holding': '罗伯·霍尔丁',
    'jack wilshere': '杰克·威尔谢尔',
    'theo walcott': '西奥·沃尔科特',
    'tomás soucek': '托马斯·苏切克',
    'mark noble': '马克·诺布尔',
    'antonio conte': '安东尼奥·孔蒂',
    'michail antonio': '米夏伊尔·安东尼奥',
    'declan rice': '德克兰·赖斯',
    'craig dawson': '克雷格·道森',
    'issa diop': '伊萨·迪奥普',
    'aaron cresswell': '亚伦·克莱斯韦尔',
    'pablo fornals': '巴勃罗·福纳尔斯',
    'andriy yarmolenko': '安德烈·亚尔莫连科',
    'patrice evra': '帕特里斯·埃夫拉',
    'nemanja vidic': '内马尼亚·维迪奇',
    'jonny evans': '乔尼·埃文斯',
    'darren fletcher': '达伦·弗莱彻',
    'anderson': '安德森',
    'antonio valencia': '安东尼奥·巴伦西亚',
    'wayne bridge': '韦恩·布里奇',
    'claude makelele': '克劳德·马克莱莱',
    'michael essien': '迈克尔·埃辛',
    'frank lampard': '弗兰克·兰帕德',
    'joe cole': '乔·科尔',
    'arjen robben': '阿尔扬·罗本',
    'shaun wright-phillips': '肖恩·赖特-菲利普斯',
    'scott parker': '斯科特·帕克',
    'john lundstram': '约翰·伦斯特拉姆',
    'james ward-prowse': '詹姆斯·沃德-普劳斯',
    'maya yoshida': '吉田麻也',
    'virgil van dijk': '维吉尔·范戴克',
    'dejan lovren': '德扬·洛夫伦',
    'nathaniel clyne': '纳撒尼尔·克莱恩',
    'emre can': '埃姆雷·詹',
    'adam lallana': '亚当·拉拉纳',
    'philippe coutinho': '菲利普·库蒂尼奥',
    'daniel sturridge': '丹尼尔·斯特里奇',
    'divock origi': '迪沃克·奥里吉',
    'gylfi sigurdsson': '吉尔菲·西于尔兹松',
    'peter odemwingie': '彼得·奥德姆温吉耶',
    'andrew johnson': '安德鲁·约翰逊',
    'david wheater': '大卫·韦特尔',
    'ian wright': '伊恩·赖特',
    'eric cantona': '埃里克·坎通纳',
    'dennis bergkamp': '丹尼斯·伯格坎普',
}

CLUB_MAP = {
    # Full names → Chinese
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
    # API shortNames → Chinese (so profile_clubs short names get mapped correctly)
    'Man Utd': '曼联', 'Man City': '曼城', 'Spurs': '热刺',
    'Brighton': '布莱顿', 'Newcastle': '纽卡斯尔', 'West Ham': '西汉姆',
    'Leicester': '莱斯特城', 'Blackburn': '布莱克本', 'Leeds': '利兹联',
    'West Brom': '西布罗姆维奇', 'Stoke': '斯托克城', 'Birmingham': '伯明翰',
    'Coventry': '考文垂', 'Swansea': '斯旺西', 'Wigan': '威根竞技',
    'Norwich': '诺维奇', 'Wolves': '狼队', "Nott'm Forest": '诺丁汉森林',
    'Sheff Weds': '谢周三', 'Sheff Utd': '谢菲尔德联', 'QPR': '女王公园巡游者',
    'Ipswich': '伊普斯威奇', 'Derby': '德比郡', 'Bolton': '博尔顿',
    'Middlesbrough': '米德尔斯堡', 'Boro': '米德尔斯堡',
    'Huddersfield': '哈德斯菲尔德', 'Cardiff': '卡迪夫城',
    'Aston Villa': '阿斯顿维拉',
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


def _parse_achievements(row) -> List[Dict[str, str]]:
    """Return list of {type, detail} dicts for each achievement."""
    achievements: List[Dict[str, str]] = []
    seen: Set[str] = set()

    def _add(typ: str, detail: str) -> None:
        if typ not in seen:
            achievements.append({'type': typ, 'detail': detail})
            seen.add(typ)

    apps = float(_v(row, 'appearances', 0) or 0)
    clean_sheets = float(_v(row, '100cleansheetsgk_Premier League total clean sheets', 0) or 0)
    goals = float(_v(row, '100goalsclub_Premier League total goals', 0) or 0)
    titles = float(_v(row, 'ayers3ustitles_titles', 0) or 0)
    golden_boot = _v(row, 'golden_boot_season')
    golden_glove = _v(row, 'goldenglovewinners_Season')
    pots_club = _v(row, 'ayerofseasonwinners_Club')
    # ayerofseasonwinners_Season 在列清理阶段被 rename 成了 yearofseasonwinners
    pots_season = _v(row, 'yearofseasonwinners') or _v(row, 'ayerofseasonwinners_Season')
    team_xi = _v(row, 'team10y20yawardxi_award')
    team1 = str(_v(row, 'multi_team1', '') or '')
    team2 = str(_v(row, 'multi_team2', '') or '')
    team3 = str(_v(row, 'multi_team3', '') or '')
    team1_apps = float(_v(row, 'multi_team1_appearances', 0) or 0)
    team2_apps = float(_v(row, 'multi_team2_appearances', 0) or 0)
    team3_apps = float(_v(row, 'multi_team3_appearances', 0) or 0)

    if apps >= 250:
        _add('出场250次', f'{int(apps)}场')
    # 单队200场紧排在出场250次之后
    for tname, tapps in [(team1, team1_apps), (team2, team2_apps), (team3, team3_apps)]:
        if tname.strip() and tapps >= 200:
            mapped = CLUB_MAP.get(tname.strip(), tname.strip())
            _add('单队200场', f'{mapped}|{int(tapps)}')
    if goals >= 100:
        _add('百球', f'{int(goals)}')
    if clean_sheets >= 100:
        _add('百大零封', f'{int(clean_sheets)}')
    if titles >= 3:
        # detail 格式：seasons§clubs  用§分隔，供前端按俱乐部分行显示
        seasons_raw = str(_v(row, 'ayers3ustitles_seasons', '') or '').strip()
        clubs_raw = str(_v(row, 'ayers3ustitles_clubs', '') or '').strip()
        _add('三冠王', f"{seasons_raw}§{clubs_raw}" if clubs_raw else seasons_raw)
    if golden_boot and str(golden_boot).strip():
        _add('金靴奖', str(golden_boot).strip())
    if golden_glove and str(golden_glove).strip():
        _add('金手套奖', str(golden_glove).strip())
    if pots_club and str(pots_club).strip():
        detail = str(pots_season).strip() if pots_season and str(pots_season).strip() else ''
        _add('年度最佳', detail)
    if team_xi and str(team_xi).strip():
        xi_label = '20年' if '20' in str(team_xi) else '10年'
        _add('最佳阵容', xi_label)
    return achievements


def _parse_clubs(row) -> List[str]:
    clubs = []

    # 1. ChatGPT xlsx 历史俱乐部（最高优先级，支持半角和全角分号分隔）
    xlsx_clubs = _v(row, 'xlsx_clubs', '')
    if xlsx_clubs and str(xlsx_clubs).strip():
        # 统一将全角分号替换为半角，再 split
        normalized = str(xlsx_clubs).replace('\uff1b', ';')
        for raw in normalized.split(';'):
            raw = raw.strip()
            if not raw:
                continue
            mapped = CLUB_MAP.get(raw, raw)
            if mapped not in clubs:
                clubs.append(mapped)
        if clubs:
            return clubs

    # 2. Transfermarkt 全量数据（multi_all_teams）
    all_teams = _v(row, 'multi_all_teams', '')
    if all_teams and str(all_teams).strip():
        for raw in str(all_teams).split(','):
            raw = raw.strip()
            if not raw:
                continue
            mapped = CLUB_MAP.get(raw, raw)
            if mapped not in clubs:
                clubs.append(mapped)

    # 3. profile_clubs 补充（currentTeam + previousTeam，来自250.py）
    profile = _v(row, 'profile_clubs', '')
    if profile and str(profile).strip():
        for raw in str(profile).split(','):
            raw = raw.strip()
            if not raw or raw not in CLUB_MAP:
                continue
            mapped = CLUB_MAP[raw]
            if mapped not in clubs:
                clubs.append(mapped)

    # 4. 兜底：用获冠军记录里的俱乐部
    if not clubs:
        titles_club = _v(row, 'ayers3ustitles_clubs', '')
        if titles_club and str(titles_club).strip():
            first = str(titles_club).split(',')[0]
            first = re.sub(r'\s*\(\d+\)$', '', first).strip()
            clubs.append(CLUB_MAP.get(first, first))
    return clubs


def _single_club_apps(row) -> Optional[float]:
    """Return the highest single-club PL appearances (team1, sorted by apps desc).
    Used for near-miss detection (180-200) and single-club 200 badge."""
    team1 = _v(row, 'multi_team1', '')
    team1_apps = float(_v(row, 'multi_team1_appearances', 0) or 0)
    return team1_apps if team1 and str(team1).strip() else None


# ============================================================
# 当赛季英超球队（English full names 匹配 current_team / current_club 字段）
# 每赛季升降级后在这里更新即可
# ============================================================
CURRENT_PL_CLUBS_EN: Set[str] = {
    'Manchester City', 'Liverpool', 'Arsenal', 'Chelsea', 'Tottenham Hotspur',
    'Manchester United', 'Wolverhampton Wanderers', 'West Ham United', 'Leeds United',
    'Sunderland', 'Brighton & Hove Albion', 'Aston Villa', 'Bournemouth',
    'Crystal Palace', 'Burnley', 'Newcastle United', 'Nottingham Forest',
    'Brentford', 'Fulham', 'Everton'
}

# 英超名人堂入选球员（官方公布，2021 年起）
# 键为 Pulselive 标准英文姓名（小写），值为入选年份
HALL_OF_FAME_MEMBERS: dict = {
    # 2021 届首批
    'alan shearer':    2021,
    'thierry henry':   2021,
    'eric cantona':    2021,
    'roy keane':       2021,
    'frank lampard':   2021,
    'dennis bergkamp': 2021,
    'steven gerrard':  2021,
    'david beckham':   2021,
    # 2022 届
    'sergio agüero':   2022,
    'didier drogba':   2022,
    'vincent kompany': 2022,
    'peter schmeichel':2022,
    'paul scholes':    2022,
    'ian wright':      2022,
    # 2023 届（教练 Ferguson/Wenger 不在球员表中）
    'tony adams':      2023,
    'petr cech':       2023,
    'rio ferdinand':   2023,
    # 2024 届
    'ashley cole':     2024,
    'andrew cole':     2024,
    'john terry':      2024,
    # 2025 届
    'gary neville':    2025,
    'eden hazard':     2025,
}

# 中文名现在通过 xlsx 合并（xlsx_cn_names），不再使用 JSON 文件。


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

        _status_retired = _v(row, 'is_retired')
        is_retired = str(_status_retired).strip().lower() == 'yes' if _status_retired is not None and str(_status_retired).strip().lower() not in ('', 'nan') else False
        is_active = not is_retired

        birth_date = dob_lookup.get(player_id, '')

        # single_club_name: English name of the club with highest PL apps (for near-miss label)
        _team1_raw = str(_v(row, 'multi_team1', '') or '').strip()
        single_club_name_en = _team1_raw  # keep English for frontend filtering

        # 中文名来源：xlsx player_name_zh（ChatGPT 爬取），未找到则保留英文名
        _xlsx_zh = str(_v(row, 'player_name_zh', '') or '').strip()
        name_cn = _xlsx_zh if _xlsx_zh else name

        # 规范化 current_team（去除 "FC"/"AFC" 等后缀/前缀，匹配 CURRENT_PL_CLUBS_EN）
        _raw_club = str(_v(row, 'current_team', '') or '').strip()
        current_club = re.sub(r'\s+FC$', '', _raw_club).strip()
        current_club = re.sub(r'^AFC\s+', '', current_club).strip()

        hof_year = HALL_OF_FAME_MEMBERS.get(name.lower())
        is_hall_of_fame = hof_year is not None

        # 四类球员状态（互斥，名人堂优先）
        if is_hall_of_fame:
            player_status = 'hall_of_fame'
        elif is_retired:
            player_status = 'retired'
        elif current_club in CURRENT_PL_CLUBS_EN:
            player_status = 'active_pl'
        else:
            player_status = 'active_not_pl'

        players.append({
            'id': player_id,
            'name_en': name,
            'name_cn': name_cn,
            'total_appearances': total_apps,
            'single_club_appearances': _single_club_apps(row),
            'single_club_name': single_club_name_en,
            'goals': goals_val,
            'clean_sheets': clean_sheets_val,
            'premier_league_titles': titles_val,
            'clubs': _parse_clubs(row),
            'achievements': _parse_achievements(row),
            'is_active': is_active,
            'player_status': player_status,
            'hof_year': hof_year,
            'is_hall_of_fame': is_hall_of_fame,
            'nationality': str(_v(row, 'nationality', '') or ''),
            'position': str(_v(row, 'position', '') or ''),
            'current_club': current_club,
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
