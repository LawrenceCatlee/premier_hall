"""
fetch_all_chinese_names.py
==========================
One-time script: fetch Chinese names for ALL players in the merged CSV.

Usage:
    python fetch_all_chinese_names.py

Output:
    backend/data/player_chinese_names.json

The JSON maps lowercase English player name → Chinese name, e.g.:
    {"james milner": "詹姆斯·米尔纳", ...}

Strategy:
  1. Pre-seed from the hardcoded SEED_MAP below (already curated names).
  2. For players not in the seed, query Wikipedia interlanguage links.
  3. Save everything to data/player_chinese_names.json.

This script is NOT part of the automated pipeline. Run it manually when you
want to refresh the full name mapping (e.g. after a new season of new players
has been pulled by the data scripts).
"""

import json
import time
import re
import requests
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
CN_NAMES_FILE = DATA_DIR / "player_chinese_names.json"
MERGED_CSV = DATA_DIR / "premier_league_players_merged_final.csv"
WIKI_API = "https://en.wikipedia.org/w/api.php"

ZH_API = "https://zh.wikipedia.org/w/api.php"


def _strip_html(text: str) -> str:
    import html as _html
    return re.sub(r'<[^>]+>', '', _html.unescape(text)).strip()


def _clean_zh_title(title: str) -> str:
    """Strip disambiguation suffixes like (足球运动员) from Wikipedia page titles."""
    return re.sub(r'\s*（[^）]*）$', '', re.sub(r'\s*\([^)]*\)$', '', title)).strip()


def _zh_title_to_mandarin(zh_title: str, session: requests.Session) -> str:
    """
    Convert a zh.wikipedia.org page title to Simplified Chinese Mandarin
    by calling zh.wikipedia.org with uselang=zh-hans.
    Returns the displaytitle, or the original title on failure.
    """
    try:
        resp = session.get(ZH_API, params={
            'action': 'parse',
            'page': zh_title,
            'prop': 'displaytitle',
            'uselang': 'zh-hans',
            'format': 'json',
        }, timeout=15)
        data = resp.json()
        if 'error' not in data:
            raw = data.get('parse', {}).get('displaytitle', '')
            result = _strip_html(raw)
            if result:
                return result
    except Exception:
        pass
    return zh_title


def fetch_zh_name_via_wiki(player_name: str) -> str | None:
    """
    Try English Wikipedia interlanguage links to find the Chinese name,
    then convert via zh.wikipedia.org to Simplified Chinese Mandarin.
    Returns the Simplified Chinese name, or None if not found.
    """
    session = requests.Session()
    session.headers.update({'User-Agent': 'PremierHallBot/1.0 (liguangzhaolvcatlee@gmail.com)'})

    def _get_langlink(title: str) -> str | None:
        try:
            resp = session.get(WIKI_API, params={
                'action': 'query',
                'titles': title,
                'prop': 'langlinks',
                'lllang': 'zh',
                'format': 'json',
                'redirects': 1,
            }, timeout=10)
            pages = resp.json().get('query', {}).get('pages', {})
            for page in pages.values():
                if page.get('ns', -1) != 0:
                    continue
                for ll in page.get('langlinks', []):
                    if ll.get('lang') == 'zh':
                        return _clean_zh_title(ll.get('*', ''))
        except Exception:
            pass
        return None

    # 1. Direct title lookup
    zh_title = _get_langlink(player_name)

    # 2. Search Wikipedia for footballer if not found
    if not zh_title:
        try:
            resp = session.get(WIKI_API, params={
                'action': 'query',
                'list': 'search',
                'srsearch': f'{player_name} footballer Premier League',
                'format': 'json',
                'srlimit': 3,
            }, timeout=10)
            results = resp.json().get('query', {}).get('search', [])
            for hit in results[:2]:
                candidate = hit['title']
                if any(skip in candidate.lower() for skip in ['season', 'club', 'f.c.', 'league']):
                    continue
                zh_title = _get_langlink(candidate)
                if zh_title:
                    break
                time.sleep(0.3)
        except Exception:
            pass

    if not zh_title:
        return None

    # 3. Convert zh.wikipedia.org title to Simplified Chinese Mandarin
    time.sleep(0.3)
    return _zh_title_to_mandarin(zh_title, session)


def load_existing_names() -> dict[str, str]:
    """Load the existing player_chinese_names.json if it exists."""
    if CN_NAMES_FILE.exists():
        with open(CN_NAMES_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_names(names: dict[str, str]) -> None:
    CN_NAMES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CN_NAMES_FILE, 'w', encoding='utf-8') as f:
        json.dump(dict(sorted(names.items())), f, ensure_ascii=False, indent=2)
    print(f"Saved {len(names)} entries → {CN_NAMES_FILE}")


def main() -> None:
    # Load player names from merged CSV
    if not MERGED_CSV.exists():
        print(f"ERROR: {MERGED_CSV} not found. Run merge_player_data.py first.")
        return

    df = pd.read_csv(MERGED_CSV, usecols=['player_name'])
    all_names = df['player_name'].dropna().str.strip().unique().tolist()
    print(f"Found {len(all_names)} players in merged CSV.")

    # Start from existing JSON (preserves any manual corrections)
    result = load_existing_names()

    # Find players still missing a Chinese name
    missing = [n for n in all_names if n.lower() not in result]
    print(f"{len(missing)} players need Wikipedia lookup.")

    for i, name in enumerate(missing, 1):
        print(f"[{i}/{len(missing)}] Looking up: {name} ...", end=' ', flush=True)
        zh = fetch_zh_name_via_wiki(name)
        if zh:
            print(f"→ {zh}")
            result[name.lower()] = zh
        else:
            print("→ not found")
            # Fallback: keep the English name so the JSON entry exists
            result[name.lower()] = name

        # Save incrementally every 20 players so we don't lose progress
        if i % 20 == 0:
            save_names(result)

        time.sleep(0.5)  # be polite to Wikipedia

    save_names(result)
    print("Done.")


if __name__ == '__main__':
    main()
