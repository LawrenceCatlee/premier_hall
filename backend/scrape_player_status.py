#!/usr/bin/env python3
"""
scrape_player_status.py

Scrapes ALL Transfermarkt club history pages to determine is_retired and
current_team for every player in the PulseLive index.

Method: same as player_premier_team_200.py — check "Retired" text on each
player's row on the club's all-time appearances page.

Output: data/player_status_all.csv  (player_id, is_retired, current_team)

This script is run manually (not in CI). Commit the output CSV so that
merge_player_data.py can pick it up without re-scraping.

Usage:
    cd backend
    python scrape_player_status.py
"""

import requests
from bs4 import BeautifulSoup
from player_name_normalizer import clean_player_name
from player_name_mapper import standardize_player_name
from pulselive_data import get_pulselive_player_index
import pandas as pd
import time
from pathlib import Path

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}

OUT_PATH = Path('data/player_status_all.csv')
DELAY_SECS = 2


def _build_name_lookup() -> dict:
    """Return {normalized_name: player_id} from PulseLive index (all players)."""
    pl_df = get_pulselive_player_index().copy()
    lookup: dict = {}
    for _, row in pl_df.iterrows():
        pid = row.get('player_id')
        name = str(row.get('player_name', '') or '').strip()
        if pd.isna(pid) or not name:
            continue
        pid = int(pid)
        for variant in (
            name.lower(),
            standardize_player_name(name).lower(),
            clean_player_name(name).lower(),
        ):
            if variant and variant not in lookup:
                lookup[variant] = pid
    return lookup


def _scrape_club(team_name: str, url: str) -> list:
    """
    Scrape a Transfermarkt club history page. Returns list of dicts:
      {player_name, is_retired, current_team}
    for every player row found (no appearance filter).
    """
    print(f'  {team_name} ...', flush=True)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f'    ERROR: {e}')
        return []

    soup = BeautifulSoup(resp.content, 'html.parser')
    table = soup.find('table', class_='items') or soup.find('table')
    if not table:
        print(f'    no table found')
        return []

    results = []
    seen: set = set()

    for row in table.find_all('tr')[1:]:
        cells = row.find_all('td')
        if len(cells) < 2:
            continue

        # Player name from img alt attribute
        player_name = ''
        player_cell_idx = -1
        for i, cell in enumerate(cells):
            img = cell.find('img', alt=True)
            if img and img.get('alt', '').strip():
                player_name = img['alt'].strip()
                player_cell_idx = i
                break

        if not player_name or player_name in seen:
            continue
        seen.add(player_name)

        # Retirement: "Retired" text in any cell
        is_retired = any('Retired' in cell.get_text(strip=True) for cell in cells)

        # Current team (only meaningful when not retired)
        current_team = ''
        if not is_retired:
            for cell_idx in (1, 4):
                if cell_idx >= len(cells):
                    continue
                text = cells[cell_idx].get_text(strip=True)
                if cell_idx == 1 and text.startswith(player_name):
                    text = text[len(player_name):].strip()
                if text and len(text) > 2 and 'Without Club' not in text and text != player_name:
                    current_team = text
                    break

        results.append({
            'player_name_tm': player_name,
            'is_retired': is_retired,
            'current_team': current_team,
        })

    return results


def main() -> None:
    print('Building name → player_id lookup from PulseLive index...')
    name_lookup = _build_name_lookup()
    print(f'  {len(name_lookup)} name variants indexed')

    # Load club URLs
    teams_df = pd.read_excel('data/Team_transfer_link.xlsx', header=None)
    teams_df.columns = ['team_name', 'url']
    teams_df = teams_df.dropna()
    print(f'\nScraping {len(teams_df)} clubs...')

    # player_id → {is_retired, current_team}
    # Priority: first non-retired result wins; if only retired found, mark retired
    status_map: dict = {}       # pid → entry once confirmed active
    retired_map: dict = {}      # pid → entry when only retired found so far

    for _, trow in teams_df.iterrows():
        team_name = str(trow['team_name'])
        url = str(trow['url'])

        players = _scrape_club(team_name, url)

        for p in players:
            tm_name = p['player_name_tm']
            # Try name variants for matching
            pid = None
            for variant in (
                tm_name.lower(),
                standardize_player_name(tm_name).lower(),
                clean_player_name(tm_name).lower(),
            ):
                pid = name_lookup.get(variant)
                if pid:
                    break

            if not pid:
                continue

            entry = {
                'player_id': pid,
                'is_retired': 'yes' if p['is_retired'] else 'no',
                'current_team': p['current_team'],
            }

            if not p['is_retired']:
                # Active: store immediately, overwrite any previous retired entry
                status_map[pid] = entry
            elif pid not in status_map:
                # Retired and not yet confirmed active
                retired_map[pid] = entry

        time.sleep(DELAY_SECS)

    # Merge: active_map wins over retired_map
    combined = {**retired_map, **status_map}
    print(f'\nMatched {len(combined)} players '
          f'({sum(1 for v in combined.values() if v["is_retired"]=="no")} active, '
          f'{sum(1 for v in combined.values() if v["is_retired"]=="yes")} retired)')

    # Players in PulseLive index but not found on any club page → retired (conservative)
    all_pids = {int(pid) for pid in get_pulselive_player_index()['player_id'].dropna()}
    not_found = all_pids - set(combined.keys())
    print(f'  {len(not_found)} players not found on any club page → marked retired')

    rows = list(combined.values())
    for pid in not_found:
        rows.append({'player_id': pid, 'is_retired': 'yes', 'current_team': ''})

    df = pd.DataFrame(rows, columns=['player_id', 'is_retired', 'current_team'])
    df = df.sort_values('player_id').reset_index(drop=True)

    Path('data').mkdir(exist_ok=True)
    df.to_csv(OUT_PATH, index=False, encoding='utf-8-sig')
    print(f'\nSaved {len(df)} rows → {OUT_PATH}')


if __name__ == '__main__':
    main()
