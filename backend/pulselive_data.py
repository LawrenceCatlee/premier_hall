"""
Pulselive Data Module

This module provides functions to fetch and cache Premier League player data
from the Pulselive API (used by premierleague.com).

Used by:
- premier_league_awards.py
- player_premier_team_200.py
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests


# Configuration
DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (compatible; pl-scraper/1.3; +https://example.com)"}

# Pulselive (Premier League site backend used by premierleague.com)
PL_BASE = "https://footballapi.pulselive.com"

# Cache: an index built from the all-time Premier League appearances ranking endpoint
PLAYER_INDEX_CACHE = DATA_DIR / "pulselive_player_index_appearances.csv"
PLAYER_DOB_CACHE = DATA_DIR / "pulselive_player_dob.csv"
PLAYER_INDEX_PAGE_SIZE = 200
PLAYER_INDEX_SLEEP = 0.08
PLAYER_PROFILE_SLEEP = 0.15  # polite delay between individual profile requests


def _make_pl_session() -> requests.Session:
    """Create a session for Pulselive API requests"""
    s = requests.Session()
    s.headers.update(UA)
    return s


def _as_int(v) -> Optional[int]:
    """Convert value to int, return None if not possible"""
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _build_player_index_from_appearances(session: requests.Session) -> pd.DataFrame:
    """Build player index from Pulselive appearances API.

    Current response shape (2024+):
      { "stats": { "pageInfo": {...}, "content": [ { "owner": {...}, "value": 657 }, ... ] } }
    Each "owner" contains id, name, nationalTeam, info (position), currentTeam, birth.
    DOB is available directly here, so we skip the separate profile endpoint.
    """
    import datetime as _dt
    print("Building player index from Pulselive appearances API...")

    url = f"{PL_BASE}/football/stats/ranked/players/appearances"
    params = {
        "comps": "1",   # Premier League (all-time)
        "page": 0,
        "pageSize": PLAYER_INDEX_PAGE_SIZE,
        "altIds": "true",
        "type": "player",
    }

    rows = []
    page = 0

    while True:
        params["page"] = page
        try:
            response = session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Handle both old shape (data["content"]) and new shape (data["stats"]["content"])
            content = (
                data.get("stats", {}).get("content")
                or data.get("content")
                or []
            )
            if not content:
                print(f"No more data at page {page}")
                break

            for entry in content:
                owner = entry.get("owner", entry)  # new API wraps in "owner"
                pid = _as_int(owner.get("id"))
                name = owner.get("name", {}).get("display", "")
                if not pid or not name:
                    continue

                nationality = (
                    owner.get("nationalTeam", {}).get("country", "")
                    or owner.get("nationality", {}).get("name", "")
                )
                position = owner.get("info", {}).get("position", "")
                current_club = (
                    owner.get("currentTeam", {}).get("name", "")
                    or owner.get("info", {}).get("club", {}).get("name", "")
                )

                # DOB — available directly in this endpoint
                birth_millis = owner.get("birth", {}).get("date", {}).get("millis")
                birth_date = ""
                if birth_millis:
                    try:
                        birth_date = _dt.datetime.utcfromtimestamp(
                            float(birth_millis) / 1000
                        ).strftime("%Y-%m-%d")
                    except Exception:
                        pass

                rows.append({
                    "player_id":   pid,
                    "player_name": name,
                    "appearances": _as_int(entry.get("value", 0)),
                    "nationality": nationality,
                    "position":    position,
                    "current_club": current_club,
                    "birth_date":  birth_date,
                })

            print(f"Page {page}: {len(content)} players")

            page_info = data.get("stats", {}).get("pageInfo", {})
            num_pages = page_info.get("numPages", 0)
            if num_pages and page >= num_pages - 1:
                break
            if len(content) < PLAYER_INDEX_PAGE_SIZE:
                break

            page += 1
            time.sleep(PLAYER_INDEX_SLEEP)

        except requests.exceptions.RequestException as e:
            print(f"Error fetching page {page}: {e}")
            break

    if not rows:
        print("WARNING: No data fetched — returning empty DataFrame")
        return pd.DataFrame(columns=["player_id", "player_name", "appearances",
                                     "nationality", "position", "current_club", "birth_date"])

    df = pd.DataFrame(rows).drop_duplicates(subset=["player_id"])
    df["appearances"] = pd.to_numeric(df["appearances"], errors="coerce")
    df.to_csv(PLAYER_INDEX_CACHE, index=False, encoding="utf-8-sig")
    print(f"Saved {len(df)} players to {PLAYER_INDEX_CACHE}")

    # 同步写入 DOB 缓存，避免后续重复爬取
    dob_df = df[["player_id", "birth_date"]].copy()
    dob_df.to_csv(PLAYER_DOB_CACHE, index=False, encoding="utf-8-sig")
    print(f"DOB cache also updated: {len(dob_df)} entries")

    return df


def _load_or_build_player_index(session: requests.Session) -> pd.DataFrame:
    """Load existing player index or build new one"""
    if PLAYER_INDEX_CACHE.exists():
        df = pd.read_csv(PLAYER_INDEX_CACHE)
        if {"player_id", "player_name", "appearances"}.issubset(df.columns):
            print(f"Loaded {len(df)} players from cache")
            return df
    return _build_player_index_from_appearances(session)


def get_pulselive_player_index() -> pd.DataFrame:
    """
    Get Premier League player index from Pulselive API.
    Returns DataFrame with player_id, player_name, appearances, etc.
    """
    session = _make_pl_session()
    return _load_or_build_player_index(session)


def search_player_by_name(name: str) -> Optional[pd.DataFrame]:
    """
    Search for players by name in the Pulselive index.
    Returns DataFrame with matching players.
    """
    df = get_pulselive_player_index()
    
    # Simple name matching (case-insensitive)
    name_lower = name.lower().strip()
    matches = df[df["player_name"].str.lower().str.contains(name_lower, na=False)]
    
    return matches if not matches.empty else None


def get_player_by_id(player_id: int) -> Optional[pd.DataFrame]:
    """
    Get player information by player_id.
    Returns DataFrame with player info or None if not found.
    """
    df = get_pulselive_player_index()
    player = df[df["player_id"] == player_id]
    
    return player if not player.empty else None


def fetch_player_dob_batch(player_ids: List[int], force_refresh: bool = False) -> pd.DataFrame:
    """
    Fetch date-of-birth for a list of player_ids via the Pulselive player profile endpoint.
    Results are cached in PLAYER_DOB_CACHE.

    Returns a DataFrame with columns: player_id, birth_date (ISO string, may be empty).
    """
    # Load existing cache
    if PLAYER_DOB_CACHE.exists() and not force_refresh:
        cached = pd.read_csv(PLAYER_DOB_CACHE, dtype={"player_id": int})
        already_fetched = set(cached["player_id"].tolist())
    else:
        cached = pd.DataFrame(columns=["player_id", "birth_date"])
        already_fetched = set()

    missing_ids = [pid for pid in player_ids if pid not in already_fetched]
    if not missing_ids:
        print(f"DOB cache hit for all {len(player_ids)} players")
        return cached

    print(f"Fetching DOB for {len(missing_ids)} players (cache has {len(already_fetched)})...")
    session = _make_pl_session()
    new_rows = []

    for i, player_id in enumerate(missing_ids, 1):
        url = f"{PL_BASE}/football/players/{player_id}"
        try:
            resp = session.get(url, params={"altIds": "true"}, timeout=20)
            if resp.status_code == 404:
                new_rows.append({"player_id": player_id, "birth_date": ""})
            else:
                resp.raise_for_status()
                data = resp.json()
                dob = data.get("birth", {}).get("date", {}).get("millis")
                if dob:
                    import datetime
                    birth_date = datetime.datetime.utcfromtimestamp(dob / 1000).strftime("%Y-%m-%d")
                else:
                    birth_date = ""
                new_rows.append({"player_id": player_id, "birth_date": birth_date})
        except Exception as e:
            print(f"  Error fetching player {player_id}: {e}")
            new_rows.append({"player_id": player_id, "birth_date": ""})

        if i % 50 == 0:
            print(f"  Progress: {i}/{len(missing_ids)}")
        time.sleep(PLAYER_PROFILE_SLEEP)

    new_df = pd.DataFrame(new_rows)
    combined = pd.concat([cached, new_df], ignore_index=True).drop_duplicates(subset=["player_id"])
    combined.to_csv(PLAYER_DOB_CACHE, index=False, encoding="utf-8-sig")
    print(f"DOB cache updated: {len(combined)} players total")
    return combined


def refresh_player_cache() -> pd.DataFrame:
    """
    Force refresh of the player cache by rebuilding from API.
    """
    if PLAYER_INDEX_CACHE.exists():
        PLAYER_INDEX_CACHE.unlink()
        print("Removed existing cache")
    
    session = _make_pl_session()
    return _build_player_index_from_appearances(session)


if __name__ == "__main__":
    # Test the module
    print("=== Pulselive Data Module Test ===")
    
    # Get player index
    df = get_pulselive_player_index()
    print(f"Total players: {len(df)}")
    print(f"Columns: {df.columns.tolist()}")
    
    # Test search
    test_name = "Kane"
    matches = search_player_by_name(test_name)
    if matches is not None:
        print(f"\nFound {len(matches)} players matching '{test_name}':")
        print(matches[["player_id", "player_name", "appearances"]].head().to_string(index=False))
    
    # Test get by ID
    if matches is not None and len(matches) > 0:
        test_id = matches.iloc[0]["player_id"]
        player = get_player_by_id(test_id)
        if player is not None:
            print(f"\nPlayer details for ID {test_id}:")
            print(player.to_string(index=False))
