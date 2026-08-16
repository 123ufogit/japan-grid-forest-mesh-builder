import os
import sys
import geopandas as gpd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    g_dir = os.path.join(base, "gpkg_by_zukaku")

    for f in os.listdir(g_dir):
        if f.endswith(".gpkg"):
            p = os.path.join(g_dir, f)
            print(f"Updating NULL for {f} ...", end="", flush=True)
            try:
                layers = [l[0] for l in pyogrio.list_layers(p)]
                gdfs = {}
                for l in layers:
                    gdf = gpd.read_file(p, layer=l, engine="pyogrio")
                    if l == "ishikawa_zukaku_2500_boundary":
                        # 平均標高 カラムの削除または None の明示的割り当て
                        if "平均標高" in gdf.columns:
                            gdf["平均標高"] = None
                    gdfs[l] = gdf

                tmp = p + ".final.gpkg"
                if os.path.exists(tmp):
                    os.remove(tmp)
                for l, gdf in gdfs.items():
                    gdf.to_file(tmp, layer=l, driver="GPKG", engine="pyogrio")
                
                if os.path.exists(p):
                    os.remove(p)
                os.rename(tmp, p)
                print(" ✓ DONE")
            except Exception as e:
                print(f" Error: {e}")

if __name__ == "__main__":
    main()
