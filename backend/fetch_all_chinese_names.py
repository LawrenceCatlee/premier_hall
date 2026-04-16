"""
fetch_all_chinese_names.py
==========================
One-time script: fetch Chinese names for ALL players in the merged CSV.

Usage:
    python fetch_all_chinese_names.py

Output:
    backend/data/player_chinese_names.json

The JSON maps lowercase English player name → Chinese name, e.g.:
    {"james milner": "詹姆斯·米尔纳", ...}

Strategy:
  1. Pre-seed from the hardcoded SEED_MAP below (already curated names).
  2. For players not in the seed, query Wikipedia interlanguage links.
  3. Save everything to data/player_chinese_names.json.

This script is NOT part of the automated pipeline. Run it manually when you
want to refresh the full name mapping (e.g. after a new season of new players
has been pulled by the data scripts).
"""

import json
import time
import re
import requests
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
CN_NAMES_FILE = DATA_DIR / "player_chinese_names.json"
MERGED_CSV = DATA_DIR / "premier_league_players_merged_final.csv"
WIKI_API = "https://en.wikipedia.org/w/api.php"

# --- Pre-seeded curated names (copied from merge_player_data.py PLAYER_CN_NAME_MAP) ---
SEED_MAP: dict[str, str] = {
    'gareth barry': '加雷斯·巴里',
    'ryan giggs': '瑞安·吉格斯',
    'james milner': '詹姆斯·米尔纳',
    'frank lampard': '弗兰克·兰帕德',
    'david james': '大卫·詹姆斯',
    'gary speed': '加里·斯皮德',
    'emile heskey': '埃米尔·赫斯基',
    'sol campbell': '索尔·坎贝尔',
    'paul scholes': '保罗·斯科尔斯',
    'jamie carragher': '杰米·卡拉格',
    'wayne rooney': '韦恩·鲁尼',
    'steven gerrard': '史蒂文·杰拉德',
    'john terry': '约翰·特里',
    'andy cole': '安迪·科尔',
    'andrew cole': '安迪·科尔',
    'alan shearer': '艾伦·希勒',
    'michael owen': '迈克尔·欧文',
    'robbie fowler': '罗比·福勒',
    'peter schmeichel': '彼得·舒梅切尔',
    'petr cech': '彼得·切赫',
    'david seaman': '大卫·西曼',
    'mark schwarzer': '马克·施瓦泽',
    'brad friedel': '布拉德·弗里德尔',
    'shay given': '谢·吉文',
    'tim howard': '蒂姆·霍华德',
    'paul robinson': '保罗·罗宾逊',
    'ashley cole': '阿什利·科尔',
    'gary neville': '加里·内维尔',
    'phil neville': '菲尔·内维尔',
    'nicky butt': '尼基·巴特',
    'roy keane': '罗伊·基恩',
    'david beckham': '大卫·贝克汉姆',
    'patrick vieira': '帕特里克·维埃拉',
    'robert pires': '罗伯特·皮雷斯',
    'freddie ljungberg': '弗雷迪·云加贝里',
    'thierry henry': '蒂埃里·亨利',
    'dennis bergkamp': '丹尼斯·伯格坎普',
    'nicolas anelka': '尼古拉斯·阿内尔卡',
    'tony adams': '托尼·亚当斯',
    'martin keown': '马丁·基翁',
    'nigel winterburn': '奈杰尔·温特伯恩',
    'lee dixon': '李·迪克森',
    'ray parlour': '雷·帕洛尔',
    'dwight yorke': '德怀特·约克',
    'ruud van nistelrooij': '鲁德·范尼斯特尔罗伊',
    'ole gunnar solskjaer': '奥莱·冈纳·索尔斯克亚',
    'robin van persie': '罗宾·范佩西',
    'dimitar berbatov': '迪米塔尔·贝尔巴托夫',
    'carlos tevez': '卡洛斯·特维斯',
    'cristiano ronaldo': '克里斯蒂亚诺·罗纳尔多',
    'michael carrick': '迈克尔·卡里克',
    'ashley young': '阿什利·杨',
    'wes brown': '韦斯·布朗',
    "john o'shea": '约翰·奥谢',
    'rio ferdinand': '里奥·费迪南德',
    'didier drogba': '迪迪埃·德罗巴',
    'eden hazard': '伊甸·阿扎尔',
    'john obi mikel': '约翰·奥比·米克尔',
    'fernando torres': '费尔南多·托雷斯',
    'peter crouch': '彼得·克劳奇',
    'teddy sheringham': '泰迪·谢林汉姆',
    'dion dublin': '狄翁·都柏林',
    'les ferdinand': '莱斯·费迪南德',
    'ledley king': '莱德利·金',
    'robbie keane': '罗比·基恩',
    'jermain defoe': '贾梅因·德福',
    'darren bent': '达伦·本特',
    'darren anderton': '达伦·安德顿',
    'michael dawson': '迈克尔·道森',
    'leighton baines': '利顿·贝恩斯',
    'leon osman': '莱昂·奥斯曼',
    'tim cahill': '蒂姆·卡希尔',
    'phil jagielka': '菲利普·雅吉尔卡',
    'seamus coleman': '谢默斯·科尔曼',
    'mikel arteta': '米克尔·阿尔特塔',
    'kevin campbell': '凯文·坎贝尔',
    'sami hyypia': '萨米·许佩亚',
    'jamie redknapp': '杰米·雷德克纳普',
    'martin skrtel': '马丁·斯克特尔',
    'daniel agger': '丹尼尔·阿格',
    'lucas leiva': '卢卡斯·莱瓦',
    'kolo toure': '科洛·图雷',
    'bacary sagna': '巴卡里·萨尼亚',
    'william gallas': '威廉·加拉斯',
    'mikael silvestre': '米卡埃尔·西尔韦斯特雷',
    'sylvain distin': '西尔万·迪斯汀',
    'matthew le tissier': '马修·勒蒂西尔',
    'matt le tissier': '马修·勒蒂西尔',
    'nigel martyn': '奈杰尔·马丁',
    'sander westerveld': '桑德·韦斯特韦尔德',
    'dean kiely': '迪安·基利',
    'scott carson': '斯科特·卡森',
    'ben foster': '本·福斯特',
    'robert green': '罗伯特·格林',
    'stephen warnock': '史蒂芬·沃诺克',
    'martin laursen': '马丁·劳森',
    'olof mellberg': '奥洛夫·梅尔贝里',
    'gareth southgate': '加雷斯·索斯盖特',
    'ugo ehiogu': '乌戈·埃霍古',
    'alan wright': '艾伦·莱特',
    'mark bosnich': '马克·博斯尼奇',
    'peter enckelman': '彼得·恩克尔曼',
    'darius vassell': '达里亚斯·瓦塞尔',
    'tommy johnson': '汤米·约翰逊',
    'paul merson': '保罗·默森',
    'lee hendrie': '李·亨德里',
    'ian taylor': '伊恩·泰勒',
    'tommy elphick': '汤米·埃尔菲克',
    'marc albrighton': '马克·阿尔布莱顿',
    'shinji okazaki': '冈崎慎司',
    'riyad mahrez': '里亚德·马赫雷斯',
    'jamie vardy': '杰米·瓦尔迪',
    'kasper schmeichel': '卡斯帕·舒梅切尔',
    'christian fuchs': '克里斯蒂安·富克斯',
    'danny drinkwater': '丹尼·德林克沃特',
    'wes morgan': '韦斯·摩根',
    'robert huth': '罗伯特·胡特',
    'son heung-min': '孙兴慜',
    'harry kane': '哈里·凯恩',
    'hugo lloris': '乌戈·洛里斯',
    'jan vertonghen': '扬·弗托根',
    'toby alderweireld': '托比·阿尔德韦勒尔德',
    'kieran trippier': '基兰·特里皮尔',
    'dele alli': '德莱·阿利',
    'christian eriksen': '克里斯蒂安·埃里克森',
    'vincent kompany': '文森特·孔帕尼',
    'yaya toure': '亚亚·图雷',
    'david silva': '大卫·席尔瓦',
    'sergio aguero': '塞尔希奥·阿奎罗',
    'ilkay gundogan': '伊尔卡伊·居恩多安',
    'ilkay gündogan': '伊尔卡伊·居恩多安',
    'raheem sterling': '拉希姆·斯特林',
    'kevin de bruyne': '凯文·德布劳内',
    'fernandinho': '费尔南迪尼奥',
    'nicolas otamendi': '尼古拉斯·奥塔门迪',
    'kyle walker': '凯尔·沃克',
    'pablo zabaleta': '巴勃罗·萨瓦莱塔',
    'joe hart': '乔·哈特',
    'jordan henderson': '乔丹·亨德森',
    'virgil van dijk': '维吉尔·范戴克',
    'alisson becker': '阿利松·贝克尔',
    'trent alexander-arnold': '特伦特·亚历山大-阿诺德',
    'andy robertson': '安迪·罗伯逊',
    'sadio mane': '萨迪奥·马内',
    'mohamed salah': '穆罕默德·萨拉赫',
    'roberto firmino': '罗伯托·菲尔米诺',
    'xabi alonso': '沙比·阿隆索',
    'dirk kuijt': '德克·库伊特',
    'pepe reina': '佩佩·雷纳',
    'paul konchesky': '保罗·坤切斯基',
    'cesc fabregas': '塞斯克·法布雷加斯',
    'samir nasri': '萨米尔·纳斯里',
    'gael clichy': '加埃尔·克利希',
    'thomas vermaelen': '托马斯·弗梅伦',
    'per mertesacker': '佩尔·默特萨克',
    'laurent koscielny': '洛朗·科西尔尼',
    'nacho monreal': '纳乔·蒙雷亚尔',
    'santi cazorla': '桑蒂·卡索拉',
    'alexis sanchez': '阿莱克西斯·桑切斯',
    'mesut ozil': '梅苏特·厄齐尔',
    'pierre-emerick aubameyang': '皮埃尔-埃梅里克·奥巴姆扬',
    'alexandre lacazette': '亚历山大·拉卡泽特',
    'granit xhaka': '格拉尼特·贾卡',
    'bernd leno': '贝恩德·莱诺',
    'hector bellerin': '埃克托尔·贝列林',
    'rob holding': '罗伯·霍尔丁',
    'jack wilshere': '杰克·威尔谢尔',
    'theo walcott': '西奥·沃尔科特',
    'tomás soucek': '托马斯·苏切克',
    'mark noble': '马克·诺布尔',
    'michail antonio': '米夏伊尔·安东尼奥',
    'declan rice': '德克兰·赖斯',
    'craig dawson': '克雷格·道森',
    'issa diop': '伊萨·迪奥普',
    'aaron cresswell': '亚伦·克莱斯韦尔',
    'pablo fornals': '巴勃罗·福纳尔斯',
    'andriy yarmolenko': '安德烈·亚尔莫连科',
    'patrice evra': '帕特里斯·埃夫拉',
    'nemanja vidic': '内马尼亚·维迪奇',
    'jonny evans': '乔尼·埃文斯',
    'darren fletcher': '达伦·弗莱彻',
    'anderson': '安德森',
    'antonio valencia': '安东尼奥·巴伦西亚',
    'wayne bridge': '韦恩·布里奇',
    'claude makelele': '克劳德·马克莱莱',
    'michael essien': '迈克尔·埃辛',
    'joe cole': '乔·科尔',
    'arjen robben': '阿尔扬·罗本',
    'shaun wright-phillips': '肖恩·赖特-菲利普斯',
    'scott parker': '斯科特·帕克',
    'john lundstram': '约翰·伦斯特拉姆',
    'james ward-prowse': '詹姆斯·沃德-普劳斯',
    'maya yoshida': '吉田麻也',
    'dejan lovren': '德扬·洛夫伦',
    'nathaniel clyne': '纳撒尼尔·克莱恩',
    'emre can': '埃姆雷·詹',
    'adam lallana': '亚当·拉拉纳',
    'philippe coutinho': '菲利普·库蒂尼奥',
    'daniel sturridge': '丹尼尔·斯特里奇',
    'divock origi': '迪沃克·奥里吉',
    'gylfi sigurdsson': '吉尔菲·西于尔兹松',
    'peter odemwingie': '彼得·奥德姆温吉耶',
    'andrew johnson': '安德鲁·约翰逊',
    'david wheater': '大卫·韦特尔',
    'ian wright': '伊恩·赖特',
    'eric cantona': '埃里克·坎通纳',
}


