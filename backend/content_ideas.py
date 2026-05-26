#!/usr/bin/env python3
"""
自媒体内容创意生成器：基于最新新闻和球员数据，通过 GPT-4o 输出选题建议。

用法：
  python content_ideas.py [--dry-run] [--top N]

环境变量：
  OPENAI_API_KEY
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from openai import OpenAI

REPO_ROOT    = Path(__file__).resolve().parent.parent
NEWS_JSON    = REPO_ROOT / "frontend" / "public" / "data" / "news.json"
PLAYERS_JSON = REPO_ROOT / "frontend" / "public" / "data" / "players.json"


# ── 数据加载 ──────────────────────────────────────────────────────────────────

def _load_news(top: int) -> list[dict]:
    try:
        data = json.loads(NEWS_JSON.read_text(encoding="utf-8"))
        return data.get("items", [])[:top]
    except Exception:
        return []


def _load_player_context() -> str:
    """提取球员库里最有内容价值的部分：接近里程碑、新成就。"""
    try:
        players: list[dict] = json.loads(PLAYERS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return "（球员数据暂不可用）"

    lines: list[str] = []

    # 接近里程碑的现役英超球员
    near = []
    for p in players:
        if p.get("achievements") or p.get("player_status") != "active_pl":
            continue
        apps  = int(p.get("total_appearances") or 0)
        sc    = int(p.get("single_club_appearances") or 0)
        goals = int(p.get("goals") or 0)
        cs    = int(p.get("clean_sheets") or 0)
        sc_name = p.get("single_club_name") or ""
        name  = p.get("name_cn") or p.get("name_en") or ""
        items = []
        if 230 <= apps < 250:
            items.append(f"总出场{apps}场（距250差{250-apps}场）")
        if sc and 180 <= sc < 200:
            items.append(f"{sc_name}单队{sc}场（差{200-sc}场）")
        if goals and 80 < goals < 100:
            items.append(f"进球{goals}个（差{100-goals}个）")
        if cs and 80 < cs < 100:
            items.append(f"零封{cs}次（差{100-cs}次）")
        if items:
            near.append(f"{name}：{'、'.join(items)}")

    if near:
        lines.append("【接近里程碑的现役英超球员】")
        lines.extend(f"  · {x}" for x in near[:8])

    # 最近获得新成就的球员（achievements 列表非空且 player_status 为 active_pl）
    achievers = [
        p for p in players
        if p.get("achievements") and p.get("player_status") == "active_pl"
    ]
    if achievers:
        lines.append("\n【现役英超球员中已达标的成就】")
        for p in achievers[:6]:
            name = p.get("name_cn") or p.get("name_en") or ""
            achs = [a.get("type", "") if isinstance(a, dict) else a
                    for a in p.get("achievements", [])]
            lines.append(f"  · {name}：{'、'.join(achs)}")

    return "\n".join(lines) if lines else "（暂无特别接近里程碑的球员）"


# ── GPT 调用 ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是一位专注英超足球内容的中文自媒体策划，擅长为抖音、快手、B站、视频号制作爆款内容。
你的受众是中国球迷，喜欢数据驱动的深度内容、情绪化的球星故事、有争议性的话题。
请用中文输出，标题要有冲击力，大纲要具体可执行。"""

USER_PROMPT_TEMPLATE = """以下是今日最新英超相关新闻（按热度排序）：

{news_block}

---
以下是我维护的英超球员数据库中的关键信息：

{player_context}

---
请基于以上信息，为我的自媒体账号（抖音/快手/B站/视频号）生成 **5个** 内容选题建议。

每个选题请按以下格式输出：

【选题 N】
🎯 标题：（吸引眼球的中文标题，15字以内）
📱 最适合平台：（抖音 / 快手 / B站 / 视频号，可多选，并说明原因）
📋 内容大纲：
  1. 开篇钩子（前3秒留住观众）
  2. 核心内容（2-3个要点）
  3. 结尾引导（互动/关注）
💡 关键素材：（需要用到的数据或新闻来源）
⭐ 爆款潜力：（高/中/低，一句话说明理由）

选题类型要多样化，兼顾：数据盘点、新闻解读、球星故事、争议话题。"""


def generate_ideas(news_items: list[dict], player_context: str, top: int) -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 未设置")

    client = OpenAI(api_key=api_key)

    # 格式化新闻块
    news_lines = []
    for i, item in enumerate(news_items, 1):
        kw = " ".join(f"#{k}" for k in item.get("keywords", [])[:3])
        news_lines.append(
            f"{i}. [{item.get('source','')}] {item.get('title','')}\n"
            f"   摘要：{item.get('summary','')[:120]}…\n"
            f"   标签：{kw}"
        )
    news_block = "\n\n".join(news_lines) if news_lines else "（暂无新闻数据）"

    user_prompt = USER_PROMPT_TEMPLATE.format(
        news_block=news_block,
        player_context=player_context,
    )

    print("正在调用 GPT-4o…")
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.85,
        max_tokens=2000,
    )
    return resp.choices[0].message.content or ""


# ── Telegram 发送 ─────────────────────────────────────────────────────────────

def _send_telegram(text: str) -> None:
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("⚠️  TELEGRAM 未配置，跳过发送")
        return

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    max_len = 4000
    while text:
        chunk = text[:max_len]
        if len(text) > max_len:
            split = chunk.rfind("\n")
            if split > 0:
                chunk = text[:split]
        requests.post(
            api_url,
            json={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
            timeout=15,
        )
        text = text[len(chunk):].lstrip("\n")


# ── 入口 ─────────────────────────────────────────────────────────────────────

def main() -> None:
    dry_run = "--dry-run" in sys.argv
    top = 15
    for arg in sys.argv:
        if arg.startswith("--top="):
            top = int(arg.split("=")[1])

    print("加载新闻数据…")
    news_items = _load_news(top)
    print(f"已加载 {len(news_items)} 条新闻")

    print("加载球员数据…")
    player_context = _load_player_context()

    ideas = generate_ideas(news_items, player_context, top)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = f"💡 自媒体选题建议 — {now}\n基于最新 {len(news_items)} 条新闻 + 球员数据库\n\n"
    full_text = header + ideas

    print("\n" + "=" * 60)
    print(full_text)
    print("=" * 60 + "\n")

    if dry_run:
        print("（dry-run，不发送 Telegram）")
    else:
        _send_telegram(full_text)
        print("已发送 Telegram")


if __name__ == "__main__":
    main()
