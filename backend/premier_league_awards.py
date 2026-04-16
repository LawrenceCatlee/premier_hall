from __future__ import annotations

import json
import re
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Import player name normalization functions
from player_name_normalizer import (
    normalize_player_name,
    apply_nickname,
    first_last_only,
    last_token,
    clean_player_name,
    clean_text,
    similarity_score
)
# Import player name mapping
from player_name_mapper import standardize_player_name
# Import pulselive data functions
from pulselive_data import get_pulselive_player_index


"""
Premier League awards + milestones scraper (Wikipedia -> tables),
then map each player to Pulselive player_id using an index built from:

  https://footballapi.pulselive.com/football/stats/ranked/players/appearances?comps=1...

Why name mismatches happen:
- Wikipedia often uses diacritics (e.g. Solskjær) while Pulselive uses ASCII (Solskjaer)
- Nicknames (Matt vs Matthew, Andy vs Andrew, etc.)
- Dutch "ij" vs "y" variants (Nistelrooij vs Nistelrooy)

This version improves normalisation (incl. æ/ø/ß etc) and, after the run,
auto-generates a name-alias dictionary (based on pulselive_player_index_appearances.csv)
to fill remaining missing player_id.
"""


DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (compatible; pl-scraper/1.3; +https://example.com)"}

# Pulselive (Premier League site backend used by premierleague.com)
PL_BASE = "https://footballapi.pulselive.com"

# Cache: an index built from the all-time Premier League appearances ranking endpoint
PLAYER_INDEX_CACHE = DATA_DIR / "pulselive_player_index_appearances.csv"
PLAYER_INDEX_PAGE_SIZE = 200
PLAYER_INDEX_SLEEP = 0.08

# Reports / outputs
UNMATCHED_REPORT = DATA_DIR / "pulselive_player_id_unmatched_report.csv"
AUTO_ALIAS_JSON = DATA_DIR / "pulselive_player_id_auto_aliases.json"
AUTO_ALIAS_CSV = DATA_DIR / "pulselive_player_id_auto_aliases.csv"
STILL_MISSING_CSV = DATA_DIR / "pulselive_player_id_still_missing.csv"


# ---------- common helpers ----------

def fetch_html(url: str) -> str:
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r.text


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [
            " ".join([str(x) for x in col if str(x) != "nan"]).strip()
            for col in df.columns.to_flat_index()
        ]
    return df


def pick_table_by_required_cols(tables: List[pd.DataFrame], required_cols: List[str]) -> pd.DataFrame:
    req = set(required_cols)
    for t in tables:
        t2 = flatten_columns(t)
        cols = set([clean_text(c) for c in t2.columns])
        if req.issubset(cols):
            t2.columns = [clean_text(c) for c in t2.columns]
            return t2
    raise RuntimeError(f"Cannot find table with required columns: {required_cols}")


# ---------- pulselive: build appearances index (player_id + display name) ----------

def _make_pl_session() -> requests.Session:
    s = requests.Session()
    # These headers usually prevent 403 (Pulselive is used by premierleague.com frontend)
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


def _pl_get_json(
    session: requests.Session,
    path: str,
    params: Optional[dict] = None,
    retries: int = 6,
    timeout: int = 25,
) -> Dict[str, Any]:
    url = f"{PL_BASE}{path}"
    last_err: Optional[Exception] = None

    for i in range(retries):
        try:
            resp = session.get(url, params=params, timeout=timeout)
            if resp.status_code == 429:
                time.sleep(1.2 * (i + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_err = e
            time.sleep(0.8 * (i + 1))

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


def _extract_owner_name(owner: Any) -> str:
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


def _extract_owner_id(owner: Any) -> Optional[int]:
    if isinstance(owner, dict):
        return _as_int(owner.get("id") or owner.get("playerId"))
    return None


def _build_player_index_from_appearances(session: requests.Session) -> pd.DataFrame:
    """
    Build an index of (player_id, player_name, appearances) by paging:
      /football/stats/ranked/players/appearances?comps=1&page=...&pageSize=...

    NOTE: This is exactly what pulselive_player_index_appearances.csv represents:
    an "all-time PL appearances ranking" list, not an exhaustive roster per season.
    """
    rows: List[Dict[str, Any]] = []
    page = 0

    while True:
        params = {
            "page": page,
            "pageSize": PLAYER_INDEX_PAGE_SIZE,
            "comps": "1",  # Premier League competition id
            "compCodeForActivePlayer": "EN_PR",
            "altIds": "true",
        }
        js = _pl_get_json(session, "/football/stats/ranked/players/appearances", params=params)

        content = None
        if isinstance(js.get("stats"), dict):
            content = js["stats"].get("content")
        if content is None:
            content = js.get("content")
        if not isinstance(content, list) or not content:
            break

        for it in content:
            owner = it.get("owner") or {}
            pid = _extract_owner_id(owner)
            name = _extract_owner_name(owner)
            apps = _as_int(it.get("value") or it.get("statValue") or it.get("total") or it.get("appearances"))
            if pid is None or not name or name == "Unknown":
                continue
            rows.append({"player_id": pid, "player_name": name, "appearances": apps})

        page += 1
        time.sleep(PLAYER_INDEX_SLEEP)

    df = pd.DataFrame(rows).drop_duplicates(subset=["player_id"])
    df["appearances"] = pd.to_numeric(df["appearances"], errors="coerce")
    df.to_csv(PLAYER_INDEX_CACHE, index=False, encoding="utf-8-sig")
    return df


def _load_or_build_player_index(session: requests.Session) -> pd.DataFrame:
    if PLAYER_INDEX_CACHE.exists():
        df = pd.read_csv(PLAYER_INDEX_CACHE)
        if {"player_id", "player_name", "appearances"}.issubset(df.columns):
            return df
    return _build_player_index_from_appearances(session)


# ---------- pulselive: build appearances index (player_id + display name) ----------

@dataclass(frozen=True)
class PlayerIndexItem:
    player_id: int
    player_name: str
    appearances: int
    norm: str
    norm_ns: str
    last: str

class PlayerIdResolver:
    """
    Resolver strategy:
    1) exact match on normalised name
    2) exact match on deterministic variants:
       - nickname expansion (Matt -> Matthew, Andy -> Andrew, ...)
       - first+last only (drop middle tokens)
       - no-space normalised
    3) fuzzy fallback restricted by last-name token (to reduce false positives)
    """

    def __init__(self) -> None:
        # Use the new pulselive data module
        df = get_pulselive_player_index()

        items: List[PlayerIndexItem] = []
        for _, r in df.iterrows():
            pid = _as_int(r.get("player_id"))
            nm = str(r.get("player_name") or "").strip()
            apps = _as_int(r.get("appearances"))
            if pid is None or not nm:
                continue
            n = normalize_player_name(nm)
            items.append(
                PlayerIndexItem(
                    player_id=int(pid),
                    player_name=nm,
                    appearances=apps,
                    norm=n,
                    norm_ns=n.replace(" ", ""),
                    last=last_token(n),
                )
            )

        self.items = items

        self.by_norm: Dict[str, List[PlayerIndexItem]] = defaultdict(list)
        self.by_norm_ns: Dict[str, List[PlayerIndexItem]] = defaultdict(list)
        self.by_last: Dict[str, List[PlayerIndexItem]] = defaultdict(list)

        for it in items:
            self.by_norm[it.norm].append(it)
            self.by_norm_ns[it.norm_ns].append(it)
            if it.last:
                self.by_last[it.last].append(it)

        # unresolved report
        self.unmatched: Dict[str, Dict[str, Any]] = {}

    def _choose_best(self, cands: List[PlayerIndexItem], target_norm_ns: str) -> Optional[int]:
        if not cands:
            return None
        scored = []
        for c in cands:
            sim = similarity_score(target_norm_ns, c.norm_ns)
            apps = c.appearances if c.appearances is not None else -1
            scored.append((sim, apps, c))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return scored[0][2].player_id

    def resolve(self, name: str) -> Optional[int]:
        # First apply name mapping to standardize known variations
        standardized_name = standardize_player_name(name)
        
        # Clean the name
        from player_name_normalizer import clean_player_name
        standardized_name = clean_player_name(standardized_name)
        if not standardized_name:
            return None

        base_norm = normalize_player_name(standardized_name)
        base_norm_ns = base_norm.replace(" ", "")

        variants_norm: List[str] = []
        variants_norm.append(base_norm)
        variants_norm.append(apply_nickname(base_norm))
        variants_norm.append(first_last_only(base_norm))
        variants_norm.append(first_last_only(apply_nickname(base_norm)))

        # unique preserve order
        variants_norm = list(dict.fromkeys([v.strip() for v in variants_norm if v.strip()]))

        # exact hits
        for v in variants_norm:
            c = self.by_norm.get(v)
            if c:
                return self._choose_best(c, v.replace(" ", ""))
            c2 = self.by_norm_ns.get(v.replace(" ", ""))
            if c2:
                return self._choose_best(c2, v.replace(" ", ""))

        # fuzzy fallback (restricted by last name)
        last = last_token(base_norm)
        pool = self.by_last.get(last, [])
        relaxed = False
        if not pool:
            relaxed = True
            pool = self.items

        best: Tuple[float, int, PlayerIndexItem] | None = None
        for c in pool:
            sim = similarity_score(base_norm_ns, c.norm_ns)
            apps = c.appearances if c.appearances is not None else -1
            if best is None or (sim, apps) > (best[0], best[1]):
                best = (sim, apps, c)

        if best is None:
            return None

        sim, apps, cand = best

        # acceptance thresholds
        threshold = 0.92 if not relaxed else 0.97
        if sim >= threshold:
            return cand.player_id

        self._add_unmatched(name, base_norm, base_norm_ns, pool)
        return None

    def best_candidate(self, name: str) -> Optional[Tuple[PlayerIndexItem, float]]:
        """
        Return best candidate even if below threshold (for auto-alias generation).
        """
        name = clean_player_name(name)
        if not name:
            return None
        base_norm = normalize_player_name(name)
        base_norm_ns = base_norm.replace(" ", "")
        last = last_token(base_norm)
        pool = self.by_last.get(last, []) or self.items

        best: Tuple[float, int, PlayerIndexItem] | None = None
        for c in pool:
            sim = similarity_score(base_norm_ns, c.norm_ns)
            apps = c.appearances if c.appearances is not None else -1
            if best is None or (sim, apps) > (best[0], best[1]):
                best = (sim, apps, c)
        if best is None:
            return None
        return best[2], float(best[0])

    def _add_unmatched(self, raw: str, norm: str, norm_ns: str, pool: List[PlayerIndexItem]) -> None:
        scored = []
        for c in pool:
            sim = similarity_score(norm_ns, c.norm_ns)
            apps = c.appearances if c.appearances is not None else -1
            scored.append((sim, apps, c))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        top = scored[:5]
        self.unmatched[raw] = {
            "raw_name": raw,
            "norm": norm,
            "suggest_1": top[0][2].player_name if len(top) > 0 else "",
            "suggest_1_id": top[0][2].player_id if len(top) > 0 else "",
            "suggest_1_score": round(top[0][0], 4) if len(top) > 0 else "",
            "suggest_2": top[1][2].player_name if len(top) > 1 else "",
            "suggest_2_id": top[1][2].player_id if len(top) > 1 else "",
            "suggest_2_score": round(top[1][0], 4) if len(top) > 1 else "",
            "suggest_3": top[2][2].player_name if len(top) > 2 else "",
            "suggest_3_id": top[2][2].player_id if len(top) > 2 else "",
            "suggest_3_score": round(top[2][0], 4) if len(top) > 2 else "",
        }

    def dump_unmatched_report(self, path: Path = UNMATCHED_REPORT) -> None:
        if not self.unmatched:
            return
        df = pd.DataFrame(list(self.unmatched.values()))
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"[INFO] Unmatched report saved -> {path} (rows={len(df)})")

def scrape_golden_boot(
    resolver: PlayerIdResolver,
    out_csv: Path = DATA_DIR / "pl_golden_boot_winners.csv",
) -> Path:
    url = "https://en.wikipedia.org/wiki/Premier_League_Golden_Boot"
    html = fetch_html(url)
    tables = pd.read_html(html)
    t = pick_table_by_required_cols(tables, ["Season", "Player", "Club", "Goals"])
    t = t[["Season", "Player", "Club", "Goals"]].copy()

    t["Season"] = t["Season"].ffill().map(clean_text)
    t["Player"] = t["Player"].map(clean_player_name)
    t["Club"] = t["Club"].map(clean_text)
    t["Goals"] = pd.to_numeric(t["Goals"], errors="coerce")

    t.insert(0, "player_id", t["Player"].apply(resolver.resolve))

    t.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"Saved -> {out_csv}")
    return out_csv


def scrape_golden_glove(
    resolver: PlayerIdResolver,
    out_csv: Path = DATA_DIR / "pl_golden_glove_winners.csv",
) -> Path:
    url = "https://en.wikipedia.org/wiki/Premier_League_Golden_Glove"
    html = fetch_html(url)
    tables = pd.read_html(html)
    t = pick_table_by_required_cols(tables, ["Season", "Player", "Club", "Clean sheets"])
    t = t[["Season", "Player", "Club", "Clean sheets"]].copy()

    t["Season"] = t["Season"].ffill().map(clean_text)
    t["Player"] = t["Player"].map(clean_player_name)
    t["Club"] = t["Club"].map(clean_text)
    t["Clean sheets"] = pd.to_numeric(t["Clean sheets"], errors="coerce")

    t.insert(0, "player_id", t["Player"].apply(resolver.resolve))

    t.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"Saved -> {out_csv}")
    return out_csv


