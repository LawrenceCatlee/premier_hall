#!/usr/bin/env python3
import pandas as pd
import json
from pathlib import Path

# 2024/25 Premier League clubs (used only to disambiguate active_pl vs active_not_pl
# for players whose epl250/multi scrapers have NaN — do NOT expand this list loosely)
# 2025/26 赛季英超球队（升降级后同步更新，与 merge_player_data.py CURRENT_PL_CLUBS_EN 保持一致）
CURRENT_PL_CLUBS = {
    'Arsenal', 'Aston Villa', 'Bournemouth',
    'Brentford', 'Brighton & Hove Albion', 'Burnley', 'Chelsea', 'Crystal Palace',
    'Everton', 'Fulham', 'Leeds United',
    'Liverpool', 'Manchester City', 'Manchester United',
    'Newcastle United', 'Nottingham Forest', 'Sunderland',
    'Tottenham Hotspur', 'West Ham United', 'Wolverhampton Wanderers',
}

HALL_OF_FAME = {
    'alan shearer':     2021, 'thierry henry':   2021, 'eric cantona':    2021,
    'roy keane':        2021, 'frank lampard':   2021, 'dennis bergkamp': 2021,
    'steven gerrard':   2021, 'david beckham':   2021,
    'sergio agüero':    2022, 'didier drogba':   2022, 'vincent kompany': 2022,
    'peter schmeichel': 2022, 'paul scholes':    2022, 'ian wright':      2022,
    'tony adams':       2023, 'petr cech':       2023, 'rio ferdinand':   2023,
    'ashley cole':      2024, 'andrew cole':     2024, 'john terry':      2024,
    'gary neville':     2025, 'eden hazard':     2025,
}

TEAM_XI_AWARD_MAP = {
    'Premier League 10 Seasons Awards': '10年最佳阵容',
    'Premier League 20 Seasons Awards': '20年最佳阵容',
}


