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

    print("=== 1/2,500 図郭別 林種7分類の面積 (ha) 付与実行 ===")

    # 1. 20m メッシュ全件から zukaku_code と 林種 を集計
    gpkgs = [os.path.join(g_dir, f) for f in os.listdir(g_dir) if f.startswith("ishikawa_fr_mesh_20_") and f.endswith(".gpkg")]
    
    records = []
    print("1. メッシュデータから属性を集計中...")
    for p in gpkgs:
        try:
            df = pyogrio.read_dataframe(p, layer="ishikawa_fr_mesh_20", columns=["zukaku_code", "林種"])
            df["林種"] = df["林種"].fillna("無林木地")
            records.append(df)
        except Exception as e:
            print(f" Error {os.path.basename(p)}: {e}")

    df_all_mesh = pd.concat(records, ignore_index=True)

    # 2. メッシュ数 * 0.04 ha (ヘクタール) の算出
    ct = pd.crosstab(df_all_mesh["zukaku_code"], df_all_mesh["林種"])
    for cat in categories:
        if cat not in ct.columns:
            ct[cat] = 0

    area_df = (ct[categories] * 0.04).round(3).reset_index()

    # 3. 1/2,500 図郭境界ポリゴンデータへのマージ
    gdf_zukaku = gpd.read_file(zukaku_geojson, engine="pyogrio")
    if "code" in gdf_zukaku.columns:
        gdf_zukaku = gdf_zukaku.rename(columns={"code": "zukaku_code"})
    gdf_zukaku_6675 = gdf_zukaku[["zukaku_code", "geometry"]].to_crs(epsg=6675)

    gdf_boundary_merged = gdf_zukaku_6675.merge(area_df, on="zukaku_code", how="left")
    for cat in categories:
        gdf_boundary_merged[cat] = gdf_boundary_merged[cat].fillna(0.000)

    # 4. マスター GeoPackage の完全置換
    print("4. マスター GeoPackage (ishikawa_zukaku_2500_boundary_all.gpkg) へ上書き保存中...")
    tmp_master = master_boundary_gpkg + ".tmp_master.gpkg"
    if os.path.exists(tmp_master):
        os.remove(tmp_master)
    gdf_boundary_merged.to_file(tmp_master, layer="ishikawa_zukaku_2500_boundary", driver="GPKG", engine="pyogrio")
    
    if os.path.exists(master_boundary_gpkg):
        os.remove(master_boundary_gpkg)
    os.rename(tmp_master, master_boundary_gpkg)
    print(" ✓ マスター GeoPackage 保存完了!")

    # 5. 各地区別 GeoPackage にも同調保存
    print("5. 各地区別 GeoPackage に図郭境界レイヤー (7属性付与済み) を追加同調中...")
    for p in gpkgs:
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
            print(f" ✓ {os.path.basename(p)} 同調完了")
        except Exception as e:
            print(f" Error {os.path.basename(p)}: {e}")

    print("\n✓ すべての処理が完了しました。")

if __name__ == "__main__":
    main()