def scrape_player_of_the_season(
    resolver: PlayerIdResolver,
    out_csv: Path = DATA_DIR / "pl_player_of_season_winners.csv",
) -> Path:
    url = "https://en.wikipedia.org/wiki/Premier_League_Player_of_the_Season"
    html = fetch_html(url)
    tables = pd.read_html(html)
    t = pick_table_by_required_cols(tables, ["Season", "Player", "Club"])
    keep = [c for c in ["Season", "Player", "Club", "Position", "Nationality"] if c in t.columns]
    t = t[keep].copy()

    t["Season"] = t["Season"].map(clean_text)
    t["Player"] = t["Player"].map(clean_player_name)
    t["Club"] = t["Club"].map(clean_text)

    t.insert(0, "player_id", t["Player"].apply(resolver.resolve))

    t.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"Saved -> {out_csv}")
    return out_csv


def scrape_3plus_premier_league_titles(
    resolver: PlayerIdResolver,
    out_csv: Path = DATA_DIR / "pl_players_3plus_titles.csv",
) -> Path:
    url = "https://en.wikipedia.org/wiki/List_of_Premier_League_winning_players"
    html = fetch_html(url)
    tables = pd.read_html(html)

    t = pick_table_by_required_cols(tables, ["Player", "No.", "Club(s)", "Season(s)"]).copy()

    t["No."] = pd.to_numeric(t["No."], errors="coerce")
    t = t[t["No."] >= 3].copy()

    t["Player"] = t["Player"].map(clean_player_name)
    for col in ["Nat.", "Pos.", "Club(s)", "Season(s)"]:
        if col in t.columns:
            t[col] = t[col].map(clean_text)

    rename_map = {
        "No.": "titles",
        "Nat.": "nationality",
        "Pos.": "position",
        "Club(s)": "clubs",
        "Season(s)": "seasons",
        "Player": "player",
    }
    t = t.rename(columns={k: v for k, v in rename_map.items() if k in t.columns})

    keep = [c for c in ["player", "titles", "nationality", "position", "clubs", "seasons"] if c in t.columns]
    t = t[keep]

    t.insert(0, "player_id", t["player"].apply(resolver.resolve))

    t.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"Saved -> {out_csv}")
    return out_csv


