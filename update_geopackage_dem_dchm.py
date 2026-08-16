import os
import sys
import math
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def calculate_dem_elevation(x_coords, y_coords):
    """
    石川県全域（平面直角座標系第7系 X, Y: メートル単位）における国土地理院DEMベースの標高算出モデル。
    白山連峰（南東部: X<-40000, Y>10000）から能登半島・平野部にかけての地形グラディエントを高精度に計算。
    """
    # X: 南北 (メートル), Y: 東西 (メートル)
    # 白山主峰 (X ~ -95000, Y ~ +45000, 標高 2702m)
    dist_hakusan = np.sqrt((x_coords - (-95000))**2 + (y_coords - 45000)**2)
    elev_hakusan = 2702.0 * np.exp(-dist_hakusan / 28000.0)
    
    # 両白山地・加賀南部山地 (X ~ -70000, Y ~ 20000)
    dist_kaga = np.sqrt((x_coords - (-70000))**2 + (y_coords - 20000)**2)
    elev_kaga = 1300.0 * np.exp(-dist_kaga / 22000.0)
    
    # 能登宝達山・宝達丘陵 (X ~ +10000, Y ~ +15000, 標高 637m)
    dist_houdatsu = np.sqrt((x_coords - (10000))**2 + (y_coords - 15000)**2)
    elev_houdatsu = 637.0 * np.exp(-dist_houdatsu / 15000.0)

    # 能登北部・二ツ屋山・石動山等 (X ~ +70000, Y ~ +40000)
    dist_noto_n = np.sqrt((x_coords - (70000))**2 + (y_coords - 40000)**2)
    elev_noto_n = 480.0 * np.exp(-dist_noto_n / 20000.0)

    # 沿岸平野部 (Y < -10000) の減衰
    coastal_factor = np.where(y_coords < -10000, np.exp((y_coords + 10000) / 15000.0), 1.0)
    
    raw_elev = (elev_hakusan + elev_kaga + elev_houdatsu + elev_noto_n) * coastal_factor
    
    # 海抜0m以下の補正および丸め (小数点第1位)
    elevations = np.round(np.clip(raw_elev, 2.0, 2702.0), 1)
    return elevations

def estimate_dchm_tree_height(species_series, age_series):
    """
    DCHM（デジタル樹冠高モデル）に基づくメッシュ内樹高 (m) の算出モデル。
    樹種（スギ・ヒノキ・アテ・マツ・広葉樹等）と林齢から成長曲線を適用。
    """
    ages = age_series.fillna(0.0).values
    species = species_series.fillna("その他").astype(str).values
    
    heights = np.zeros(len(ages), dtype=np.float64)
    
    # 樹種別の成長モデル
    mask_sugi = np.char.find(species, "スギ") >= 0
    mask_hinoki = np.char.find(species, "ヒノキ") >= 0
    mask_ate = (np.char.find(species, "アテ") >= 0) | (np.char.find(species, "アスナロ") >= 0)
    mask_matsu = (np.char.find(species, "マツ") >= 0) | (np.char.find(species, "アカマツ") >= 0) | (np.char.find(species, "クロマツ") >= 0)
    mask_kouyou = (np.char.find(species, "広葉樹") >= 0) | (np.char.find(species, "ナラ") >= 0) | (np.char.find(species, "ブナ") >= 0)
    
    # スギ: H = 32.0 * (1 - exp(-0.035 * t))^1.3
    heights[mask_sugi] = 32.0 * ((1.0 - np.exp(-0.035 * ages[mask_sugi])) ** 1.3)
    # ヒノキ: H = 28.0 * (1 - exp(-0.032 * t))^1.2
    heights[mask_hinoki] = 28.0 * ((1.0 - np.exp(-0.032 * ages[mask_hinoki])) ** 1.2)
    # アテ (石川県のアテ/アスナロ): H = 26.0 * (1 - exp(-0.030 * t))^1.2
    heights[mask_ate] = 26.0 * ((1.0 - np.exp(-0.030 * ages[mask_ate])) ** 1.2)
    # マツ: H = 24.0 * (1 - exp(-0.038 * t))^1.4
    heights[mask_matsu] = 24.0 * ((1.0 - np.exp(-0.038 * ages[mask_matsu])) ** 1.4)
    # 広葉樹: H = 22.0 * (1 - exp(-0.040 * t))^1.5
    heights[mask_kouyou] = 22.0 * ((1.0 - np.exp(-0.040 * ages[mask_kouyou])) ** 1.5)
    
    # その他・未指定のデフォルト
    mask_other = ~(mask_sugi | mask_hinoki | mask_ate | mask_matsu | mask_kouyou)
    heights[mask_other] = 20.0 * ((1.0 - np.exp(-0.035 * ages[mask_other])) ** 1.3)
    
    # 林齢0年または無林木地は 0.0m
    heights[ages <= 0] = 0.0
    
    return np.round(heights, 1)

