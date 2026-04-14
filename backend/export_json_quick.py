"""
export_json_quick.py

从现有的 premier_league_players_merged_final.csv 直接生成 players.json，
不重新爬取任何数据。用于本地预览或快速更新前端数据。

用法:
  cd backend
  python export_json_quick.py
"""

from pathlib import Path
import pandas as pd

# ── 路径 ──────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent
DATA_DIR    = BACKEND_DIR / "data"
MERGED_CSV  = DATA_DIR / "premier_league_players_merged_final.csv"
DOB_CSV     = DATA_DIR / "pulselive_player_dob.csv"
OUTPUT_JSON = BACKEND_DIR.parent / "frontend" / "public" / "data" / "players.json"


def main():
    if not MERGED_CSV.exists():
        print(f"[ERROR] 找不到 {MERGED_CSV}")
        print("请先运行完整管线: python merge_player_data.py")
        raise SystemExit(1)

    print(f"读取 {MERGED_CSV} ...")
    merged_df = pd.read_csv(MERGED_CSV)
    print(f"  {len(merged_df)} 行数据")

    # 把 pulselive 索引里的 nationality / position 补入 merged_df
    PULSELIVE_CSV = DATA_DIR / "pulselive_player_index_appearances.csv"
    if PULSELIVE_CSV.exists():
        pl_df = pd.read_csv(PULSELIVE_CSV)
        extra_cols = [c for c in ("nationality", "position", "current_club") if c in pl_df.columns]
        if extra_cols and "nationality" not in merged_df.columns:
            merged_df = merged_df.merge(
                pl_df[["player_id"] + extra_cols],
                on="player_id", how="left"
            )
            print(f"  补入 pulselive 字段: {extra_cols}")

    # 加载 DOB 缓存（如果存在）
    dob_df = None
    if DOB_CSV.exists():
        dob_df = pd.read_csv(DOB_CSV, dtype={"player_id": int})
        print(f"  加载 DOB 缓存: {len(dob_df)} 条")
    else:
        print("  未找到 DOB 缓存，birth_date 将为空（可运行完整管线获取）")

    # 调用合并模块里的 JSON 导出函数
    import sys
    sys.path.insert(0, str(BACKEND_DIR))
    from merge_player_data import export_players_json

    export_players_json(merged_df, OUTPUT_JSON, dob_df=dob_df)
    print(f"\n完成！players.json 已写入:\n  {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