def scrape_100_goals_club(
    resolver: PlayerIdResolver,
    out_csv: Path = DATA_DIR / "pl_100_goals_club.csv",
) -> Path:
    """
    Data source: Transfermarkt (All-time top goalscorers)
      https://www.transfermarkt.com/premier-league/ewigetorschuetzen/wettbewerb/GB1

    Re-implemented to follow the same parsing style as player_premier_team_200.py:
    - requests + browser-like headers
    - BeautifulSoup find <table class="items">
    - parse each <tr> by scanning <td> cells and extracting player name via <img alt=...>
      (or link fallback)
    - add pagination: /page/2, /page/3, ... and stop once goals <= 80 (table is sorted by goals desc)

    Output columns (English):
      player_id, player name, Premier League appearances, Premier League total goals
    """
    base_url = "https://www.transfermarkt.com/premier-league/ewigetorschuetzen/wettbewerb/GB1"
    min_goals = 81  # strictly > 80

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.7",
        "Connection": "keep-alive",
        "Referer": "https://www.transfermarkt.com/",
    }

    rows: List[Dict[str, Any]] = []
    processed: Set[str] = set()

    page = 1
    while True:
        url = base_url if page == 1 else f"{base_url}/page/{page}"
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.content, "html.parser")

        table = soup.find("table", class_="items")
        if not table:
            table = soup.find("table")
        if not table:
            raise RuntimeError(f"Could not find table on page {page}: {url}")

        tr_list = table.find_all("tr")
        if len(tr_list) <= 1:
            break  # no data rows

        stop_after_page = False
        found_any = False

        # skip header
        for tr in tr_list[1:]:
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue

            # ---- player name (like 200.py: prefer img alt) ----
            player_name = ""
            img = tr.find("img", alt=True)
            if img and img.get("alt"):
                player_name = img.get("alt", "").strip()

            if not player_name:
                # fallback to the first "hauptlink" anchor text
                a = tr.find("a", class_="spielprofil_tooltip")
                if a and a.get_text(strip=True):
                    player_name = a.get_text(strip=True)
                else:
                    # another fallback: any link with title attr
                    a2 = tr.find("a", title=True)
                    if a2 and a2.get("title"):
                        player_name = a2.get("title", "").strip()

            if not player_name:
                continue

            player_name = clean_player_name(player_name)

            # Avoid duplicates across pages
            if player_name in processed:
                continue
            processed.add(player_name)

            # ---- Extract numeric stats robustly ----
            # Transfermarkt compact view typically has numbers like:
            # matches, minutes (with dots), assists, goals (last)
            # Example from page text:
            # 441 38.199 147 260  -> matches=441, goals=260
            nums_in_order: List[int] = []

            for td in tds:
                txt = td.get_text(" ", strip=True)
                if not txt:
                    continue
                # pick integer-like tokens, keep order
                # "38.199" -> "38199"
                token = re.sub(r"[^\d]", "", txt)
                if token.isdigit():
                    nums_in_order.append(int(token))

            # remove rank if it sneaks in as the first number
            # rank is usually a small number, and appears in the first td
            if nums_in_order and nums_in_order[0] <= 500 and len(nums_in_order) >= 4:
                # Heuristic: if first td is rank, it will be very small (1..1000)
                # but matches is also <=1000; so we only drop rank if the first td text is exactly rank-like.
                first_td_txt = tds[0].get_text(strip=True)
                if first_td_txt.isdigit() and int(first_td_txt) == nums_in_order[0]:
                    nums_in_order = nums_in_order[1:]

            if len(nums_in_order) < 2:
                continue

            # goals: last "reasonable" value (<= 500) from left-to-right sequence
            goals = None
            for v in reversed(nums_in_order):
                if 0 <= v <= 500:
                    goals = v
                    break

            # appearances (matches): maximum value <= 1000 (minutes will be >> 1000)
            apps = None
            small = [v for v in nums_in_order if 0 <= v <= 1000]
            if small:
                apps = max(small)

            if goals is None or apps is None:
                continue

            found_any = True

            # stop condition: table sorted by goals desc
            if goals < min_goals:
                stop_after_page = True
                continue

            rows.append(
                {
                    "player_id": resolver.resolve(player_name),
                    "player name": player_name,
                    "Premier League appearances": int(apps),
                    "Premier League total goals": int(goals),
                }
            )

        # if we already reached <=80 on this page, break after processing it
        if stop_after_page:
            break

        if not found_any:
            break

        page += 1
        # polite delay (Transfermarkt is strict sometimes)
        time.sleep(1.2)

    df = pd.DataFrame(rows)
    if df.empty:
        print("No players found with Premier League total goals > 80")
        df.to_csv(out_csv, index=False, encoding="utf-8-sig")
        return out_csv

    df = df.sort_values(
        by=["Premier League total goals", "Premier League appearances", "player name"],
        ascending=[False, False, True],
    )

    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"Saved -> {out_csv} (rows={len(df)})")
    return out_csv