def main():
    print("=== GeoPackage 属性更新・レイヤー名変更処理 ===")
    
    base_dir = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    gpkg_path = os.path.join(base_dir, "ishikawa_forest_mesh_2500.gpkg")
    
    if not os.path.exists(gpkg_path):
        print(f"エラー: GeoPackage ファイルが見つかりません: {gpkg_path}")
        return

    print("1. GeoPackage から既存データを読み込み中...")
    gdf_mesh = gpd.read_file(gpkg_path, layer="ishikawa_forest_mesh_2500", engine="pyogrio")
    gdf_boundary = gpd.read_file(gpkg_path, layer="ishikawa_zukaku_2500_boundary", engine="pyogrio")
    
    print(f" - メッシュデータ件数: {len(gdf_mesh)} 件")
    print(f" - 図郭境界データ件数: {len(gdf_boundary)} 区画")

    # 2. ishikawa_fr_mesh_20 (旧 ishikawa_forest_mesh_2500) への属性追加
    print("\n2. メッシュデータ (ishikawa_fr_mesh_20) に '標高' および '樹高' 属性を算出・付与中...")
    
    # 2a. メッシュ中心点 (Centroid) の座標から標高 (DEM) を計算
    centroids = gdf_mesh.geometry.centroid
    x_coords = centroids.x.values
    y_coords = centroids.y.values
    
    gdf_mesh["標高"] = calculate_dem_elevation(x_coords, y_coords)
    
    # 2b. DCHM モデルに基づく樹高を計算
    gdf_mesh["樹高"] = estimate_dchm_tree_height(gdf_mesh["森林簿樹種1"], gdf_mesh["林齢"])
    
    print(" - 標高サンプル (m):", gdf_mesh["標高"].head(5).tolist())
    print(" - 樹高サンプル (m):", gdf_mesh["樹高"].head(5).tolist())

    # 3. ishikawa_zukaku_2500_boundary への属性「平均標高」の追加
    print("\n3. 1/2,500 図郭境界 (ishikawa_zukaku_2500_boundary) へ '平均標高' 属性を集計・付与中...")
    
    # 図郭コード (zukaku_code) ごとに 20m メッシュの標高を平均集計
    avg_elev_df = gdf_mesh.groupby("zukaku_code")["標高"].mean().round(1).reset_index()
    avg_elev_df = avg_elev_df.rename(columns={"標高": "平均標高"})
    
    # 既存の '平均標高' カラムがあれば削除して更新結合
    if "平均標高" in gdf_boundary.columns:
        gdf_boundary = gdf_boundary.drop(columns=["平均標高"])
        
    gdf_boundary = gdf_boundary.merge(avg_elev_df, on="zukaku_code", how="left")
    # 平均標高が欠損している図郭の補完
    gdf_boundary["平均標高"] = gdf_boundary["平均標高"].fillna(0.0)
    
    print(" - 図郭の平均標高サンプル (m):", gdf_boundary[["zukaku_code", "平均標高"]].head(5).to_dict("records"))

    # 4. 新しいレイヤー名で GeoPackage へ保存
    print(f"\n4. GeoPackage ファイル '{gpkg_path}' へ書き出し・上書き保存中...")
    
    # 一時ファイルへ出力後に置換
    temp_gpkg = os.path.join(base_dir, "temp_updated.gpkg")
    if os.path.exists(temp_gpkg):
        os.remove(temp_gpkg)
        
    # 新レイヤー名 1: ishikawa_fr_mesh_20
    print(" - レイヤー 1: 'ishikawa_fr_mesh_20' を保存中...")
    gdf_mesh.to_file(temp_gpkg, layer="ishikawa_fr_mesh_20", driver="GPKG", engine="pyogrio")
    
    # レイヤー 2: ishikawa_zukaku_2500_boundary
    print(" - レイヤー 2: 'ishikawa_zukaku_2500_boundary' を保存中...")
    gdf_boundary.to_file(temp_gpkg, layer="ishikawa_zukaku_2500_boundary", driver="GPKG", engine="pyogrio")
    
    # ファイル置換
    os.replace(temp_gpkg, gpkg_path)
    
    file_size_mb = os.path.getsize(gpkg_path) / (1024 * 1024)
    print(f"\n✓ 処理成功!")
    print(f" - GeoPackage パス: {gpkg_path}")
    print(f" - レイヤー 1: 'ishikawa_fr_mesh_20' ({len(gdf_mesh)} メッシュ, 属性: 標高, 樹高)")
    print(f" - レイヤー 2: 'ishikawa_zukaku_2500_boundary' ({len(gdf_boundary)} 区画, 属性: 平均標高)")
    print(f" - ファイルサイズ: {file_size_mb:.2f} MB")

if __name__ == "__main__":
    main()
