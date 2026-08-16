import os
import sys
import numpy as np
import geopandas as gpd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    g_dir = os.path.join(base, "gpkg_by_zukaku")

    print("=== 図郭境界レイヤー '平均標高' の NULL 化処理 ===")

    for f in os.listdir(g_dir):
        if f.endswith(".gpkg"):
            p = os.path.join(g_dir, f)
            print(f"処理中: {f} ...", end="", flush=True)
            try:
                layers = [l[0] for l in pyogrio.list_layers(p)]
                gdfs = {}
                for l in layers:
                    gdf = gpd.read_file(p, layer=l, engine="pyogrio")
                    if l == "ishikawa_zukaku_2500_boundary":
                        # 平均標高 カラムの全要素を None (NULL) にリセット
                        gdf["平均標高"] = None
                        gdf["平均標高"] = gdf["平均標高"].astype(object)
                    gdfs[l] = gdf

                tmp = p + ".nullified.gpkg"
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

    print("\n✓ すべての GeoPackage ファイルの図郭境界レイヤーの '平均標高' が NULL に更新されました。")

if __name__ == "__main__":
    main()
