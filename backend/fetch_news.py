#!/usr/bin/env python3
"""
RSS新闻聚合器：抓取体育相关新闻，按优先级评分后发送到 Telegram。

用法：
  python fetch_news.py [--dry-run] [--hours N]

环境变量：
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import NamedTuple

import feedparser
import requests

REPO_ROOT    = Path(__file__).resolve().parent.parent
PLAYERS_JSON = REPO_ROOT / "frontend" / "public" / "data" / "players.json"
NEWS_JSON    = REPO_ROOT / "frontend" / "public" / "data" / "news.json"
ARCHIVE_JSON = REPO_ROOT / "frontend" / "public" / "data" / "news_archive.json"
SENT_GUIDS   = REPO_ROOT / "backend" / "data" / "news_sent_guids.json"
MAX_GUIDS    = 1000
MAX_ARCHIVE  = 2000  # 最多保留多少条历史新闻

# ── RSS 数据源（name, url, tier） ──────────────────────────────────────────────
# tier 3 = 顶级转会/独家消息源, tier 2 = 主流体育媒体, tier 1 = 综合体育
SOURCES = [
    ("罗马诺",         "https://fabrizioromano.substack.com/feed",                    3),
    ("Transfermarkt",  "https://www.transfermarkt.com/rss/news_world.rss",             3),
    ("Sky Sports",     "https://www.skysports.com/rss/12040",                          2),
    ("BBC Sport",      "http://feeds.bbci.co.uk/sport/football/rss.xml",               2),
    ("The Guardian",   "https://www.theguardian.com/football/rss",                     2),
    ("ESPN FC",        "https://www.espn.com/espn/rss/soccer/news",                    1),
    ("Goal.com",       "https://www.goal.com/feeds/en/news",                           1),
]

# ── 英超球队关键词 ──────────────────────────────────────────────────────────────
PL_TEAMS = [
    "Arsenal", "Aston Villa", "Brentford", "Brighton", "Chelsea",
    "Crystal Palace", "Everton", "Fulham", "Ipswich", "Leicester",
    "Liverpool", "Manchester City", "Manchester United", "Newcastle",
    "Nottingham Forest", "Southampton", "Tottenham", "West Ham", "Wolves", "Bournemouth",
    "Man City", "Man United", "Man Utd", "Spurs", "Forest",
]

PL_KEYWORDS = PL_TEAMS + [
    "Premier League", "EPL", "FA Cup", "Carabao Cup",
]

BREAKING_KEYWORDS = [
    "here we go", "breaking", "exclusive", "confirmed", "done deal",
    "signs", "agrees", "announced", "official", "completed",
]

SPORTS_KEYWORDS = [
    "football", "soccer", "FIFA", "UEFA", "Champions League", "Europa League",
    "Conference League", "Bundesliga", "La Liga", "Serie A", "Ligue 1",
    "World Cup", "Euros", "international", "transfer", "signing", "loan",
    "manager", "coach", "goal", "match", "fixture", "standings",
    "injured", "injury", "contract", "release clause", "fee", "wages",
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "was", "are", "were", "be", "been", "has", "have",
    "had", "will", "would", "could", "should", "may", "might", "as", "by",
    "from", "that", "this", "it", "he", "she", "they", "we", "you", "i",
    "his", "her", "their", "its", "our", "your", "my", "who", "which",
    "after", "before", "over", "into", "out", "up", "how", "what", "when",
    "why", "where", "not", "no", "can", "do", "did", "does", "said", "says",
    "new", "also", "than", "more", "all", "one", "two", "three", "just",
    "about", "so", "if", "then", "there", "here", "now", "get", "got",
}

TIER_EMOJI = {3: "🔴", 2: "🟡", 1: "⚪"}
TIER_LABEL = {3: "顶级消息源", 2: "英超主流媒体", 1: "综合体育"}


class NewsItem(NamedTuple):
    title: str
    url: str
    source: str
    tier: int
    published: datetime
    score: float
    keywords: list[str]
    summary: str


# ── 加载球员姓名 ───────────────────────────────────────────────────────────────

def _load_player_names() -> set[str]:
    try:
        players = json.loads(PLAYERS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return set()
    names: set[str] = set()
    for p in players:
        en = (p.get("name_en") or "").strip()
        if not en:
            continue
        names.add(en.lower())
        # 加姓氏（最后一个单词）
        parts = en.split()
        if parts:
            names.add(parts[-1].lower())
    return names


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _parse_date(entry) -> datetime | None:
    """尝试从 feedparser entry 解析发布时间，返回 UTC datetime。"""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _text_lower(item_title: str, item_summary: str) -> str:
    return (item_title + " " + item_summary).lower()


def _contains_any(text: str, keywords: list[str]) -> bool:
    tl = text.lower()
    return any(kw.lower() in tl for kw in keywords)


def _score(title: str, summary: str, tier: int, player_names: set[str]) -> float:
    text = _text_lower(title, summary)
    score = tier * 10.0  # 基础分

    # 英超相关加分
    for kw in PL_KEYWORDS:
        if kw.lower() in text:
            score += 5
            break

    # 突发/独家关键词加分
    for kw in BREAKING_KEYWORDS:
        if kw in text:
            score += 8
            break

    # 命中数据库球员名加分
    for name in player_names:
        if name in text and len(name) > 4:  # 避免太短的词误匹配
            score += 6
            break

    return score


def _extract_keywords(title: str, summary: str, player_names: set[str]) -> list[str]:
    text = title + " " + summary
    found: list[str] = []

    # 先匹配 PL 球队
    for team in PL_TEAMS:
        if team.lower() in text.lower() and team not in found:
            found.append(team)

    # 匹配球员名
    for name in player_names:
        if len(name) > 4 and name in text.lower():
            # 找回原始大小写版本
            match = re.search(re.escape(name), text, re.IGNORECASE)
            if match:
                canonical = match.group()
                if canonical not in found:
                    found.append(canonical)

    # 从标题提取高频词（去停用词）
    words = re.findall(r"\b[A-Za-z][a-zA-Z]{3,}\b", title)
    for w in words:
        if w.lower() not in STOPWORDS and w not in found:
            found.append(w)

    return found[:6]


def _is_sports_relevant(title: str, summary: str, player_names: set[str]) -> bool:
    """判断新闻是否体育相关（含球星花边例外）。"""
    text = _text_lower(title, summary)

    # 命中球员名 → 无论什么话题都保留（花边/民生例外）
    for name in player_names:
        if len(name) > 4 and name in text:
            return True

    # 命中体育关键词
    if _contains_any(text, SPORTS_KEYWORDS + PL_KEYWORDS):
        return True

    return False


# ── 主抓取逻辑 ────────────────────────────────────────────────────────────────

def fetch_all(hours: int, player_names: set[str]) -> list[NewsItem]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    seen_urls: set[str] = set()
    items: list[NewsItem] = []

    for source_name, url, tier in SOURCES:
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
        except Exception as e:
            print(f"[{source_name}] 抓取失败: {e}", file=sys.stderr)
            continue

        for entry in feed.entries:
            link = getattr(entry, "link", "") or ""
            if link in seen_urls:
                continue

            pub = _parse_date(entry)
            if pub and pub < cutoff:
                continue  # 太旧跳过

            title = _normalize(getattr(entry, "title", ""))
            raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
            # 去掉 HTML 标签
            summary = re.sub(r"<[^>]+>", " ", raw_summary)
            summary = _normalize(summary)[:300]

            if not title:
                continue

            if not _is_sports_relevant(title, summary, player_names):
                continue

            score = _score(title, summary, tier, player_names)
            keywords = _extract_keywords(title, summary, player_names)

            items.append(NewsItem(
                title=title,
                url=link,
                source=source_name,
                tier=tier,
                published=pub or datetime.now(timezone.utc),
                score=score,
                keywords=keywords,
                summary=summary,
            ))
            seen_urls.add(link)

        time.sleep(0.5)  # 礼貌性延迟

    # 按评分降序
    items.sort(key=lambda x: x.score, reverse=True)
    return items


# ── Telegram 发送 ─────────────────────────────────────────────────────────────

def _send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("⚠️  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 未设置，跳过发送")
        return

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    # 超长时分段
    max_len = 4000
    while text:
        chunk = text[:max_len]
        if len(text) > max_len:
            split = chunk.rfind("\n")
            if split > 0:
                chunk = text[:split]
        resp = requests.post(
            api_url,
            json={"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown",
                  "disable_web_page_preview": True},
            timeout=15,
        )
        if not resp.ok:
            print(f"Telegram 发送失败: {resp.status_code} {resp.text}", file=sys.stderr)
        text = text[len(chunk):].lstrip("\n")


# ── 格式化报告 ────────────────────────────────────────────────────────────────

def build_report(items: list[NewsItem], hours: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = f"📰 *英超新闻快报* — {now}\n过去 {hours}h 内共 {len(items)} 条体育相关新闻\n"

    if not items:
        return header + "\n暂无新内容。"

    lines = [header]
    top = items[:20]  # 最多显示20条

    current_tier = None
    for i, item in enumerate(top, 1):
        if item.tier != current_tier:
            current_tier = item.tier
            lines.append(f"\n{TIER_EMOJI[item.tier]} *{TIER_LABEL[item.tier]}*")

        pub_str = item.published.strftime("%H:%M") if item.published else "—"
        kw_str = "  `" + "` `".join(item.keywords[:4]) + "`" if item.keywords else ""

        line = (
            f"{i}\\. [{item.title}]({item.url})\n"
            f"   _{item.source}_ · {pub_str}{kw_str}"
        )
        lines.append(line)

    if len(items) > 20:
        lines.append(f"\n_（另有 {len(items) - 20} 条新闻未显示）_")

    return "\n".join(lines)


# ── 已发送 URL 去重 ───────────────────────────────────────────────────────────

def _load_sent_guids() -> set[str]:
    try:
        return set(json.loads(SENT_GUIDS.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _save_sent_guids(guids: set[str], new_urls: list[str]) -> None:
    updated = list(guids) + [u for u in new_urls if u not in guids]
    if len(updated) > MAX_GUIDS:
        updated = updated[-MAX_GUIDS:]
    SENT_GUIDS.write_text(json.dumps(updated, ensure_ascii=False), encoding="utf-8")


# ── OpenAI 批量翻译 ───────────────────────────────────────────────────────────

def translate_items(items: list[NewsItem]) -> dict[str, dict]:
    """批量翻译标题 + 生成中文摘要，返回 {url: {title_cn, summary_cn}}。"""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or not items:
        return {}

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except ImportError:
        print("openai 未安装，跳过翻译", file=sys.stderr)
        return {}

    # 构造批量请求，压缩 token 用量
    entries = "\n".join(
        f'{i+1}. URL:{item.url}\nEN_TITLE:{item.title}\nEN_SUMMARY:{item.summary[:200]}'
        for i, item in enumerate(items)
    )
    prompt = (
        "请将以下英文体育新闻翻译并摘要，用 JSON 数组返回，"
        "每项包含字段 url、title_cn（中文标题，15字以内，吸引眼球）、"
        "summary_cn（中文摘要，2句话以内，突出核心信息）。只返回 JSON，不要其他内容。\n\n"
        + entries
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=len(items) * 120,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        # 兼容 {"items": [...]} 或直接 [...]
        arr = data if isinstance(data, list) else data.get("items", list(data.values())[0] if data else [])
        return {entry["url"]: entry for entry in arr if "url" in entry}
    except Exception as e:
        print(f"翻译失败: {e}", file=sys.stderr)
        return {}


# ── 归档历史新闻 ──────────────────────────────────────────────────────────────

def update_archive(new_items: list[NewsItem], translations: dict[str, dict]) -> None:
    """将新条目追加到 news_archive.json，最多保留 MAX_ARCHIVE 条。"""
    try:
        existing = json.loads(ARCHIVE_JSON.read_text(encoding="utf-8")).get("items", [])
    except Exception:
        existing = []

    existing_urls = {item["url"] for item in existing}
    fetched_at = datetime.now(timezone.utc).isoformat()

    to_add = []
    for item in new_items:
        if item.url in existing_urls:
            continue
        tr = translations.get(item.url, {})
        to_add.append({
            "title":      item.title,
            "title_cn":   tr.get("title_cn", ""),
            "url":        item.url,
            "source":     item.source,
            "tier":       item.tier,
            "published":  item.published.isoformat() if item.published else None,
            "score":      round(item.score, 1),
            "keywords":   item.keywords,
            "summary":    item.summary,
            "summary_cn": tr.get("summary_cn", ""),
            "fetched_at": fetched_at,
        })

    merged = to_add + existing  # 新的在前
    if len(merged) > MAX_ARCHIVE:
        merged = merged[:MAX_ARCHIVE]

    ARCHIVE_JSON.write_text(
        json.dumps({"items": merged}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"归档已更新：新增 {len(to_add)} 条，共 {len(merged)} 条")


# ── 保存 JSON 供前端消费 ──────────────────────────────────────────────────────

def save_news_json(items: list[NewsItem], translations: dict[str, dict] | None = None) -> None:
    tr = translations or {}
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": [
            {
                "title":      item.title,
                "title_cn":   tr.get(item.url, {}).get("title_cn", ""),
                "url":        item.url,
                "source":     item.source,
                "tier":       item.tier,
                "published":  item.published.isoformat() if item.published else None,
                "score":      round(item.score, 1),
                "keywords":   item.keywords,
                "summary":    item.summary,
                "summary_cn": tr.get(item.url, {}).get("summary_cn", ""),
            }
            for item in items[:30]
        ],
    }
    NEWS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已保存 {len(payload['items'])} 条新闻到 {NEWS_JSON}")


# ── 入口 ─────────────────────────────────────────────────────────────────────

def main() -> None:
    dry_run = "--dry-run" in sys.argv
    hours = 8
    for arg in sys.argv:
        if arg.startswith("--hours="):
            hours = int(arg.split("=")[1])

    print(f"加载球员名单…")
    player_names = _load_player_names()
    print(f"已加载 {len(player_names)} 个球员名（含姓氏）")

    print(f"抓取过去 {hours}h 内的新闻…")
    all_items = fetch_all(hours, player_names)
    print(f"过滤后共 {len(all_items)} 条新闻")

    # 去重：找出本次未发送过的新条目
    sent_guids = _load_sent_guids()
    new_items = [it for it in all_items if it.url not in sent_guids]
    print(f"其中新条目：{len(new_items)} 条")

    gh_output = os.environ.get("GITHUB_OUTPUT", "")

    if not new_items:
        save_news_json(all_items)
        print("没有新内容，跳过翻译和 Telegram 推送")
        if gh_output:
            with open(gh_output, "a") as f:
                f.write("has_new=false\n")
        return

    # 有新内容：翻译 → 归档 → 更新 news.json → 发 Telegram
    print("调用 GPT-4o-mini 批量翻译新条目…")
    translations = translate_items(new_items)
    update_archive(new_items, translations)
    save_news_json(all_items, translations)

    if gh_output:
        with open(gh_output, "a") as f:
            f.write("has_new=true\n")

    report = build_report(new_items, hours)
    print("\n" + "=" * 60)
    print(report)
    print("=" * 60 + "\n")

    if dry_run:
        print("（dry-run 模式，不发送 Telegram）")
    else:
        _send_telegram(report)
        print("已发送 Telegram 消息")

    _save_sent_guids(sent_guids, [it.url for it in new_items])


if __name__ == "__main__":
    main()
