import os
import sys
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

def main():
    gpkg_ic = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson\gpkg_by_zukaku\ishikawa_fr_mesh_20_07IC.gpkg"

    if os.path.exists(gpkg_ic):
        print(f"=== {os.path.basename(gpkg_ic)} の SQL ALTER TABLE DROP COLUMN 処理 ===")
        conn = sqlite3.connect(gpkg_ic)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%'")
        tbls = [t[0] for t in cur.fetchall()]
        for tbl in tbls:
            cur.execute(f'PRAGMA table_info("{tbl}")')
            cols = [c[1] for c in cur.fetchall()]
            for target in ["標高", "樹高", "平均標高"]:
                if target in cols:
                    try:
                        cur.execute(f'ALTER TABLE "{tbl}" DROP COLUMN "{target}"')
                        conn.commit()
                        print(f" ✓ カラム '{target}' をテーブル '{tbl}' から完全削除しました")
                    except Exception as e:
                        print(f" Error dropping {target}: {e}")
        conn.close()

if __name__ == "__main__":
    main()
