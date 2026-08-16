import os
import sys
import geopandas as gpd
import pyogrio
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    g_dir = os.path.join(base, "gpkg_by_zukaku")

    files = [os.path.join(g_dir, f) for f in os.listdir(g_dir) if f.endswith(".gpkg")]
    files.append(os.path.join(base, "ishikawa_forest_mesh_2500.gpkg"))

    print("=== 全 GeoPackage から '標高' および '樹高' フィールドの完全削除処理 ===")

    for f in files:
        if not os.path.exists(f):
            continue
            
        print(f"処理中: {os.path.basename(f)} ...", end="", flush=True)
        try:
            layers = [l[0] for l in pyogrio.list_layers(f)]
            gdfs = {}
            for l in layers:
                gdf = gpd.read_file(f, layer=l, engine="pyogrio")
                cols_to_drop = [c for c in ["標高", "樹高", "平均標高"] if c in gdf.columns]
                if cols_to_drop:
                    gdf = gdf.drop(columns=cols_to_drop)
                gdfs[l] = gdf

            tmp_p = f + ".clean_nodem.gpkg"
            if os.path.exists(tmp_p):
                os.remove(tmp_p)

            for l_name, gdf in gdfs.items():
                gdf.to_file(tmp_p, layer=l_name, driver="GPKG", engine="pyogrio")

            if os.path.exists(f):
                os.remove(f)
            os.rename(tmp_p, f)

            # SQLite レベルでも二重安全確認
            try:
                conn = sqlite3.connect(f)
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%'")
                tbls = [t[0] for t in cur.fetchall()]
                for tbl in tbls:
                    cur.execute(f'PRAGMA table_info("{tbl}")')
                    cols = [c[1] for c in cur.fetchall()]
                    for target_col in ["標高", "樹高", "平均標高"]:
                        if target_col in cols:
                            try:
                                cur.execute(f'ALTER TABLE "{tbl}" DROP COLUMN "{target_col}"')
                                conn.commit()
                            except Exception:
                                pass
                conn.close()
            except Exception:
                pass

            print(" ✓ フィールド削除完了")
        except Exception as e:
            print(f" Error: {e}")

    print("\n✓ すべての GeoPackage ファイルから '標高' および '樹高' フィールドが完全に削除されました。")

if __name__ == "__main__":
    main()
