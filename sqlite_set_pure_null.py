import os
import sys
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    g_dir = os.path.join(base, "gpkg_by_zukaku")

    files = [os.path.join(g_dir, f) for f in os.listdir(g_dir) if f.endswith(".gpkg")]
    files.append(os.path.join(base, "ishikawa_forest_mesh_2500.gpkg"))

    print("=== GeoPackage (SQLite) 直接 UPDATE NULL 確定処理 ===")

    for f in files:
        if not os.path.exists(f):
            continue
        try:
            conn = sqlite3.connect(f)
            cur = conn.cursor()
            
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%'")
            tbls = [t[0] for t in cur.fetchall()]
            
            for tbl in tbls:
                cur.execute(f'PRAGMA table_info("{tbl}")')
                cols = [c[1] for c in cur.fetchall()]
                if "平均標高" not in cols:
                    cur.execute(f'ALTER TABLE "{tbl}" ADD COLUMN "平均標高" REAL;')
                cur.execute(f'UPDATE "{tbl}" SET "平均標高" = NULL;')
                conn.commit()
            conn.close()
            print(f"✓ {os.path.basename(f)}: 全テーブルの '平均標高' を NULL にクリアしました。")
        except Exception as e:
            print(f"Error on {os.path.basename(f)}: {e}")

if __name__ == "__main__":
    main()
