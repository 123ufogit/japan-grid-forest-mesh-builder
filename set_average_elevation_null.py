import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def set_null_average_elevation(gpkg_path):
    if not os.path.exists(gpkg_path):
        return
        
    try:
        layers = [l[0] for l in pyogrio.list_layers(gpkg_path)]
        if "ishikawa_zukaku_2500_boundary" not in layers:
            return
            
        print(f"処理中: {os.path.basename(gpkg_path)} ...", end="", flush=True)
        
        # 全レイヤーを読み込み
        layer_gdfs = {}
        for l in layers:
            layer_gdfs[l] = gpd.read_file(gpkg_path, layer=l, engine="pyogrio")
            
        # ishikawa_zukaku_2500_boundary の 平均標高 を NULL に設定
        gdf_boundary = layer_gdfs["ishikawa_zukaku_2500_boundary"]
        gdf_boundary["平均標高"] = None
        gdf_boundary["平均標高"] = gdf_boundary["平均標高"].astype(object)
        layer_gdfs["ishikawa_zukaku_2500_boundary"] = gdf_boundary

        # 一時ファイルへ出力して上書き
        dir_name = os.path.dirname(gpkg_path)
        temp_path = os.path.join(dir_name, f"temp_{os.path.basename(gpkg_path)}")
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        for idx, (l_name, gdf) in enumerate(layer_gdfs.items()):
            gdf.to_file(temp_path, layer=l_name, driver="GPKG", engine="pyogrio")
            
        if os.path.exists(gpkg_path):
            os.remove(gpkg_path)
            
        os.rename(temp_path, gpkg_path)
        print(" ✓ 完了 (平均標高を NULL に設定)")
    except Exception as e:
        print(f" エラー: {e}")

def main():
    print("=== 図郭境界レイヤー '平均標高' の全値 NULL 設定処理 ===")
    
    base_dir = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    gpkg_dir = os.path.join(base_dir, "gpkg_by_zukaku")
    
    # 1. gpkg_by_zukaku フォルダ内の全 gpkg
    if os.path.exists(gpkg_dir):
        files = [os.path.join(gpkg_dir, f) for f in os.listdir(gpkg_dir) if f.endswith(".gpkg")]
        for f_path in files:
            set_null_average_elevation(f_path)
            
    # 2. メイン GeoPackage
    main_gpkg = os.path.join(base_dir, "ishikawa_forest_mesh_2500.gpkg")
    if os.path.exists(main_gpkg):
        set_null_average_elevation(main_gpkg)
        
    print("\nすべての GeoPackage ファイルの '平均標高' 属性の NULL 化が完了しました。")

if __name__ == "__main__":
    main()
