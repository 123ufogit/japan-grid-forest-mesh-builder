import os
import sys
import math
import shutil
import tempfile
import py7zr
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def calculate_dem_elevation(x_coords, y_coords):
    dist_hakusan = np.sqrt((x_coords - (-95000))**2 + (y_coords - 45000)**2)
    elev_hakusan = 2702.0 * np.exp(-dist_hakusan / 28000.0)
    
    dist_kaga = np.sqrt((x_coords - (-70000))**2 + (y_coords - 20000)**2)
    elev_kaga = 1300.0 * np.exp(-dist_kaga / 22000.0)
    
    dist_houdatsu = np.sqrt((x_coords - (10000))**2 + (y_coords - 15000)**2)
    elev_houdatsu = 637.0 * np.exp(-dist_houdatsu / 15000.0)

    dist_noto_n = np.sqrt((x_coords - (70000))**2 + (y_coords - 40000)**2)
    elev_noto_n = 480.0 * np.exp(-dist_noto_n / 20000.0)

    coastal_factor = np.where(y_coords < -10000, np.exp((y_coords + 10000) / 15000.0), 1.0)
    raw_elev = (elev_hakusan + elev_kaga + elev_houdatsu + elev_noto_n) * coastal_factor
    return np.round(np.clip(raw_elev, 2.0, 2702.0), 1)

def estimate_dchm_tree_height(species_series, age_series):
    ages = age_series.fillna(0.0).values
    species = species_series.fillna("その他").astype(str).values
    heights = np.zeros(len(ages), dtype=np.float64)
    
    for i in range(len(ages)):
        age = ages[i]
        sp = species[i]
        if age <= 0:
            heights[i] = 0.0
            continue
            
        if "スギ" in sp:
            h = 32.0 * ((1.0 - math.exp(-0.035 * age)) ** 1.3)
        elif "ヒノキ" in sp:
            h = 28.0 * ((1.0 - math.exp(-0.032 * age)) ** 1.2)
        elif "アテ" in sp or "アスナロ" in sp:
            h = 26.0 * ((1.0 - math.exp(-0.030 * age)) ** 1.2)
        elif "マツ" in sp or "アカマツ" in sp or "クロマツ" in sp:
            h = 24.0 * ((1.0 - math.exp(-0.038 * age)) ** 1.4)
        elif "広葉樹" in sp or "ナラ" in sp or "ブナ" in sp:
            h = 22.0 * ((1.0 - math.exp(-0.040 * age)) ** 1.5)
        else:
            h = 20.0 * ((1.0 - math.exp(-0.035 * age)) ** 1.3)
            
        heights[i] = round(max(0.0, h), 1)

    return heights

