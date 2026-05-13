#!/usr/bin/env python3
"""
生成英超球员数据更新报告并通过 Telegram 发送。

用法：
  python generate_report.py [--dry-run]

环境变量：
  TELEGRAM_BOT_TOKEN  — Bot Token（从 @BotFather 获取）
  TELEGRAM_CHAT_ID    — 目标 Chat ID
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

# ─── 路径 ─────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
PLAYERS_JSON = REPO_ROOT / "frontend" / "public" / "data" / "players.json"
GIT_PATH = "frontend/public/data/players.json"   # 相对 repo 根目录



# ─── 工具函数 ─────────────────────────────────────────────────────────────────

def _git_old_players() -> list[dict] | None:
    """从 git HEAD 读取旧版 players.json；若不存在则返回 None。"""
    result = subprocess.run(
        ["git", "show", f"HEAD:{GIT_PATH}"],
        capture_output=True, text=True, encoding="utf-8",
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _load_new_players() -> list[dict]:
    with open(PLAYERS_JSON, encoding="utf-8") as f:
        return json.load(f)


def _index_by_id(players: list[dict]) -> dict[int, dict]:
    return {p["id"]: p for p in players}


def _ach_types(player: dict) -> set[str]:
    return {a["type"] for a in player.get("achievements", [])}


def _fmt_name(p: dict) -> str:
    cn = p.get("name_cn", "")
    en = p.get("name_en", "")
    if cn and cn != en:
        return f"{cn}（{en}）"
    return en


def _status_zh(status: str) -> str:
    return {
        "active_pl": "英超现役",
        "active_not_pl": "其他联赛",
        "retired": "退役",
        "hall_of_fame": "名人堂",
    }.get(status, status)


def _near_miss_lines(players: list[dict]) -> list[str]:
    """接近达标的英超现役球员，逻辑与前端 nearMissPlayers 完全一致：
    - 无任何 achievement（有任何达标记录则排除）
    - player_status == 'active_pl'
    - 阈值：总出场 [230,250)、单队 [180,200)、进球 (80,100)、零封 (80,100)
    """
    lines: list[str] = []

    for p in players:
        if p.get("achievements"):
            continue
        if p.get("player_status") != "active_pl":
            continue

        apps    = p.get("total_appearances") or 0
        sc_apps = p.get("single_club_appearances") or 0
        sc_name = p.get("single_club_name") or ""
        goals   = p.get("goals") or 0
        cs      = p.get("clean_sheets") or 0

        items: list[str] = []

        if 230 <= apps < 250:
            items.append(f"总出场 {int(apps)} 场（距250场还差 {250 - int(apps)} 场）")

        if sc_apps and 180 <= sc_apps < 200:
            items.append(f"单队（{sc_name}）{int(sc_apps)} 场（差 {200 - int(sc_apps)} 场）")

        if goals and 80 < goals < 100:
            items.append(f"进球 {int(goals)} 个（差 {100 - int(goals)} 个）")

        if cs and 80 < cs < 100:
            items.append(f"零封 {int(cs)} 次（差 {100 - int(cs)} 次）")

        if items:
            lines.append(f"  • {_fmt_name(p)}：{' / '.join(items)}")

    return lines


# ─── 差异分析 ─────────────────────────────────────────────────────────────────

def build_report(old: list[dict] | None, new: list[dict]) -> str:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    old_idx = _index_by_id(old) if old else {}
    new_idx = _index_by_id(new)

    # ── 1. 新加入总表的球员 ────────────────────────────────────────────────────
    new_player_ids = set(new_idx) - set(old_idx)
    new_players = [new_idx[pid] for pid in sorted(new_player_ids)]

    # ── 2. 出场次数变动 ────────────────────────────────────────────────────────
    app_changes: list[tuple[dict, int, int]] = []   # (player, old_apps, new_apps)
    for pid, np in new_idx.items():
        if pid not in old_idx:
            continue
        op = old_idx[pid]
        old_apps = int(op.get("total_appearances") or 0)
        new_apps = int(np.get("total_appearances") or 0)
        if new_apps != old_apps:
            app_changes.append((np, old_apps, new_apps))
    app_changes.sort(key=lambda x: x[2], reverse=True)

    # ── 3. 状态变化 ────────────────────────────────────────────────────────────
    status_changes: list[tuple[dict, str, str]] = []
    for pid, np in new_idx.items():
        if pid not in old_idx:
            continue
        op = old_idx[pid]
        if op.get("player_status") != np.get("player_status"):
            status_changes.append((np, op["player_status"], np["player_status"]))

    # ── 4. 新达标里程碑 ────────────────────────────────────────────────────────
    new_achievements: list[tuple[dict, list[str]]] = []
    for pid, np in new_idx.items():
        old_ach = _ach_types(old_idx[pid]) if pid in old_idx else set()
        new_ach = _ach_types(np)
        gained = new_ach - old_ach
        if gained:
            new_achievements.append((np, sorted(gained)))

    # ── 5. 接近达标球员（当前快照中）────────────────────────────────────────────
    near_lines = _near_miss_lines(new)

    # ─── 组装报告 ─────────────────────────────────────────────────────────────
    sections: list[str] = []
    total = len(new)
    old_total = len(old) if old else "N/A"

    sections.append(
        f"🏴󠁧󠁢󠁥󠁮󠁧󠁿 *英超名人堂数据更新报告*\n"
        f"📅 {now}\n"
        f"📊 总表球员数：{old_total} → {total}"
    )

    # 新加入总表
    if new_players:
        lines = [f"  • {_fmt_name(p)}（{_status_zh(p.get('player_status',''))}，出场 {int(p.get('total_appearances') or 0)} 场）"
                 for p in new_players]
        sections.append("🆕 *新加入总表的球员*（共 {} 人）\n{}".format(len(new_players), "\n".join(lines)))
    else:
        sections.append("🆕 *新加入总表的球员*：无")

    # 出场次数变动
    if app_changes:
        lines = [
            f"  • {_fmt_name(p)}：{old_a} → {new_a} 场（+{new_a - old_a}）"
            for p, old_a, new_a in app_changes[:20]   # 最多显示 20 条
        ]
        extra = len(app_changes) - 20
        note = f"\n  （另有 {extra} 名球员出场数也有变动）" if extra > 0 else ""
        sections.append(
            "📈 *出场次数变动的球员*（共 {} 人）\n{}{}".format(
                len(app_changes), "\n".join(lines), note
            )
        )
    else:
        sections.append("📈 *出场次数变动的球员*：无")

    # 状态变化
    if status_changes:
        lines = [
            f"  • {_fmt_name(p)}：{_status_zh(old_s)} → {_status_zh(new_s)}"
            for p, old_s, new_s in status_changes
        ]
        sections.append("🔄 *球员状态变化*（共 {} 人）\n{}".format(len(status_changes), "\n".join(lines)))

    # 新达标里程碑
    if new_achievements:
        lines = []
        for p, achs in new_achievements:
            lines.append(f"  • {_fmt_name(p)}：{'、'.join(achs)}")
        sections.append("🏆 *新达标里程碑*（共 {} 人）\n{}".format(len(new_achievements), "\n".join(lines)))
    else:
        sections.append("🏆 *新达标里程碑*：无")

    # 接近达标
    if near_lines:
        sections.append("⚡ *接近达标里程碑的球员*（共 {} 人）\n{}".format(len(near_lines), "\n".join(near_lines)))
    else:
        sections.append("⚡ *接近达标里程碑的球员*：无")

    return "\n\n".join(sections)


# ─── Telegram 发送 ────────────────────────────────────────────────────────────

def send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("⚠️  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 未设置，跳过发送")
        return

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Telegram 单条消息最多 4096 字符，超长时分段发送
    chunks = _split_message(text, max_len=4000)
    for chunk in chunks:
        resp = requests.post(
            api_url,
            json={"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"},
            timeout=15,
        )
        if not resp.ok:
            print(f"Telegram 发送失败: {resp.status_code} {resp.text}", file=sys.stderr)
            resp.raise_for_status()
        else:
            print("Telegram 消息已发送")


def _split_message(text: str, max_len: int = 4000) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


# ─── 入口 ─────────────────────────────────────────────────────────────────────

def main() -> None:
    dry_run = "--dry-run" in sys.argv

    print("读取旧版 players.json（git HEAD）…")
    old_players = _git_old_players()
    if old_players is None:
        print("未找到旧版本，将以首次运行模式生成报告")

    print("读取新版 players.json…")
    new_players = _load_new_players()

    print("生成报告…")
    report = build_report(old_players, new_players)

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60 + "\n")

    if dry_run:
        print("（dry-run 模式，不发送 Telegram）")
    else:
        send_telegram(report)


if __name__ == "__main__":
    main()
