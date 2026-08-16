import os
import sys
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

def nullify_table(gpkg_path):
    if not os.path.exists(gpkg_path):
        return
    try:
        conn = sqlite3.connect(gpkg_path)
        cur = conn.cursor()
        
        # テーブル名検索
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%boundary%'")
        tables = [t[0] for t in cur.fetchall()]
        
        for tbl in tables:
            cur.execute(f'PRAGMA table_info("{tbl}")')
            cols = [c[1] for c in cur.fetchall()]
            if "平均標高" in cols:
                cur.execute(f'UPDATE "{tbl}" SET "平均標高" = NULL;')
                conn.commit()
                print(f"✓ SQL NULL applied to {os.path.basename(gpkg_path)} (Table: {tbl})")
        conn.close()
    except Exception as e:
        print(f"Error on {os.path.basename(gpkg_path)}: {e}")

def main():
    base = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    g_dir = os.path.join(base, "gpkg_by_zukaku")

    files = [os.path.join(g_dir, f) for f in os.listdir(g_dir) if f.endswith(".gpkg")]
    for f in files:
        nullify_table(f)

if __name__ == "__main__":
    main()
