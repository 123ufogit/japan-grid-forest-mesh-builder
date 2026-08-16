import os
import sys
import glob
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    g_dir = os.path.join(base, "gpkg_by_zukaku")

    print("=== 全 GeoPackage 一時ファイル掃除 & SQL NULL 一括設定 ===")

    # 一時ファイルの削除
    temp_patterns = ["*.tmp*", "*.final*", "*.strict*", "*.dropped*", "*.clean*"]
    for pat in temp_patterns:
        for tmp_f in glob.glob(os.path.join(g_dir, pat)):
            try:
                os.remove(tmp_f)
                print(f"削除した一時ファイル: {os.path.basename(tmp_f)}")
            except Exception:
                pass

    # 正式な gpkg の処理
    gpkg_files = [os.path.join(g_dir, f) for f in os.listdir(g_dir) if f.endswith(".gpkg")]
    for p in gpkg_files:
        print(f"処理中: {os.path.basename(p)} ...", end="", flush=True)
        try:
            conn = sqlite3.connect(p)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%'")
            tables = [t[0] for t in cur.fetchall()]
            for tbl in tables:
                cur.execute(f'PRAGMA table_info("{tbl}")')
                cols = [c[1] for c in cur.fetchall()]
                if "平均標高" in cols:
                    cur.execute(f'UPDATE "{tbl}" SET "平均標高" = NULL;')
                    conn.commit()
                    print(f" ({tbl} の平均標高を NULL 化)", end="")
            conn.close()
            print(" ✓ SUCCESS")
        except Exception as e:
            print(f" Error: {e}")

    print("\n✓ すべての正式 GeoPackage ファイルの '平均標高' が SQLite NULL に完全クリアされました。")

if __name__ == "__main__":
    main()
