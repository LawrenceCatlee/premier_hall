"""
fetch_new_chinese_names.py
==========================
Incremental script: fetch Chinese names for players NOT yet in
data/player_chinese_names.json.

Usage:
    python fetch_new_chinese_names.py

Run this after the data pipeline has pulled in new players and you want
to fill in their Chinese names without re-running the full lookup.
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
ZH_API   = "https://zh.wikipedia.org/w/api.php"


def _strip_html(text: str) -> str:
    import html as _html
    return re.sub(r'<[^>]+>', '', _html.unescape(text)).strip()


def _clean_zh_title(title: str) -> str:
    return re.sub(r'\s*（[^）]*）$', '', re.sub(r'\s*\([^)]*\)$', '', title)).strip()


def _zh_title_to_mandarin(zh_title: str, session: requests.Session) -> str:
    try:
        resp = session.get(ZH_API, params={
            'action': 'parse', 'page': zh_title,
            'prop': 'displaytitle', 'uselang': 'zh-hans', 'format': 'json',
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
    session = requests.Session()
    session.headers.update({'User-Agent': 'PremierHallBot/1.0 (liguangzhaolvcatlee@gmail.com)'})

    def _get_langlink(title: str) -> str | None:
        try:
            resp = session.get(WIKI_API, params={
                'action': 'query', 'titles': title,
                'prop': 'langlinks', 'lllang': 'zh',
                'format': 'json', 'redirects': 1,
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

    zh_title = _get_langlink(player_name)

    if not zh_title:
        try:
            resp = session.get(WIKI_API, params={
                'action': 'query', 'list': 'search',
                'srsearch': f'{player_name} footballer Premier League',
                'format': 'json', 'srlimit': 3,
            }, timeout=10)
            results = resp.json().get('query', {}).get('search', [])
            for hit in results[:2]:
                candidate = hit['title']
                if any(s in candidate.lower() for s in ['season', 'club', 'f.c.', 'league']):
                    continue
                zh_title = _get_langlink(candidate)
                if zh_title:
                    break
                time.sleep(0.3)
        except Exception:
            pass

    if not zh_title:
        return None

    time.sleep(0.3)
    return _zh_title_to_mandarin(zh_title, session)


def main() -> None:
    if not MERGED_CSV.exists():
        print(f"ERROR: {MERGED_CSV} not found. Run merge_player_data.py first.")
        return

    # Load current name mapping
    existing: dict[str, str] = {}
    if CN_NAMES_FILE.exists():
        with open(CN_NAMES_FILE, encoding='utf-8') as f:
            existing = json.load(f)
        print(f"Loaded {len(existing)} existing entries from {CN_NAMES_FILE}")
    else:
        print("No existing player_chinese_names.json — run fetch_all_chinese_names.py first.")

    df = pd.read_csv(MERGED_CSV, usecols=['player_name'])
    all_names = df['player_name'].dropna().str.strip().unique().tolist()

    # Only process players not yet in the JSON
    new_names = [n for n in all_names if n.lower() not in existing]
    print(f"{len(new_names)} new players need lookup.")

    if not new_names:
        print("Nothing to do.")
        return

    for i, name in enumerate(new_names, 1):
        print(f"[{i}/{len(new_names)}] {name} ...", end=' ', flush=True)
        zh = fetch_zh_name_via_wiki(name)
        if zh:
            print(f"→ {zh}")
            existing[name.lower()] = zh
        else:
            print("→ not found (keeping English)")
            existing[name.lower()] = name

        if i % 20 == 0:
            CN_NAMES_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CN_NAMES_FILE, 'w', encoding='utf-8') as f:
                json.dump(dict(sorted(existing.items())), f, ensure_ascii=False, indent=2)

        time.sleep(0.5)

    CN_NAMES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CN_NAMES_FILE, 'w', encoding='utf-8') as f:
        json.dump(dict(sorted(existing.items())), f, ensure_ascii=False, indent=2)
    print(f"Done. Saved {len(existing)} entries → {CN_NAMES_FILE}")


if __name__ == '__main__':
    main()
