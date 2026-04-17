#!/usr/bin/env python3
import pandas as pd
import json
from pathlib import Path

# 2024/25 Premier League clubs (used only to disambiguate active_pl vs active_not_pl
# for players whose epl250/multi scrapers have NaN — do NOT expand this list loosely)
CURRENT_PL_CLUBS = {
    'Arsenal', 'Aston Villa', 'Bournemouth', 'AFC Bournemouth',
    'Brentford', 'Brighton & Hove Albion', 'Chelsea', 'Crystal Palace',
    'Everton', 'Fulham', 'Ipswich Town', 'Leicester City',
    'Liverpool', 'Manchester City', 'Manchester United',
    'Newcastle United', 'Nottingham Forest', 'Southampton',
    'Tottenham Hotspur', 'West Ham United', 'Wolverhampton Wanderers',
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

    # PulseLive index for current club / retired status
    try:
        pl_index = pd.read_csv('data/pulselive_player_index_appearances.csv')
        pl_info = {
            int(r['player_id']): {
                'retired': int(r.get('retired', 0)),
                'current_club': str(r.get('current_club', '') or ''),
            }
            for _, r in pl_index.iterrows()
        }
    except Exception:
        pl_info = {}

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
        single_club = None
        single_club_apps = None
        for i in (1, 2, 3):
            t_col = f'multi_team{i}'
            a_col = f'multi_team{i}_appearances'
            if pd.notna(row.get(t_col)) and pd.notna(row.get(a_col)):
                t = str(row[t_col]).strip()
                a = float(row[a_col])
                if t and a >= 200:
                    if single_club is None:
                        single_club = t
                        single_club_apps = a

        # Player status
        # epl250_is_retired: PulseLive owner.active → False=currently in PL, True=left PL
        # multi_is_retired:  Transfermarkt "Retired" text → no=still playing, yes=retired
        pli = pl_info.get(pid, {})
        epl250_ret = str(row.get('epl250_is_retired', '')).strip().lower()
        multi_ret   = str(row.get('multi_is_retired', '')).strip().lower()
        current_club = str(pli.get('current_club', '') or row.get('current_team', '') or '')

        if epl250_ret == 'false':
            # PulseLive confirms currently active in PL
            player_status = 'active_pl'
        elif epl250_ret in ('true', '1', 'yes'):
            # Left PL per PulseLive — check if still playing elsewhere
            if multi_ret == 'no':
                player_status = 'active_not_pl'
            else:
                player_status = 'retired'
        else:
            # Not in 250+ list (epl250=NaN) — use multi_is_retired + current_club
            if multi_ret == 'yes':
                player_status = 'retired'
            elif multi_ret == 'no':
                # Transfermarkt says still playing; check if current club is PL
                if current_club in CURRENT_PL_CLUBS:
                    player_status = 'active_pl'
                else:
                    player_status = 'active_not_pl'
            else:
                # Award-only (both NaN) — no scraper confirmation; default retired.
                # fetch_active_status.py must be run manually to set accurate status.
                player_status = 'retired'

        # Achievements
        achievements = []

        # 出场250次
        if app_count >= 250:
            achievements.append({'type': '出场250次', 'detail': f'{app_count}场'})

        # 单队200场
        if single_club is not None:
            achievements.append({
                'type': '单队200场',
                'detail': f'{single_club}|{int(single_club_apps)}',
            })

        # 百球
        goals_val = goals_lookup.get(pid)
        if goals_val is not None:
            achievements.append({'type': '百球', 'detail': str(goals_val)})

        # 百大零封
        cs_val = cs_lookup.get(pid)
        if cs_val is not None:
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
            'current_club': pli.get('current_club', '') or str(row.get('current_team', '') or ''),
            'birth_date': str(row['birth_date']) if pd.notna(row.get('birth_date')) else '',
            'hof_year': None,
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