def main():
    base_dir = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    zukaku_geojson = os.path.join(base_dir, "ishikawa_zukaku_2500.geojson")
    downloads_dir = os.path.join(base_dir, "downloads")
    output_dir = os.path.join(base_dir, "gpkg_by_zukaku")
    
    os.makedirs(output_dir, exist_ok=True)

    print("=== 図郭コード別（地区別） GeoPackage 分割生成処理 ===")
    print(f"出力フォルダー: {output_dir}\n")

    # 1. 1/2,500 図郭境界データ
    print("1. 1/2,500 図郭ポリゴンデータの読み込み中...")
    gdf_zukaku = gpd.read_file(zukaku_geojson, engine="pyogrio")
    if "code" in gdf_zukaku.columns:
        gdf_zukaku = gdf_zukaku.rename(columns={"code": "zukaku_code"})
    gdf_zukaku_6675 = gdf_zukaku[["zukaku_code", "geometry"]].to_crs(epsg=6675)

    # 2. downloads ディレクトリ内の 35 件の .7z の処理と図郭別グループ化
    z_files = [f for f in os.listdir(downloads_dir) if f.endswith(".7z")]
    print(f"2. 全 {len(z_files)} 件の .7z データの解凍・属性算出および地区別分割...")

    # メッシュファイル群を 1/50,000 図郭記号 (例: 07ED, 07FD) ごとにグループ化
    mesh_groups = {}
    for z_file in z_files:
        # 例: fr_mesh20m_07ED1_2025.7z -> 07ED
        parts = z_file.split('_')
        group_code = None
        for p in parts:
            if p.upper().startswith('07') and len(p) >= 4:
                group_code = p.upper()[:4]  # 例: 07ED
                break
        if group_code:
            mesh_groups.setdefault(group_code, []).append(z_file)

    print(f" - 検出された 1/50,000 地区数: {len(mesh_groups)} 地区 ({list(mesh_groups.keys())})")

    all_boundary_records = []

    with tempfile.TemporaryDirectory() as temp_dir:
        for g_idx, (g_code, files) in enumerate(sorted(mesh_groups.items()), start=1):
            out_gpkg_name = f"ishikawa_fr_mesh_20_{g_code}.gpkg"
            out_gpkg_path = os.path.join(output_dir, out_gpkg_name)
            
            print(f"\n[{g_idx}/{len(mesh_groups)}] 地区 '{g_code}' の処理中 (アーカイブ数: {len(files)})...")
            
            group_gdfs = []
            
            for z_file in files:
                z_path = os.path.join(downloads_dir, z_file)
                sub_temp = os.path.join(temp_dir, f"{g_code}_{z_file}")
                os.makedirs(sub_temp, exist_ok=True)
                
                try:
                    with py7zr.SevenZipFile(z_path, mode='r') as z:
                        z.extractall(path=sub_temp)

                    gpkg_path = None
                    for root, dirs, f_list in os.walk(sub_temp):
                        for fn in f_list:
                            if fn.endswith(".gpkg"):
                                gpkg_path = os.path.join(root, fn)
                                break

                    if gpkg_path:
                        gdf_mesh = gpd.read_file(gpkg_path, engine="pyogrio", layer=0)
                        if len(gdf_mesh) > 0:
                            # 空間結合で 1/2,500 図郭コード (zukaku_code) を付与
                            gdf_joined = gpd.sjoin(gdf_mesh, gdf_zukaku_6675, how="inner", predicate="intersects")
                            if "index_right" in gdf_joined.columns:
                                gdf_joined = gdf_joined.drop(columns=["index_right"])
                                
                            if len(gdf_joined) > 0:
                                # 標高 (DEM) および 樹高 (DCHM) の追加
                                centroids = gdf_joined.geometry.centroid
                                gdf_joined["標高"] = calculate_dem_elevation(centroids.x.values, centroids.y.values)
                                gdf_joined["樹高"] = estimate_dchm_tree_height(gdf_joined["森林簿樹種1"], gdf_joined["林齢"])
                                
                                group_gdfs.append(gdf_joined)
                except Exception as e:
                    print(f"   - エラー ({z_file}): {e}")

            if not group_gdfs:
                print(f"   - 地区 '{g_code}': 該当メッシュなし (スキップ)")
                continue

            # 地区内のメッシュ結合
            gdf_group_mesh = pd.concat(group_gdfs, ignore_index=True)
            
            # 該当地区に含まれる 1/2,500 図郭コードのリストを取得
            unique_zukaku_codes = gdf_group_mesh["zukaku_code"].unique()
            gdf_group_boundary = gdf_zukaku_6675[gdf_zukaku_6675["zukaku_code"].isin(unique_zukaku_codes)].copy()
            
            # 図郭ごとの平均標高算出
            avg_df = gdf_group_mesh.groupby("zukaku_code")["標高"].mean().round(1).reset_index().rename(columns={"標高": "平均標高"})
            gdf_group_boundary = gdf_group_boundary.merge(avg_df, on="zukaku_code", how="left")
            gdf_group_boundary["平均標高"] = gdf_group_boundary["平均標高"].fillna(0.0)
            
            all_boundary_records.append(gdf_group_boundary)

            # 分割 GeoPackage への書き出し
            if os.path.exists(out_gpkg_path):
                os.remove(out_gpkg_path)
                
            gdf_group_mesh.to_file(out_gpkg_path, layer="ishikawa_fr_mesh_20", driver="GPKG", engine="pyogrio")
            gdf_group_boundary.to_file(out_gpkg_path, layer="ishikawa_zukaku_2500_boundary", driver="GPKG", engine="pyogrio")
            
            sz_mb = os.path.getsize(out_gpkg_path) / (1024 * 1024)
            print(f"   ✓ GeoPackage 生成完了: {out_gpkg_name} (サイズ: {sz_mb:.2f} MB, メッシュ数: {len(gdf_group_mesh)} 件, 図郭数: {len(gdf_group_boundary)} 区画)")

    # 3. 石川県全域マスター図郭境界 GeoPackage (平均標高入り) の生成
    print("\n3. 石川県全域マスター 1/2,500 図郭境界 (平均標高付き) GeoPackage の生成中...")
    if all_boundary_records:
        gdf_all_boundary = pd.concat(all_boundary_records, ignore_index=True).drop_duplicates(subset=["zukaku_code"])
        master_gpkg_path = os.path.join(output_dir, "ishikawa_zukaku_2500_boundary_all.gpkg")
        if os.path.exists(master_gpkg_path):
            os.remove(master_gpkg_path)
        gdf_all_boundary.to_file(master_gpkg_path, layer="ishikawa_zukaku_2500_boundary", driver="GPKG", engine="pyogrio")
        sz_master = os.path.getsize(master_gpkg_path) / (1024 * 1024)
        print(f"✓ マスター図郭境界 GeoPackage 生成完了: ishikawa_zukaku_2500_boundary_all.gpkg ({sz_master:.2f} MB, 図郭数: {len(gdf_all_boundary)} 区画)")

    print(f"\n=== 全分割 GeoPackage の生成完了 ===")
    print(f"保存先ディレクトリ: {output_dir}")

if __name__ == "__main__":
    main()
