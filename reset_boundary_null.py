import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    zukaku_geojson = os.path.join(base, "ishikawa_zukaku_2500.geojson")
    g_dir = os.path.join(base, "gpkg_by_zukaku")

    print("=== 図郭境界レイヤー '平均標高' の GeoPackage NULL リセット処理 ===")

    gdf_z = gpd.read_file(zukaku_geojson, engine="pyogrio").rename(columns={"code": "zukaku_code"})[["zukaku_code", "geometry"]]
    gdf_z_6675 = gdf_z.to_crs(epsg=6675)
    gdf_z_6675["平均標高"] = None
    gdf_z_6675["平均標高"] = gdf_z_6675["平均標高"].astype(object)

    for f in os.listdir(g_dir):
        if f.endswith(".gpkg") and f != "ishikawa_zukaku_2500_boundary_all.gpkg":
            p = os.path.join(g_dir, f)
            print(f"処理中: {f} ...", end="", flush=True)
            
            try:
                gdf_m = gpd.read_file(p, layer="ishikawa_fr_mesh_20", engine="pyogrio")
                codes = gdf_m["zukaku_code"].unique()
                sub_b = gdf_z_6675[gdf_z_6675["zukaku_code"].isin(codes)].copy()

                tmp = p + ".tmp.gpkg"
                if os.path.exists(tmp):
                    os.remove(tmp)
                    
                gdf_m.to_file(tmp, layer="ishikawa_fr_mesh_20", driver="GPKG", engine="pyogrio")
                sub_b.to_file(tmp, layer="ishikawa_zukaku_2500_boundary", driver="GPKG", engine="pyogrio")
                
                if os.path.exists(p):
                    os.remove(p)
                os.rename(tmp, p)
                print(" ✓ OK")
            except Exception as e:
                print(f" Error: {e}")

    # マスター図郭境界
    all_p = os.path.join(g_dir, "ishikawa_zukaku_2500_boundary_all.gpkg")
    print(f"処理中: ishikawa_zukaku_2500_boundary_all.gpkg ...", end="", flush=True)
    try:
        tmp_all = all_p + ".tmp.gpkg"
        if os.path.exists(tmp_all):
            os.remove(tmp_all)
        gdf_z_6675.to_file(tmp_all, layer="ishikawa_zukaku_2500_boundary", driver="GPKG", engine="pyogrio")
        if os.path.exists(all_p):
            os.remove(all_p)
        os.rename(tmp_all, all_p)
        print(" ✓ OK")
    except Exception as e:
        print(f" Error: {e}")

    print("\n✓ すべての図郭境界レイヤーの '平均標高' が GeoPackage 上で完全に NULL に設定されました。")

if __name__ == "__main__":
    main()
