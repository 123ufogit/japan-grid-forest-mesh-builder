import os
import sys
import geopandas as gpd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    g_dir = os.path.join(base, "gpkg_by_zukaku")

    print("=== 図郭境界レイヤーからの '平均標高' 属性削除・NULLリセット処理 ===")

    for f in os.listdir(g_dir):
        if f.endswith(".gpkg"):
            p = os.path.join(g_dir, f)
            print(f"処理中: {f} ...", end="", flush=True)
            try:
                layers = [l[0] for l in pyogrio.list_layers(p)]
                gdfs = {}
                for l in layers:
                    gdf = gpd.read_file(p, layer=l, engine="pyogrio")
                    if l == "ishikawa_zukaku_2500_boundary" and "平均標高" in gdf.columns:
                        gdf = gdf.drop(columns=["平均標高"])
                    gdfs[l] = gdf

                tmp = p + ".clean.gpkg"
                if os.path.exists(tmp):
                    os.remove(tmp)
                    
                for l, gdf in gdfs.items():
                    gdf.to_file(tmp, layer=l, driver="GPKG", engine="pyogrio")
                
                if os.path.exists(p):
                    os.remove(p)
                os.rename(tmp, p)
                print(" ✓ OK")
            except Exception as e:
                print(f" Error: {e}")

    print("\n✓ 図郭境界レイヤーから '平均標高' カラムを完全に除去・削除いたしました。")

if __name__ == "__main__":
    main()
