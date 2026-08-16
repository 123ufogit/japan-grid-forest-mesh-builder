import os
import sys
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    g_dir = os.path.join(base, "gpkg_by_zukaku")

    files = [os.path.join(g_dir, f) for f in os.listdir(g_dir) if f.endswith(".gpkg")]
    files.append(os.path.join(base, "ishikawa_forest_mesh_2500.gpkg"))

    print("=== GeoPackage (SQLite) 直接 SQL による '平均標高' NULL 化処理 ===")

    for f in files:
        if not os.path.exists(f):
            continue
        print(f"処理中: {os.path.basename(f)} ...", end="", flush=True)
        try:
            conn = sqlite3.connect(f)
            cur = conn.cursor()
            
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%boundary%' OR name LIKE '%zukaku%')")
            tbls = [t[0] for t in cur.fetchall()]
            
            updated = False
            for tbl in tbls:
                cur.execute(f"PRAGMA table_info(\"{tbl}\")")
                cols = [c[1] for c in cur.fetchall()]
                if "平均標高" in cols:
                    cur.execute(f'UPDATE "{tbl}" SET "平均標高" = NULL')
                    conn.commit()
                    updated = True
                    
            conn.close()
            if updated:
                print(" ✓ SQLite NULL 更新完了")
            else:
                print(" (対象カラムなし)")
        except Exception as e:
            print(f" Error: {e}")

    print("\n✓ すべての GeoPackage データベース上の '平均標高' カラムの値が SQLite レベルで完全な NULL に設定されました。")

if __name__ == "__main__":
    main()