def scrape_100_clean_sheets_gk(
    resolver: PlayerIdResolver,
    out_csv: Path = DATA_DIR / "pl_100_clean_sheets_gk.csv",
) -> Path:
    """
    Data source: Transfermarkt (Premier League all-time clean sheets)
      https://www.transfermarkt.co.uk/premier-league/weisseWeste/wettbewerb/GB1/saison_id/gesamt/plus/1

    Requirement:
    - include ALL goalkeepers with Premier League total clean sheets > 80
    - output columns (English):
        player_id, player name, Premier League appearances, Premier League total clean sheets

    Implementation style follows player_premier_team_200.py:
    - requests + browser-like headers
    - BeautifulSoup find <table class="items">
    - parse rows and extract player name via <img alt=...> (fallback to spielprofil_tooltip)
    - pagination via /page/{n}
    - stop once clean sheets <= 80 (table is sorted desc)
    """
    base_url = "https://www.transfermarkt.co.uk/premier-league/weisseWeste/wettbewerb/GB1/saison_id/gesamt"
    min_cs = 80  # strictly > 80

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.8",
        "Connection": "keep-alive",
        "Referer": "https://www.transfermarkt.co.uk/",
    }

    def _to_int(s: str) -> Optional[int]:
        s = re.sub(r"[^\d]", "", s or "")
        return int(s) if s else None

    rows: List[Dict[str, Any]] = []
    processed = set()

    page = 1
    while True:
        url = base_url if page == 1 else f"{base_url}/page/{page}"
        resp = requests.get(url, headers=headers, timeout=60)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.content, "html.parser")
        table = soup.find("table", class_="items")
        if not table:
            break

        tr_list = table.find_all("tr")
        if len(tr_list) <= 1:
            break

        stop_after_page = False
        found_any = False

        # Build header index map (best-effort; Transfermarkt sometimes uses blank headers)
        header_cells = tr_list[0].find_all(["th", "td"])
        header_texts = [c.get_text(" ", strip=True).lower() for c in header_cells]
        idx_apps = None
        idx_cs = None
        for i, ht in enumerate(header_texts):
            ht = re.sub(r"\s+", " ", ht).strip()
            if idx_apps is None and any(k in ht for k in ["apps", "appearances", "matches", "games", "spiele"]):
                idx_apps = i
            if idx_cs is None and any(k in ht for k in ["clean sheets", "clean sheet", "weisse weste", "weiße weste", "cs"]):
                idx_cs = i
        
        # fu = 0
        for tr in tr_list[1:]:
            tds = tr.find_all("td")
            
            if len(tds) < 4:
                continue

            # ---- player name ----
            player_name = ""
            img = tr.find("img", alt=True)
            if img and img.get("alt"):
                player_name = img.get("alt", "").strip()

            if not player_name:
                a = tr.find("a", class_="spielprofil_tooltip")
                if a and a.get_text(strip=True):
                    player_name = a.get_text(strip=True)

            if not player_name:
                continue

            player_name = clean_player_name(player_name)

            if player_name in processed:
                continue
            processed.add(player_name)

            # ---- appearances / clean sheets ----
            apps = _to_int(tds[-3].get_text(" ", strip=True))
            cs = _to_int(tds[-2].get_text(" ", strip=True))

            if apps is None or cs is None:
                continue

            found_any = True

            # stop condition: table sorted by clean sheets desc
            if cs < min_cs:
                stop_after_page = True
                continue

            rows.append(
                {
                    "player_id": resolver.resolve(player_name),
                    "player name": player_name,
                    "Premier League appearances": int(apps),
                    "Premier League total clean sheets": int(cs),
                }
            )

        if stop_after_page or not found_any:
            break

        page += 1
        time.sleep(1.2)  # be polite (Transfermarkt can be strict)

    df = pd.DataFrame(rows)
    if df.empty:
        print("No goalkeepers found with Premier League total clean sheets > 80")
        df.to_csv(out_csv, index=False, encoding="utf-8-sig")
        return out_csv

    df = df.sort_values(
        by=["Premier League total clean sheets", "Premier League appearances", "player name"],
        ascending=[False, False, True],
    )

    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"Saved -> {out_csv} (rows={len(df)})")
    return out_csv


