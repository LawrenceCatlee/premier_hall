#!/usr/bin/env python3
"""
外部定时触发器：每15分钟由外部 cron 调用一次。
检测当天英超比赛是否刚结束（开球时间 + OFFSET_MINUTES），
若是则调用 GitHub workflow_dispatch 触发数据更新。

部署方式（任意有 Python 的机器 / VPS）：
  */15 * * * * GITHUB_TOKEN=<token> GITHUB_REPO=owner/repo \
      python3 /path/to/dispatch_trigger.py >> /var/log/pl_trigger.log 2>&1

环境变量：
  GITHUB_TOKEN          必填 — 有 workflow 权限的 PAT
  GITHUB_REPO           必填 — 如 lawrencecatlee/premier_hall
  OFFSET_MINUTES        可选 — 开球后多少分钟触发（默认 125）
                         90min 正赛 + ~20min 补时/加时缓冲 + 15min 数据入库
  CHECK_WINDOW_MINUTES  可选 — 与 cron 间隔保持一致（默认 15）
"""
import os
import sys
import requests
from datetime import datetime, timezone, timedelta

# ── 配置 ────────────────────────────────────────────────────────────────────
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO   = os.environ.get("GITHUB_REPO", "")
WORKFLOW_FILE = "update-data.yml"
OFFSET_MIN    = int(os.environ.get("OFFSET_MINUTES", "125"))
WINDOW_MIN    = int(os.environ.get("CHECK_WINDOW_MINUTES", "15"))

PL_HEADERS = {
    "Origin":  "https://www.premierleague.com",
    "Referer": "https://www.premierleague.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
}

# ── PL API ───────────────────────────────────────────────────────────────────
def _get(url: str, **kwargs) -> dict:
    r = requests.get(url, headers=PL_HEADERS, timeout=15, **kwargs)
    r.raise_for_status()
    return r.json()


def current_season_id() -> int:
    data = _get(
        "https://footballapi.pulselive.com/football/competitions/1/compseasons"
        "?page=0&pageSize=1&sort=desc"
    )
    return int(data["content"][0]["id"])


def recent_fixtures(season_id: int) -> list:
    """取最近100场（含已完成），用于在本地按时间窗口过滤。"""
    data = _get(
        "https://footballapi.pulselive.com/football/fixtures"
        f"?compSeasons={season_id}&page=0&pageSize=100&sort=desc&statuses=C"
    )
    return data.get("content", [])


# ── GitHub API ───────────────────────────────────────────────────────────────
def trigger_workflow() -> None:
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("ERROR: GITHUB_TOKEN / GITHUB_REPO 未设置", file=sys.stderr)
        sys.exit(1)

    r = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}"
        f"/actions/workflows/{WORKFLOW_FILE}/dispatches",
        headers={
            "Authorization":        f"Bearer {GITHUB_TOKEN}",
            "Accept":               "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"ref": "main"},
        timeout=15,
    )
    if r.status_code not in (200, 204):
        print(f"workflow_dispatch 失败: {r.status_code} {r.text}", file=sys.stderr)
        sys.exit(1)


# ── 主逻辑 ───────────────────────────────────────────────────────────────────
def main() -> None:
    now          = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=WINDOW_MIN)

    print(f"[{now:%Y-%m-%d %H:%M UTC}] 检查窗口 [{window_start:%H:%M}, {now:%H:%M}] UTC  "
          f"(offset={OFFSET_MIN}min, window={WINDOW_MIN}min)")

    season_id = current_season_id()
    fixtures  = recent_fixtures(season_id)

    triggered_match = None
    for match in fixtures:
        ko_ms = float((match.get("kickoff") or {}).get("millis") or 0)
        if ko_ms == 0:
            continue

        ko      = datetime.fromtimestamp(ko_ms / 1000, tz=timezone.utc)
        trigger = ko + timedelta(minutes=OFFSET_MIN)

        if window_start <= trigger <= now:
            teams = match.get("teams") or [{}, {}]
            home  = ((teams[0].get("team") or {}).get("name") or "?")
            away  = ((teams[1].get("team") or {}).get("name") or "?")
            triggered_match = f"{home} vs {away}  (开球 {ko:%H:%M UTC}, 触发 {trigger:%H:%M UTC})"
            break  # 同一窗口内多场比赛只需触发一次

    if triggered_match:
        print(f"命中: {triggered_match}")
        trigger_workflow()
        print("workflow_dispatch 已触发")
    else:
        print("本窗口无比赛结束，跳过")


if __name__ == "__main__":
    main()