ZH_API = "https://zh.wikipedia.org/w/api.php"


def _strip_html(text: str) -> str:
    import html as _html
    return re.sub(r'<[^>]+>', '', _html.unescape(text)).strip()


def _clean_zh_title(title: str) -> str:
    """Strip disambiguation suffixes like (足球运动员) from Wikipedia page titles."""
    return re.sub(r'\s*（[^）]*）$', '', re.sub(r'\s*\([^)]*\)$', '', title)).strip()


def _zh_title_to_mandarin(zh_title: str, session: requests.Session) -> str:
    """
    Convert a zh.wikipedia.org page title to Simplified Chinese Mandarin
    by calling zh.wikipedia.org with uselang=zh-hans.
    Returns the displaytitle, or the original title on failure.
    """
    try:
        resp = session.get(ZH_API, params={
            'action': 'parse',
            'page': zh_title,
            'prop': 'displaytitle',
            'uselang': 'zh-hans',
            'format': 'json',
        }, timeout=15)
        data = resp.json()
        if 'error' not in data:
            raw = data.get('parse', {}).get('displaytitle', '')
            result = _strip_html(raw)
            if result:
                return result
    except Exception:
        pass
    return zh_title


def fetch_zh_name_via_wiki(player_name: str) -> str | None:
    """
    Try English Wikipedia interlanguage links to find the Chinese name,
    then convert via zh.wikipedia.org to Simplified Chinese Mandarin.
    Returns the Simplified Chinese name, or None if not found.
    """
    session = requests.Session()
    session.headers.update({'User-Agent': 'PremierHallBot/1.0 (liguangzhaolvcatlee@gmail.com)'})

    def _get_langlink(title: str) -> str | None:
        try:
            resp = session.get(WIKI_API, params={
                'action': 'query',
                'titles': title,
                'prop': 'langlinks',
                'lllang': 'zh',
                'format': 'json',
                'redirects': 1,
            }, timeout=10)
            pages = resp.json().get('query', {}).get('pages', {})
            for page in pages.values():
                if page.get('ns', -1) != 0:
                    continue
                for ll in page.get('langlinks', []):
                    if ll.get('lang') == 'zh':
                        return _clean_zh_title(ll.get('*', ''))
        except Exception:
            pass
        return None

    # 1. Direct title lookup
    zh_title = _get_langlink(player_name)

    # 2. Search Wikipedia for footballer if not found
    if not zh_title:
        try:
            resp = session.get(WIKI_API, params={
                'action': 'query',
                'list': 'search',
                'srsearch': f'{player_name} footballer Premier League',
                'format': 'json',
                'srlimit': 3,
            }, timeout=10)
            results = resp.json().get('query', {}).get('search', [])
            for hit in results[:2]:
                candidate = hit['title']
                if any(skip in candidate.lower() for skip in ['season', 'club', 'f.c.', 'league']):
                    continue
                zh_title = _get_langlink(candidate)
                if zh_title:
                    break
                time.sleep(0.3)
        except Exception:
            pass

    if not zh_title:
        return None

    # 3. Convert zh.wikipedia.org title to Simplified Chinese Mandarin
    time.sleep(0.3)
    return _zh_title_to_mandarin(zh_title, session)


