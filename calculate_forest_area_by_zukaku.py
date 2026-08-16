import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base_dir = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    g_dir = os.path.join(base_dir, "gpkg_by_zukaku")
    zukaku_geojson = os.path.join(base_dir, "ishikawa_zukaku_2500.geojson")
    master_boundary_gpkg = os.path.join(g_dir, "ishikawa_zukaku_2500_boundary_all.gpkg")

    categories = ["天然林", "人工林", "その他", "未立木地", "竹林", "伐採跡地", "無林木地"]

    print("=== 1/2,500 図郭別 林種7分類の面積 (ha) 集計処理 ===")

    # 1. 地区別 GeoPackage から メッシュの zukaku_code と 林種 を全件読み込み
    gpkgs = [os.path.join(g_dir, f) for f in os.listdir(g_dir) if f.startswith("ishikawa_fr_mesh_20_") and f.endswith(".gpkg")]
    
    records = []
    print(f"1. 全 {len(gpkgs)} 地区の 20m メッシュデータから属性を集計中...")
    for idx, p in enumerate(gpkgs, start=1):
        print(f" - [{idx}/{len(gpkgs)}] 読み込み中: {os.path.basename(p)} ...", end="", flush=True)
        try:
            df = pyogrio.read_dataframe(p, layer="ishikawa_fr_mesh_20", columns=["zukaku_code", "林種"])
            df["林種"] = df["林種"].fillna("無林木地")
            records.append(df)
            print(" ✓ OK")
        except Exception as e:
            print(f" Error: {e}")

    df_all_mesh = pd.concat(records, ignore_index=True)
    print(f"   総抽出メッシュ数: {len(df_all_mesh):,} 件")

    # 2. zukaku_code × 林種 ごとのメッシュ個数をクロス集計
    print("\n2. 図郭コードごとの林種メッシュ個数および面積 (ha) の算出中...")
    ct = pd.crosstab(df_all_mesh["zukaku_code"], df_all_mesh["林種"])

    # 不足カテゴリの補元
    for cat in categories:
        if cat not in ct.columns:
            ct[cat] = 0

    # 20m メッシュ 1個 = 400 m2 = 0.04 ha
    # 面積 (ha) = 個数 * 0.04 (小数点第3位に丸め)
    area_df = (ct[categories] * 0.04).round(3).reset_index()

    print("   集計完了! 図郭数:", len(area_df))
    print("   サンプル集計データ (ha):")
    print(area_df.head(3).to_string())

    # 3. 1/2,500 図郭ポリゴンデータへのマージ結合
    print("\n3. 1/2,500 図郭境界ポリゴンデータへ 7 種類の面積属性を付与中...")
    gdf_zukaku = gpd.read_file(zukaku_geojson, engine="pyogrio")
    if "code" in gdf_zukaku.columns:
        gdf_zukaku = gdf_zukaku.rename(columns={"code": "zukaku_code"})
    gdf_zukaku_6675 = gdf_zukaku[["zukaku_code", "geometry"]].to_crs(epsg=6675)

    gdf_boundary_merged = gdf_zukaku_6675.merge(area_df, on="zukaku_code", how="left")
    for cat in categories:
        gdf_boundary_merged[cat] = gdf_boundary_merged[cat].fillna(0.000)

    # 4. マスター図郭境界 GeoPackage (ishikawa_zukaku_2500_boundary_all.gpkg) へ書き出し
    print(f"\n4. マスター GeoPackage '{os.path.basename(master_boundary_gpkg)}' の更新保存中...")
    if os.path.exists(master_boundary_gpkg):
        os.remove(master_boundary_gpkg)
        
    gdf_boundary_merged.to_file(master_boundary_gpkg, layer="ishikawa_zukaku_2500_boundary", driver="GPKG", engine="pyogrio")
    print(" ✓ マスター GeoPackage 更新完了!")

    # 5. 各地区別 GeoPackage にも最新の図郭境界レイヤーを同調保存
    print("\n5. 各地区別 GeoPackage へ図郭境界レイヤー (7属性付与済み) を追加・同調中...")
    for idx, p in enumerate(gpkgs, start=1):
        print(f" - [{idx}/{len(gpkgs)}] 同調中: {os.path.basename(p)} ...", end="", flush=True)
        try:
            gdf_m = gpd.read_file(p, layer="ishikawa_fr_mesh_20", engine="pyogrio")
            codes = gdf_m["zukaku_code"].unique()
            sub_b = gdf_boundary_merged[gdf_boundary_merged["zukaku_code"].isin(codes)].copy()

            tmp_p = p + ".area_tmp.gpkg"
            if os.path.exists(tmp_p):
                os.remove(tmp_p)

            gdf_m.to_file(tmp_p, layer="ishikawa_fr_mesh_20", driver="GPKG", engine="pyogrio")
            sub_b.to_file(tmp_p, layer="ishikawa_zukaku_2500_boundary", driver="GPKG", engine="pyogrio")

            if os.path.exists(p):
                os.remove(p)
            os.rename(tmp_p, p)
            print(" ✓ OK")
        except Exception as e:
            print(f" Error: {e}")

    print("\n✓ すべての GeoPackage の図郭境界レイヤーへの 7 種類林種面積 (ha) 属性の付与が完了しました。")

if __name__ == "__main__":
    main()
