"""
fetch_new_player_info.py
========================
为"新出现在总表里的球员"补全：
  1. 官方简体中文译名（via zh.wikipedia.org uselang=zh-hans）
  2. 所效力过的英超俱乐部（via Pulselive API —— 仅英超数据，天然保证球队在英超联赛内）

使用场景：
  每次 merge_player_data.py 生成新版 players.json 后运行本脚本，
  它会找出 player_id 不在 xlsx 文件中的球员，自动填充并追加保存。

Usage:
    python fetch_new_player_info.py

输出：
  - data/premier_league_players_name_Chinese.xlsx   （追加新行）
  - data/premier_league_players_history_clubs.xlsx  （追加新行）
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import List, Optional

import pandas as pd
import requests

DATA_DIR = Path(__file__).parent / "data"
PLAYERS_JSON = Path(__file__).parent.parent / "frontend" / "public" / "data" / "players.json"
CN_XLSX     = DATA_DIR / "premier_league_players_name_Chinese.xlsx"
CLUBS_XLSX  = DATA_DIR / "premier_league_players_history_clubs.xlsx"

PL_BASE  = "https://footballapi.pulselive.com"
WIKI_EN  = "https://en.wikipedia.org/w/api.php"
WIKI_ZH  = "https://zh.wikipedia.org/w/api.php"


# ── HTTP sessions ─────────────────────────────────────────────────────────────

def _make_pl_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Origin": "https://www.premierleague.com",
        "Referer": "https://www.premierleague.com/",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/120 Safari/537.36"
        ),
    })
    return s


def _make_wiki_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "PremierHallBot/1.0 (liguangzhaolvcatlee@gmail.com)"})
    return s


# ── Chinese name lookup ───────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    import html
    return re.sub(r"<[^>]+>", "", html.unescape(text)).strip()


def _clean_zh_title(title: str) -> str:
    return re.sub(r"\s*（[^）]*）$", "", re.sub(r"\s*\([^)]*\)$", "", title)).strip()


def _zh_title_to_simplified(zh_title: str, session: requests.Session) -> str:
    """Call zh.wikipedia.org with uselang=zh-hans to get Simplified Chinese displaytitle."""
    try:
        resp = session.get(WIKI_ZH, params={
            "action": "parse", "page": zh_title,
            "prop": "displaytitle", "uselang": "zh-hans", "format": "json",
        }, timeout=15)
        data = resp.json()
        if "error" not in data:
            raw = data.get("parse", {}).get("displaytitle", "")
            result = _strip_html(raw)
            if result:
                return result
    except Exception:
        pass
    return zh_title


def _get_zh_langlink(en_title: str, session: requests.Session) -> Optional[str]:
    try:
        resp = session.get(WIKI_EN, params={
            "action": "query", "titles": en_title,
            "prop": "langlinks", "lllang": "zh",
            "format": "json", "redirects": 1,
        }, timeout=10)
        pages = resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            if page.get("ns", -1) != 0:
                continue
            for ll in page.get("langlinks", []):
                if ll.get("lang") == "zh":
                    return _clean_zh_title(ll.get("*", ""))
    except Exception:
        pass
    return None


def fetch_chinese_name(player_name: str, wiki_session: requests.Session) -> Optional[str]:
    """Return Simplified Chinese Mandarin name, or None if not found."""
    zh_title = _get_zh_langlink(player_name, wiki_session)

    if not zh_title:
        # Try search fallback
        try:
            resp = wiki_session.get(WIKI_EN, params={
                "action": "query", "list": "search",
                "srsearch": f"{player_name} footballer Premier League",
                "format": "json", "srlimit": 3,
            }, timeout=10)
            for hit in resp.json().get("query", {}).get("search", [])[:2]:
                candidate = hit["title"]
                if any(s in candidate.lower() for s in ["season", "club", "f.c.", "league"]):
                    continue
                zh_title = _get_zh_langlink(candidate, wiki_session)
                if zh_title:
                    break
                time.sleep(0.3)
        except Exception:
            pass

    if not zh_title:
        return None

    time.sleep(0.3)
    return _zh_title_to_simplified(zh_title, wiki_session)


# ── PL clubs lookup ───────────────────────────────────────────────────────────

def fetch_pl_clubs(player_id: int, pl_session: requests.Session) -> List[str]:
    """
    Fetch current + previous PL clubs from the Pulselive player profile.
    Only PL clubs appear here — no need for additional filtering.
    Returns a list of club short names (may have 1-2 entries only).
    """
    try:
        resp = pl_session.get(
            f"{PL_BASE}/football/players/{player_id}",
            params={"altIds": "true"}, timeout=20
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        clubs: List[str] = []
        noise = {"", "FIRST", "U21", "U18"}

        def _pick(team_dict) -> Optional[str]:
            if not isinstance(team_dict, dict):
                return None
            club = team_dict.get("club") or team_dict
            nm = (club.get("shortName") or club.get("name")
                  or team_dict.get("shortName") or team_dict.get("name"))
            return str(nm).strip() if nm and str(nm).strip() not in noise else None

        for key in ("currentTeam", "previousTeam"):
            nm = _pick(data.get(key))
            if nm and nm not in clubs:
                clubs.append(nm)
        return clubs
    except Exception:
        return []


# ── Load / save xlsx ──────────────────────────────────────────────────────────

def _load_xlsx_ids(path: Path) -> set:
    if not path.exists():
        return set()
    try:
        df = pd.read_excel(path, usecols=["player_id"])
        return set(df["player_id"].dropna().astype(int).tolist())
    except Exception:
        return set()


def _append_to_xlsx(path: Path, new_rows: list[dict], columns: list[str]) -> None:
    new_df = pd.DataFrame(new_rows, columns=columns)
    if path.exists():
        existing = pd.read_excel(path)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df
    combined.to_excel(path, index=False)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if not PLAYERS_JSON.exists():
        print(f"ERROR: {PLAYERS_JSON} not found. Run merge_player_data.py first.")
        return

    with open(PLAYERS_JSON, encoding="utf-8") as f:
        players = json.load(f)

    # Find player_ids already in xlsx files
    existing_cn_ids    = _load_xlsx_ids(CN_XLSX)
    existing_clubs_ids = _load_xlsx_ids(CLUBS_XLSX)
    already_done = existing_cn_ids & existing_clubs_ids

    # New players: in players.json but not fully in both xlsx files
    new_players = [p for p in players if p["id"] not in already_done]
    print(f"Total players: {len(players)} | New (not in xlsx): {len(new_players)}")

    if not new_players:
        print("Nothing to do.")
        return

    pl_session   = _make_pl_session()
    wiki_session = _make_wiki_session()

    new_cn_rows    = []
    new_clubs_rows = []

    for i, player in enumerate(new_players, 1):
        pid  = player["id"]
        name = player["name_en"]
        print(f"[{i}/{len(new_players)}] {name} (id={pid})")

        # ── Chinese name ──────────────────────────────────────────────────────
        if pid not in existing_cn_ids:
            # Try JSON cache first
            cn_name_from_json = player.get("name_cn", "")
            has_cjk = bool(re.search(r"[\u4e00-\u9fff]", cn_name_from_json))
            if has_cjk:
                zh_name = cn_name_from_json
                print(f"  中文名（来自现有数据）: {zh_name}")
            else:
                zh_name = fetch_chinese_name(name, wiki_session)
                if zh_name:
                    print(f"  中文名（Wikipedia）: {zh_name}")
                else:
                    zh_name = name
                    print(f"  中文名: 未找到，保留英文")
            new_cn_rows.append({
                "player_id": pid,
                "player_name": name,
                "player_name_zh": zh_name,
            })

        # ── PL clubs ──────────────────────────────────────────────────────────
        if pid not in existing_clubs_ids:
            # Use clubs already in players.json (already filtered to PL clubs by pipeline)
            clubs_from_json = player.get("clubs", [])
            if clubs_from_json:
                clubs_str = "\uff1b".join(clubs_from_json)
                print(f"  俱乐部（来自现有数据）: {clubs_str}")
            else:
                # Fallback: fetch from Pulselive API
                clubs = fetch_pl_clubs(pid, pl_session)
                clubs_str = "\uff1b".join(clubs) if clubs else ""
                print(f"  俱乐部（Pulselive API）: {clubs_str or '未找到'}")
                time.sleep(0.2)
            new_clubs_rows.append({
                "player_id": pid,
                "player_name": name,
                "效力英超球队": clubs_str,
            })

        time.sleep(0.5)

    # Save results
    if new_cn_rows:
        _append_to_xlsx(CN_XLSX, new_cn_rows, ["player_id", "player_name", "player_name_zh"])
        print(f"\n已追加 {len(new_cn_rows)} 条中文名 → {CN_XLSX}")
    if new_clubs_rows:
        _append_to_xlsx(CLUBS_XLSX, new_clubs_rows, ["player_id", "player_name", "效力英超球队"])
        print(f"已追加 {len(new_clubs_rows)} 条俱乐部记录 → {CLUBS_XLSX}")

    print("\n完成。重新运行 merge_player_data.py 以更新 players.json。")


if __name__ == "__main__":
    main()