# ---------- post-process: auto-alias for missing player_id ----------

def _detect_name_col(df: pd.DataFrame) -> Optional[str]:
    for c in ["player", "Player", "player name", "player_name"]:
        if c in df.columns:
            return c
    return None


def _is_missing_pid(x: Any) -> bool:
    if x is None:
        return True
    if isinstance(x, float) and pd.isna(x):
        return True
    s = str(x).strip()
    return s == "" or s.lower() == "nan"


def build_auto_aliases(resolver: PlayerIdResolver, names: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    For each name, pick the single best candidate in pulselive index,
    and accept it only if similarity is high enough (to avoid false matches).
    """
    alias: Dict[str, Dict[str, Any]] = {}
    for raw in sorted(set([clean_player_name(n) for n in names if n])):
        cand = resolver.best_candidate(raw)
        if not cand:
            continue
        it, sim = cand

        # dynamic thresholds based on last-name pool size (common surnames are riskier)
        last = last_token(normalize_player_name(raw))
        pool_size = len(resolver.by_last.get(last, [])) if last else len(resolver.items)

        if not last:
            thr = 0.97
        elif pool_size <= 30:
            thr = 0.90
        elif pool_size <= 100:
            thr = 0.93
        else:
            thr = 0.95

        if sim >= thr:
            alias[raw] = {
                "player_id": it.player_id,
                "pulselive_name": it.player_name,
                "score": round(sim, 4),
                "pool_size": pool_size,
            }
    return alias


def apply_aliases_to_csv(csv_path: Path, alias_map: Dict[str, Dict[str, Any]]) -> int:
    if not csv_path.exists():
        return 0
    df = pd.read_csv(csv_path)
    if "player_id" not in df.columns:
        return 0
    name_col = _detect_name_col(df)
    if not name_col:
        return 0

    changed = 0
    for i, row in df.iterrows():
        if _is_missing_pid(row.get("player_id")):
            raw = clean_player_name(row.get(name_col) or "")
            if raw in alias_map:
                df.at[i, "player_id"] = alias_map[raw]["player_id"]
                changed += 1

    if changed:
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    return changed


def write_alias_outputs(alias_map: Dict[str, Dict[str, Any]]) -> None:
    if not alias_map:
        return
    AUTO_ALIAS_JSON.write_text(json.dumps(alias_map, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(
        [
            {"raw_name": k, **v}
            for k, v in alias_map.items()
        ]
    ).to_csv(AUTO_ALIAS_CSV, index=False, encoding="utf-8-sig")
    print(f"[INFO] Auto-alias written -> {AUTO_ALIAS_JSON} and {AUTO_ALIAS_CSV} (rows={len(alias_map)})")


def collect_missing_from_outputs(output_paths: List[Path]) -> List[str]:
    missing: List[str] = []
    for p in output_paths:
        if not p.exists():
            continue
        df = pd.read_csv(p)
        if "player_id" not in df.columns:
            continue
        name_col = _detect_name_col(df)
        if not name_col:
            continue
        m = df[df["player_id"].apply(_is_missing_pid)]
        if not m.empty:
            missing.extend([clean_player_name(x) for x in m[name_col].tolist()])
    return [x for x in missing if x]


def dump_still_missing(output_paths: List[Path]) -> None:
    rows = []
    for p in output_paths:
        if not p.exists():
            continue
        df = pd.read_csv(p)
        if "player_id" not in df.columns:
            continue
        name_col = _detect_name_col(df)
        if not name_col:
            continue
        m = df[df["player_id"].apply(_is_missing_pid)]
        for _, r in m.iterrows():
            rows.append({"file": p.name, "player": clean_player_name(r.get(name_col) or "")})
    if rows:
        pd.DataFrame(rows).drop_duplicates().to_csv(STILL_MISSING_CSV, index=False, encoding="utf-8-sig")
        print(f"[WARN] Still missing player_id -> {STILL_MISSING_CSV} (rows={len(rows)})")


# ---------- main ----------

def main() -> None:
    resolver = PlayerIdResolver()
    outputs: List[Path] = []

    # team_10y_20y is static — only scrape once if CSV is missing
    team_10y_file = DATA_DIR / "pl_team_10y_20y_award_xi.csv"
    if team_10y_file.exists():
        print(f"[INFO] {team_10y_file} already exists, skipping scrape.")
        outputs.append(team_10y_file)
    else:
        outputs.append(scrape_team_10_and_20_awards(resolver)); time.sleep(1)

    outputs.append(scrape_golden_boot(resolver)); time.sleep(1)
    outputs.append(scrape_golden_glove(resolver)); time.sleep(1)
    outputs.append(scrape_player_of_the_season(resolver)); time.sleep(1)
    outputs.append(scrape_3plus_premier_league_titles(resolver)); time.sleep(1)
    outputs.append(scrape_100_goals_club(resolver)); time.sleep(1)
    try:
        outputs.append(scrape_100_clean_sheets_gk(resolver))
    except Exception as e:
        print(f"[WARN] scrape_100_clean_sheets_gk failed ({e}), using existing file if available")
        existing = DATA_DIR / "pl_100_clean_sheets_gk.csv"
        if existing.exists():
            outputs.append(existing)
            print(f"[INFO] Using cached {existing}")

    # 1) dump unresolved suggestions for manual review (if any)
    resolver.dump_unmatched_report()

    # 2) build & apply auto-aliases for remaining missing player_id
    missing_names = collect_missing_from_outputs(outputs)
    alias_map = build_auto_aliases(resolver, missing_names)
    write_alias_outputs(alias_map)

    total_filled = 0
    for p in outputs:
        total_filled += apply_aliases_to_csv(p, alias_map)

    if total_filled:
        print(f"[INFO] Auto-filled player_id in outputs: {total_filled}")

    # 3) still-missing list (if any) for final manual patch
    dump_still_missing(outputs)


if __name__ == "__main__":
    main()
