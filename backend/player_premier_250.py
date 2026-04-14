from __future__ import annotations

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


def _collect_clubs_from_player_stats(session: requests.Session, player_id: int) -> List[str]:
    js = _get_json(session, f"/football/stats/player/{player_id}", params={"comps": "1", "altIds": "true"})

    clubs: Set[str] = set()

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            c = o.get("club")
            if isinstance(c, dict):
                nm = c.get("shortName") or c.get("name")
                if nm:
                    clubs.add(str(nm).strip())

            t = o.get("team")
            if isinstance(t, dict):
                nm = t.get("shortName") or t.get("name")
                if nm:
                    clubs.add(str(nm).strip())
                c2 = t.get("club")
                if isinstance(c2, dict):
                    nm2 = c2.get("shortName") or c2.get("name")
                    if nm2:
                        clubs.add(str(nm2).strip())

            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for it in o:
                walk(it)

    walk(js)

    noise = {"", "FIRST", "U21", "U18"}
    clubs = {c for c in clubs if c not in noise}
    return sorted(clubs)


def _infer_is_retired(rank_item: Dict[str, Any], details: Dict[str, Any]) -> bool:
    """
    这里返回“近似退役/非英超现役”：
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


def main() -> None:
    session = _make_session()
    Path("data").mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    seen: Set[int] = set()

    page = 0
    stop = False

    while not stop:
        items = _ranked_appearances_page(session, page=page, page_size=PAGE_SIZE)
        if not items:
            break

        for it in items:
            owner = it.get("owner") or {}

            player_id = None
            if isinstance(owner, dict):
                player_id = _as_int(owner.get("id") or owner.get("playerId"))

            apps = _as_int(it.get("value") or it.get("statValue") or it.get("total") or it.get("appearances"))
            if apps is None:
                continue

            if apps < MIN_APPS:
                stop = True
                break

            if player_id is None or player_id in seen:
                continue
            seen.add(player_id)

            player_name = _extract_name(owner)

            details = _player_details(session, player_id)
            clubs = _collect_clubs_from_player_stats(session, player_id)

            if not clubs:
                ct = details.get("currentTeam")
                if isinstance(ct, dict):
                    nm = ct.get("shortName") or ct.get("name")
                    if nm:
                        clubs = [str(nm).strip()]

            is_retired = _infer_is_retired(it, details)

            rows.append(
                {
                    "player_id": player_id,
                    "player name": player_name,
                    "clubs": ", ".join(clubs),
                    "total_appearances": apps,
                    "is_retired": bool(is_retired),
                }
            )

            time.sleep(0.15)

        page += 1

    df = pd.DataFrame(
        rows,
        columns=["player_id", "player name", "clubs", "total_appearances", "is_retired"],
    )
    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"Saved: {OUT_PATH} (rows={len(df)})")


if __name__ == "__main__":
    main()