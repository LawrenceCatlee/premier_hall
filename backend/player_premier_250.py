from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import requests
import pandas as pd


BASE = "https://footballapi.pulselive.com"
OUT_PATH = Path("data") / "epl_players_appearances_230plus.csv"

MIN_APPS = 230
PAGE_SIZE = 50  # 每页拉取数量；你也可以改成 20/100


def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "Origin": "https://www.premierleague.com",
            "Referer": "https://www.premierleague.com/",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
            ),
        }
    )
    return s


def _get_json(
    session: requests.Session,
    path: str,
    params: Optional[dict] = None,
    retries: int = 5,
) -> Dict[str, Any]:
    url = f"{BASE}{path}"
    last_err: Optional[Exception] = None

    for i in range(retries):
        try:
            resp = session.get(url, params=params, timeout=25)
            if resp.status_code == 429:
                time.sleep(1.5 * (i + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_err = e
            time.sleep(1.2 * (i + 1))

    raise RuntimeError(f"GET {url} failed after {retries} retries: {last_err}") from last_err


def _as_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return int(x)
        if isinstance(x, (int, float)):
            return int(x)
        s = str(x).strip().replace(",", "")
        if s == "":
            return None
        return int(float(s))
    except Exception:
        return None


def _extract_name(owner: Any) -> str:
    if isinstance(owner, dict):
        n = owner.get("name")
        if isinstance(n, str):
            return n.strip()
        if isinstance(n, dict):
            disp = n.get("display")
            if disp:
                return str(disp).strip()
            first = str(n.get("first") or "").strip()
            last = str(n.get("last") or "").strip()
            return (first + " " + last).strip() or "Unknown"
    return "Unknown"


def _ranked_appearances_page(session: requests.Session, page: int, page_size: int) -> List[Dict[str, Any]]:
    params = {
        "page": page,
        "pageSize": page_size,
        "comps": "1",
        "compCodeForActivePlayer": "EN_PR",
        "altIds": "true",
    }
    js = _get_json(session, "/football/stats/ranked/players/appearances", params=params)

    content = None
    if isinstance(js.get("stats"), dict):
        content = js["stats"].get("content")
    if content is None:
        content = js.get("content")
    if not isinstance(content, list):
        return []
    return content


def _player_details(session: requests.Session, player_id: int) -> Dict[str, Any]:
    return _get_json(session, f"/football/players/{player_id}", params={"altIds": "true"})


def _clubs_from_profile(details: Dict[str, Any]) -> List[str]:
    """Extract currentTeam + previousTeam short names from a player profile dict."""
    clubs: List[str] = []
    noise = {"", "FIRST", "U21", "U18"}

    def _pick(team_dict: Any) -> Optional[str]:
        if not isinstance(team_dict, dict):
            return None
        club = team_dict.get("club") or team_dict
        nm = club.get("shortName") or club.get("name") or team_dict.get("shortName") or team_dict.get("name")
        return str(nm).strip() if nm and str(nm).strip() not in noise else None

    for key in ("currentTeam", "previousTeam"):
        nm = _pick(details.get(key))
        if nm and nm not in clubs:
            clubs.append(nm)
    return clubs


def _infer_is_retired(rank_item: Dict[str, Any], details: Dict[str, Any]) -> bool:
    """
    这里返回"近似退役/非英超现役"：
    - 若 details.active / details.isActive 存在：active=True -> not retired
    - 否则用 rank_item.owner.active
    - 再兜底 currentTeam
    """
    for k in ("active", "isActive"):
        if k in details and details[k] is not None:
            return not bool(details[k])

    owner = rank_item.get("owner") or {}
    if isinstance(owner, dict) and owner.get("active") is not None:
        return not bool(owner.get("active"))

    return not bool(details.get("currentTeam"))


def _load_cache() -> Dict[int, Dict[str, Any]]:
    """Load existing CSV into a dict keyed by player_id."""
    if not OUT_PATH.exists():
        return {}
    try:
        df = pd.read_csv(OUT_PATH, encoding="utf-8-sig")
        cache: Dict[int, Dict[str, Any]] = {}
        for _, row in df.iterrows():
            pid = _as_int(row.get("player_id"))
            if pid is not None:
                cache[pid] = row.to_dict()
        print(f"[cache] Loaded {len(cache)} players from {OUT_PATH}", flush=True)
        return cache
    except Exception as e:
        print(f"[cache] Failed to load cache: {e}", flush=True)
        return {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--active-only",
        action="store_true",
        help=(
            "Incremental mode: only re-fetch active EPL players from the API. "
            "Retired/inactive players are kept from the existing CSV cache."
        ),
    )
    args = parser.parse_args()

    session = _make_session()
    Path("data").mkdir(parents=True, exist_ok=True)

    # Load cache (always; used as fallback in active-only mode, or overwritten in full mode)
    cache = _load_cache() if args.active_only else {}

    rows: List[Dict[str, Any]] = []
    seen: Set[int] = set()

    page = 0
    stop = False

    while not stop:
        print(f"[page {page}] fetching appearances ranking...", flush=True)
        items = _ranked_appearances_page(session, page=page, page_size=PAGE_SIZE)
        if not items:
            print(f"[page {page}] no items returned, stopping.", flush=True)
            break

        for it in items:
            owner = it.get("owner") or {}

            player_id = None
            if isinstance(owner, dict):
                player_id = _as_int(owner.get("id") or owner.get("playerId"))

            apps = _as_int(it.get("value") or it.get("statValue") or it.get("total") or it.get("appearances"))
            if apps is None:
                print(f"  [skip] player_id={player_id} — could not parse apps value", flush=True)
                continue

            if apps < MIN_APPS:
                print(f"  [stop] apps={apps} < {MIN_APPS}, done fetching pages.", flush=True)
                stop = True
                break

            if player_id is None or player_id in seen:
                continue
            seen.add(player_id)

            # Fix: name is at item level, not inside owner
            player_name = it.get("name") or _extract_name(owner)
            is_active = bool(owner.get("active")) if isinstance(owner, dict) else False

            if args.active_only and not is_active:
                # --active-only mode: use cached row for retired/inactive players
                if player_id in cache:
                    rows.append(cache[player_id])
                    print(
                        f"  [cache] {player_name} (id={player_id}, apps={apps}) — inactive, using cache.",
                        flush=True,
                    )
                else:
                    # Not in cache yet — add with minimal info (no API call)
                    rows.append(
                        {
                            "player_id": player_id,
                            "player name": player_name,
                            "clubs": "",
                            "total_appearances": apps,
                            "is_retired": True,
                        }
                    )
                    print(
                        f"  [new-inactive] {player_name} (id={player_id}, apps={apps}) — not in cache, added bare.",
                        flush=True,
                    )
                continue

            if is_active:
                # Active player — fetch full profile for clubs + retirement status
                print(f"  [{len(rows)+1}] {player_name} (id={player_id}, apps={apps}) — fetching details...", flush=True)
                details = _player_details(session, player_id)
                clubs = _clubs_from_profile(details)
                is_retired = _infer_is_retired(it, details)
            else:
                # Full mode, inactive — skip expensive API calls
                print(f"  [{len(rows)+1}] {player_name} (id={player_id}, apps={apps}) — inactive, skipping detail fetch.", flush=True)
                details = {}
                ct = owner.get("currentTeam") if isinstance(owner, dict) else None
                clubs = []
                if isinstance(ct, dict):
                    nm = (ct.get("club") or ct).get("shortName") or ct.get("name")
                    if nm:
                        clubs = [str(nm).strip()]
                is_retired = True

            is_retired = _infer_is_retired(it, details) if details else True

            rows.append(
                {
                    "player_id": player_id,
                    "player name": player_name,
                    "clubs": ", ".join(clubs),
                    "total_appearances": apps,
                    "is_retired": bool(is_retired),
                }
            )
            print(f"    -> clubs={clubs}, retired={is_retired}", flush=True)

            time.sleep(0.15)

        page += 1

    df = pd.DataFrame(
        rows,
        columns=["player_id", "player name", "clubs", "total_appearances", "is_retired"],
    )

    # 保护：新抓取结果比缓存少超过 10% 时拒绝覆盖，避免 Cloudflare/API 截断破坏数据
    if OUT_PATH.exists():
        try:
            cached_count = sum(1 for _ in open(OUT_PATH, encoding="utf-8-sig")) - 1  # 减表头
            if len(df) < cached_count * 0.9:
                print(
                    f"[ABORT] 新数据 {len(df)} 行 < 缓存 {cached_count} 行的 90%，"
                    f"疑似抓取不完整，保留旧文件。",
                    flush=True,
                )
                return
        except Exception:
            pass

    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"Saved: {OUT_PATH} (rows={len(df)})", flush=True)


if __name__ == "__main__":
    main()
