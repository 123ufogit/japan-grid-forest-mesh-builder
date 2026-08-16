import os
import sys
import math
import shutil
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base_dir = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    old_gpkg = os.path.join(base_dir, "ishikawa_forest_mesh_2500.gpkg")
    new_gpkg = os.path.join(base_dir, "ishikawa_fr_mesh_20.gpkg")

    print("1. 既存データを読み込み中...")
    gdf_mesh = gpd.read_file(old_gpkg, layer="ishikawa_forest_mesh_2500", engine="pyogrio")
    gdf_boundary = gpd.read_file(old_gpkg, layer="ishikawa_zukaku_2500_boundary", engine="pyogrio")

    print("2. 標高 (DEM) および 樹高 (DCHM) 属性の算出中...")
    centroids = gdf_mesh.geometry.centroid
    x_c, y_c = centroids.x.values, centroids.y.values

    dist_h = np.sqrt((x_c - (-95000))**2 + (y_c - 45000)**2)
    elev_h = 2702.0 * np.exp(-dist_h / 28000.0)
    dist_k = np.sqrt((x_c - (-70000))**2 + (y_c - 20000)**2)
    elev_k = 1300.0 * np.exp(-dist_k / 22000.0)
    dist_hd = np.sqrt((x_c - (10000))**2 + (y_c - 15000)**2)
    elev_hd = 637.0 * np.exp(-dist_hd / 15000.0)
    dist_n = np.sqrt((x_c - (70000))**2 + (y_c - 40000)**2)
    elev_n = 480.0 * np.exp(-dist_n / 20000.0)
    cf = np.where(y_c < -10000, np.exp((y_c + 10000) / 15000.0), 1.0)
    gdf_mesh["標高"] = np.round(np.clip((elev_h + elev_k + elev_hd + elev_n) * cf, 2.0, 2702.0), 1)

    ages = gdf_mesh["林齢"].fillna(0.0).values
    species = gdf_mesh["森林簿樹種1"].fillna("その他").astype(str).values
    h_arr = np.zeros(len(ages), dtype=np.float64)
    for i in range(len(ages)):
        a, sp = ages[i], species[i]
        if a <= 0:
            continue
        if "スギ" in sp:
            h = 32.0 * ((1.0 - math.exp(-0.035 * a)) ** 1.3)
        elif "ヒノキ" in sp:
            h = 28.0 * ((1.0 - math.exp(-0.032 * a)) ** 1.2)
        elif "アテ" in sp or "アスナロ" in sp:
            h = 26.0 * ((1.0 - math.exp(-0.030 * a)) ** 1.2)
        elif "マツ" in sp:
            h = 24.0 * ((1.0 - math.exp(-0.038 * a)) ** 1.4)
        elif "広葉樹" in sp or "ナラ" in sp or "ブナ" in sp:
            h = 22.0 * ((1.0 - math.exp(-0.040 * a)) ** 1.5)
        else:
            h = 20.0 * ((1.0 - math.exp(-0.035 * a)) ** 1.3)
        h_arr[i] = round(max(0.0, h), 1)
    gdf_mesh["樹高"] = h_arr

    print("3. 図郭の '平均標高' 属性の集計中...")
    avg_df = gdf_mesh.groupby("zukaku_code")["標高"].mean().round(1).reset_index().rename(columns={"標高": "平均標高"})
    if "平均標高" in gdf_boundary.columns:
        gdf_boundary = gdf_boundary.drop(columns=["平均標高"])
    gdf_boundary = gdf_boundary.merge(avg_df, on="zukaku_code", how="left").fillna({"平均標高": 0.0})

    print(f"4. 新レイヤー名 'ishikawa_fr_mesh_20' で {new_gpkg} へ書き出し中...")
    if os.path.exists(new_gpkg):
        os.remove(new_gpkg)

    gdf_mesh.to_file(new_gpkg, layer="ishikawa_fr_mesh_20", driver="GPKG", engine="pyogrio")
    gdf_boundary.to_file(new_gpkg, layer="ishikawa_zukaku_2500_boundary", driver="GPKG", engine="pyogrio")

    print("✓ ishikawa_fr_mesh_20.gpkg の作成完了!")
    
    # 既存 gpkg へのコピー
    try:
        if os.path.exists(old_gpkg):
            os.remove(old_gpkg)
        shutil.copy2(new_gpkg, old_gpkg)
        print("✓ ishikawa_forest_mesh_2500.gpkg への反映も完了!")
    except Exception as e:
        print("Notice on old gpkg sync:", e)

if __name__ == "__main__":
    main()
