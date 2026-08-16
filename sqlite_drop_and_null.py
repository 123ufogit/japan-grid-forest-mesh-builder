import os
import sys
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    g_dir = os.path.join(base, "gpkg_by_zukaku")

    gpkgs = [os.path.join(g_dir, f) for f in os.listdir(g_dir) if f.endswith(".gpkg")]
    gpkgs.append(os.path.join(base, "ishikawa_forest_mesh_2500.gpkg"))

    print("=== SQLite 直接操作による '平均標高' カラム削除/NULL化処理 ===")

    for p in gpkgs:
        if not os.path.exists(p):
            continue
        print(f"処理中: {os.path.basename(p)} ...", end="", flush=True)
        try:
            conn = sqlite3.connect(p)
            cur = conn.cursor()
            
            # テーブル検索
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%'")
            tables = [t[0] for t in cur.fetchall()]
            
            for tbl in tables:
                cur.execute(f'PRAGMA table_info("{tbl}")')
                cols = [c[1] for c in cur.fetchall()]
                if "平均標高" in cols:
                    try:
                        # SQLite 3.35+ カラム削除
                        cur.execute(f'ALTER TABLE "{tbl}" DROP COLUMN "平均標高"')
                        conn.commit()
                        print(f" (カラム '平均標高' を削除)", end="")
                    except Exception:
                        # 全値を NULL 化
                        cur.execute(f'UPDATE "{tbl}" SET "平均標高" = NULL')
                        conn.commit()
                        print(f" (全値を NULL に設定)", end="")
            conn.close()
            print(" ✓ OK")
        except Exception as e:
            print(f" Error: {e}")

    print("\n✓ すべての GeoPackage ファイルの '平均標高' 属性の処理が完了いたしました。")

if __name__ == "__main__":
    main()
