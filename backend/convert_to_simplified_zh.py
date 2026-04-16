"""
convert_to_simplified_zh.py
============================
Post-processor: use zh.wikipedia.org with uselang=zh-hans to get the correct
Simplified Chinese Mandarin transliteration for all entries in player_chinese_names.json.

Usage:
    python convert_to_simplified_zh.py

Reads/writes data/player_chinese_names.json in place.
~3 minutes for ~600 entries (0.3s delay per request to respect Wikipedia rate limits).
"""

import json
import re
import time
import requests
from pathlib import Path

CN_FILE = Path(__file__).parent / "data" / "player_chinese_names.json"
ZH_API  = "https://zh.wikipedia.org/w/api.php"
HAS_CJK = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "PremierHallBot/1.0 (liguangzhaolvcatlee@gmail.com)"})


def _strip_html(text: str) -> str:
    import html
    return re.sub(r'<[^>]+>', '', html.unescape(text)).strip()


def to_mandarin_simplified(zh_title: str):
    """
    Ask zh.wikipedia.org to parse the page with uselang=zh-hans.
    Returns the displaytitle in Simplified Chinese Mandarin, or None on failure.
    """
    try:
        resp = SESSION.get(ZH_API, params={
            "action": "parse",
            "page": zh_title,
            "prop": "displaytitle",
            "uselang": "zh-hans",
            "format": "json",
        }, timeout=15)
        data = resp.json()
        if "error" in data:
            return None
        raw = data.get("parse", {}).get("displaytitle", "")
        result = _strip_html(raw)
        return result or None
    except Exception:
        return None


def main() -> None:
    if not CN_FILE.exists():
        print(f"ERROR: {CN_FILE} not found.")
        return

    with open(CN_FILE, encoding="utf-8") as f:
        data: dict[str, str] = json.load(f)

    # Only process entries that have CJK characters (skip "not found" = English name kept)
    to_convert = {k: v for k, v in data.items() if HAS_CJK.search(v)}
    print(f"Total entries: {len(data)} | Will query zh.wikipedia.org for: {len(to_convert)}")

    updated = 0
    for i, (eng_key, zh_val) in enumerate(to_convert.items(), 1):
        simp = to_mandarin_simplified(zh_val)
        if simp and simp != zh_val:
            print(f"  [{i}/{len(to_convert)}] {zh_val} → {simp}")
            data[eng_key] = simp
            updated += 1
        # (no output for unchanged entries)

        if i % 50 == 0:
            with open(CN_FILE, "w", encoding="utf-8") as f:
                json.dump(dict(sorted(data.items())), f, ensure_ascii=False, indent=2)
            print(f"  (checkpoint {i}/{len(to_convert)}, {updated} updated)")

        time.sleep(0.3)

    with open(CN_FILE, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(data.items())), f, ensure_ascii=False, indent=2)
    print(f"\nDone. {updated} entries updated → {CN_FILE}")


if __name__ == "__main__":
    main()
