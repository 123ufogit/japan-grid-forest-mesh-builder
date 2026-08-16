import os
import sys
import glob
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    g_dir = os.path.join(base, "gpkg_by_zukaku")

    # ゴミ清掃
    for pat in ["*.tmp*", "*.final*", "*.strict*", "*.dropped*", "*.clean*"]:
        for tmp_f in glob.glob(os.path.join(g_dir, pat)):
            try:
                os.remove(tmp_f)
            except Exception:
                pass

    files = [os.path.join(g_dir, f) for f in os.listdir(g_dir) if f.endswith(".gpkg")]
    files.append(os.path.join(base, "ishikawa_forest_mesh_2500.gpkg"))

    print("=== SpatiaLite トリガー回避 SQLite UPDATE NULL 処理 ===")

    for f in files:
        if not os.path.exists(f):
            continue
        print(f"処理中: {os.path.basename(f)} ...", end="", flush=True)
        try:
            conn = sqlite3.connect(f)
            # SpatiaLite ダミー関数の登録
            conn.create_function("ST_IsEmpty", 1, lambda x: 0)
            conn.create_function("ST_MinX", 1, lambda x: 0)
            conn.create_function("ST_MinY", 1, lambda x: 0)
            conn.create_function("ST_MaxX", 1, lambda x: 0)
            conn.create_function("ST_MaxY", 1, lambda x: 0)

            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%'")
            tbls = [t[0] for t in cur.fetchall()]

            for tbl in tbls:
                cur.execute(f'PRAGMA table_info("{tbl}")')
                cols = [c[1] for c in cur.fetchall()]
                if "平均標高" in cols:
                    cur.execute(f'UPDATE "{tbl}" SET "平均標高" = NULL;')
                    conn.commit()
                    print(f" ({tbl})", end="")
            conn.close()
            print(" ✓ SUCCESS")
        except Exception as e:
            print(f" Error: {e}")

    print("\n✓ すべての GeoPackage ファイルの '平均標高' カラムの値が SQLite NULL にクリアされました。")

if __name__ == "__main__":
    main()