def load_existing_names() -> dict[str, str]:
    """Load the existing player_chinese_names.json if it exists."""
    if CN_NAMES_FILE.exists():
        with open(CN_NAMES_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_names(names: dict[str, str]) -> None:
    CN_NAMES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CN_NAMES_FILE, 'w', encoding='utf-8') as f:
        json.dump(dict(sorted(names.items())), f, ensure_ascii=False, indent=2)
    print(f"Saved {len(names)} entries → {CN_NAMES_FILE}")


def main() -> None:
    # Load player names from merged CSV
    if not MERGED_CSV.exists():
        print(f"ERROR: {MERGED_CSV} not found. Run merge_player_data.py first.")
        return

    df = pd.read_csv(MERGED_CSV, usecols=['player_name'])
    all_names = df['player_name'].dropna().str.strip().unique().tolist()
    print(f"Found {len(all_names)} players in merged CSV.")

    # Start from existing JSON (preserves any manual corrections)
    result = load_existing_names()

    # Layer in seed map for any missing entries
    for name_lower, cn in SEED_MAP.items():
        if name_lower not in result:
            result[name_lower] = cn

    # Find players still missing a Chinese name
    missing = [n for n in all_names if n.lower() not in result]
    print(f"{len(missing)} players need Wikipedia lookup.")

    for i, name in enumerate(missing, 1):
        print(f"[{i}/{len(missing)}] Looking up: {name} ...", end=' ', flush=True)
        zh = fetch_zh_name_via_wiki(name)
        if zh:
            print(f"→ {zh}")
            result[name.lower()] = zh
        else:
            print("→ not found")
            # Fallback: keep the English name so the JSON entry exists
            result[name.lower()] = name

        # Save incrementally every 20 players so we don't lose progress
        if i % 20 == 0:
            save_names(result)

        time.sleep(0.5)  # be polite to Wikipedia

    save_names(result)
    print("Done.")


if __name__ == '__main__':
    main()