def generate_simple_players_json():
    df = pd.read_csv('data/premier_league_players_merged_final.csv')

    # Load award CSVs
    goals_df = pd.read_csv('data/pl_100_goals_club.csv')
    clean_sheets_df = pd.read_csv('data/pl_100_clean_sheets_gk.csv')
    golden_boots_df = pd.read_csv('data/pl_golden_boot_winners.csv')
    golden_gloves_df = pd.read_csv('data/pl_golden_glove_winners.csv')
    pots_df = pd.read_csv('data/pl_player_of_season_winners.csv')
    titles_df = pd.read_csv('data/pl_players_3plus_titles.csv')
    team_xi_df = pd.read_csv('data/pl_team_10y_20y_award_xi.csv')

    # Pre-aggregate: player_id → comma-joined season strings
    gb_seasons = (
        golden_boots_df.groupby('player_id')['Season']
        .apply(lambda s: ', '.join(str(x) for x in sorted(set(s))))
        .to_dict()
    )
    gg_col = 'Season' if 'Season' in golden_gloves_df.columns else golden_gloves_df.columns[1]
    gg_seasons = (
        golden_gloves_df.groupby('player_id')[gg_col]
        .apply(lambda s: ', '.join(str(x) for x in sorted(set(s))))
        .to_dict()
    )
    pots_seasons = (
        pots_df.groupby('player_id')['Season']
        .apply(lambda s: ', '.join(str(x) for x in sorted(set(s))))
        .to_dict()
    )
    # Team XI: group by player, deduplicate award types
    xi_by_player = (
        team_xi_df.drop_duplicates(subset=['player_id', 'award'])
        .groupby('player_id')['award'].apply(list).to_dict()
    )

    # Goals / clean-sheets lookup
    goals_lookup = {
        int(r['player_id']): int(r['Premier League total goals'])
        for _, r in goals_df.iterrows()
        if pd.notna(r.get('Premier League total goals'))
    }
    cs_lookup = {
        int(r['player_id']): int(r['Premier League total clean sheets'])
        for _, r in clean_sheets_df.iterrows()
        if pd.notna(r.get('Premier League total clean sheets'))
    }
    # Titles lookup
    titles_lookup = {
        int(r['player_id']): r
        for _, r in titles_df.iterrows()
    }

    def _clean(val):
        s = str(val).strip() if pd.notna(val) else ''
        return '' if s in ('nan', '---', '-') else s

    def _normalize_club(name):
        """Strip common FC/AFC suffixes/prefixes so Transfermarkt names match CURRENT_PL_CLUBS."""
        n = name.strip()
        for suffix in (' FC', ' AFC', ' SC', ' SFC'):
            if n.endswith(suffix):
                return n[:-len(suffix)].strip()
        for prefix in ('FC ', 'AFC '):
            if n.startswith(prefix):
                return n[len(prefix):].strip()
        return n

    # player_status_all.csv 存在时 is_retired 列已合并进来，是唯一权威来源
    has_all_status = 'is_retired' in df.columns

    players = []

    for _, row in df.iterrows():
        pid_raw = row.get('player_id')
        if pd.isna(pid_raw):
            continue
        pid = int(pid_raw)

        # Names
        name_en = str(row['player_name']) if pd.notna(row.get('player_name')) else ''
        name_cn = str(row['player_name_zh']) if pd.notna(row.get('player_name_zh')) and str(row.get('player_name_zh', '')).strip() else name_en

        # Clubs (semicolon-separated)
        clubs = []
        if pd.notna(row.get('xlsx_clubs')):
            clubs = [c.strip() for c in str(row['xlsx_clubs']).split(';') if c.strip()]

        # Total appearances
        app_count = int(row['appearances']) if pd.notna(row.get('appearances')) else 0

        # Single-club appearances (from merged CSV multi columns)
        # Capture 180+ for near-miss display; achievement requires >= 200
        single_club = None
        single_club_apps = None
        for i in (1, 2, 3):
            t_col = f'multi_team{i}'
            a_col = f'multi_team{i}_appearances'
            if pd.notna(row.get(t_col)) and pd.notna(row.get(a_col)):
                t = str(row[t_col]).strip()
                a = float(row[a_col])
                if t and a >= 180 and single_club is None:
                    single_club = t
                    single_club_apps = a

        current_club = _clean(row.get('current_team', ''))

        club_for_check = _normalize_club(current_club) if current_club else ''

        if has_all_status:
            # 全量退役状态（scrape_player_status.py 提供，最权威）
            # 优先级：is_retired → current_team vs PL clubs
            is_ret = _clean(row.get('is_retired', '')).lower()
            if is_ret == 'yes':
                player_status = 'retired'
            elif club_for_check in CURRENT_PL_CLUBS:
                player_status = 'active_pl'
            elif current_club and is_ret == 'no':
                player_status = 'active_not_pl'
            else:
                player_status = 'retired'
        else:
            # 兜底：使用 multi_is_retired + epl250_is_retired（无全量状态时）
            multi_ret  = _clean(row.get('multi_is_retired', '')).lower()
            epl250_ret = _clean(row.get('epl250_is_retired', '')).lower()
            if multi_ret == 'yes':
                player_status = 'retired'
            elif club_for_check in CURRENT_PL_CLUBS:
                player_status = 'active_pl'
            elif current_club and multi_ret == 'no':
                player_status = 'active_not_pl'
            elif epl250_ret == 'false':
                player_status = 'active_pl'
            else:
                player_status = 'retired'

        # Hall of Fame
        hof_year = HALL_OF_FAME.get(name_en.lower())
        if hof_year:
            player_status = 'hall_of_fame'

        # Achievements
        achievements = []

        # 出场250次
        if app_count >= 250:
            achievements.append({'type': '出场250次', 'detail': f'{app_count}场'})

        # 单队200场（achievement only at >= 200; 180-199 stored for near-miss display）
        if single_club is not None and single_club_apps >= 200:
            achievements.append({
                'type': '单队200场',
                'detail': f'{single_club}|{int(single_club_apps)}',
            })

        # 百球 (achievement only if >= 100; 80-99 stored in goals for near-miss display)
        goals_val = goals_lookup.get(pid)
        if goals_val is not None and goals_val >= 100:
            achievements.append({'type': '百球', 'detail': str(goals_val)})

        # 百大零封 (achievement only if >= 100)
        cs_val = cs_lookup.get(pid)
        if cs_val is not None and cs_val >= 100:
            achievements.append({'type': '百大零封', 'detail': str(cs_val)})

        # 金靴奖
        if pid in gb_seasons:
            achievements.append({'type': '金靴奖', 'detail': gb_seasons[pid]})

        # 金手套奖
        if pid in gg_seasons:
            achievements.append({'type': '金手套奖', 'detail': gg_seasons[pid]})

        # 年度最佳
        if pid in pots_seasons:
            achievements.append({'type': '年度最佳', 'detail': pots_seasons[pid]})

        # 三冠王
        if pid in titles_lookup:
            t_row = titles_lookup[pid]
            seasons_str = str(t_row['seasons']) if pd.notna(t_row.get('seasons')) else ''
            clubs_str = str(t_row['clubs']) if pd.notna(t_row.get('clubs')) else ''
            achievements.append({'type': '三冠王', 'detail': f'{seasons_str}§{clubs_str}'})

        # 最佳阵容 (10周年 / 20周年)
        if pid in xi_by_player:
            for award in xi_by_player[pid]:
                zh_type = TEAM_XI_AWARD_MAP.get(award, '最佳阵容')
                achievements.append({'type': zh_type, 'detail': ''})

        players.append({
            'id': pid,
            'name_en': name_en,
            'name_cn': name_cn,
            'nationality': str(row['nationality']) if pd.notna(row.get('nationality')) else '',
            'position': str(row['position']) if pd.notna(row.get('position')) else '',
            'clubs': clubs,
            'total_appearances': app_count,
            'single_club_appearances': single_club_apps,
            'single_club_name': single_club,
            'goals': goals_val,
            'clean_sheets': cs_val,
            'current_club': current_club,
            'birth_date': str(row['birth_date']) if pd.notna(row.get('birth_date')) else '',
            'hof_year': hof_year,
            'player_status': player_status,
            'achievements': achievements,
        })

    output_path = Path('../frontend/public/data/players.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(players, f, ensure_ascii=False, indent=2)

    qualified = sum(1 for p in players if p['achievements'])
    print(f"Generated {len(players)} players ({qualified} with achievements) → {output_path}")


if __name__ == "__main__":
    generate_simple_players_json()
