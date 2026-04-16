"""
fetch_active_status.py
======================
爬取球员"是否活跃于英超"（is_retired）并更新 epl_players_appearances_230plus.csv。

说明：
  - is_retired = False  → 球员目前活跃于英超
  - is_retired = True   → 球员已离开英超（退役或转去其他联赛）

  数据来源：Pulselive player profile API
    - details.active / details.isActive 存在时直接使用
    - 否则用 currentTeam 是否存在来推断

使用方式：
  # 全量重新爬取所有球员
  python fetch_active_status.py

  # 只更新目前标记为"活跃"的球员（更快，退役球员状态不变）
  python fetch_active_status.py --active-only

输出：
  更新 data/epl_players_appearances_230plus.csv 的 is_retired 列
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import requests


CSV_PATH = Path("data") / "epl_players_appearances_230plus.csv"
PL_BASE  = "https://footballapi.pulselive.com"


def _make_session() -> requests.Session:
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


def _get_player_profile(player_id: int, session: requests.Session) -> Dict[str, Any]:
    """Fetch player profile from Pulselive API. Returns {} on 404/error."""
    try:
        resp = session.get(
            f"{PL_BASE}/football/players/{player_id}",
            params={"altIds": "true"}, timeout=20
        )
        if resp.status_code == 404:
            return {}
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [error] player_id={player_id}: {e}")
        return {}


def _infer_is_retired(profile: Dict[str, Any]) -> bool:
    """
    判断球员是否不再活跃于英超：
      1. profile.active / profile.isActive 存在时直接用
      2. 否则看 currentTeam 是否存在（有当前球队 = 活跃）
    返回 True = 已退役/非英超现役，False = 英超现役
    """
    if not profile:
        return True  # 404 / 请求失败，视为退役

    for key in ("active", "isActive"):
        val = profile.get(key)
        if val is not None:
            return not bool(val)

    return not bool(profile.get("currentTeam"))


def main() -> None:
    parser = argparse.ArgumentParser(description="更新球员是否活跃于英超")
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="只重新爬取当前标记为 is_retired=False 的球员，已退役球员保持不变",
    )
    args = parser.parse_args()

    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} 不存在。请先运行 player_premier_250.py。")
        return

    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    print(f"加载 {len(df)} 名球员从 {CSV_PATH}")

    if args.active_only:
        # 只处理当前标记为活跃（is_retired == False）的球员
        mask = df["is_retired"].astype(str).str.lower().isin({"false", "0", "no"})
        to_process = df[mask].copy()
        print(f"--active-only 模式：只处理 {len(to_process)} 名活跃球员")
    else:
        to_process = df.copy()
        print(f"全量模式：处理全部 {len(to_process)} 名球员")

    session = _make_session()
    updated = 0

    for i, (idx, row) in enumerate(to_process.iterrows(), 1):
        player_id_raw = row.get("player_id")
        player_name   = str(row.get("player name", "Unknown"))

        try:
            player_id = int(float(str(player_id_raw)))
        except (ValueError, TypeError):
            print(f"  [{i}] 跳过无效 player_id: {player_id_raw}")
            continue

        profile    = _get_player_profile(player_id, session)
        is_retired = _infer_is_retired(profile)
        old_val    = str(df.at[idx, "is_retired"]).lower()
        new_val    = str(is_retired)

        status_str = "退役/非英超" if is_retired else "英超现役"
        changed    = (old_val != new_val.lower())
        marker     = " ← 变更" if changed else ""
        print(f"  [{i}/{len(to_process)}] {player_name} (id={player_id}): {status_str}{marker}")

        df.at[idx, "is_retired"] = is_retired
        if changed:
            updated += 1

        time.sleep(0.2)

        # 每50名保存一次检查点
        if i % 50 == 0:
            df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
            print(f"  (checkpoint {i}/{len(to_process)}, {updated} 条状态变更)")

    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"\n完成。{updated} 条状态变更 → {CSV_PATH}")
    print("重新运行 merge_player_data.py 以更新 players.json。")


if __name__ == "__main__":
    main()
