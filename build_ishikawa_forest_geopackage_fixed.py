import os
import sys
import tempfile
import py7zr
import geopandas as gpd
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base_dir = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    zukaku_geojson = os.path.join(base_dir, "ishikawa_zukaku_2500.geojson")
    downloads_dir = os.path.join(base_dir, "downloads")
    output_gpkg = os.path.join(base_dir, "ishikawa_forest_mesh_2500.gpkg")

    print("=== 石川県 1/2,500 図郭限定 森林資源メッシュ GeoPackage 確実生成 ===")
    print(f"出力ファイルパス: {output_gpkg}")

    # 1. 1/2,500 図郭ポリゴンの読み込みと EPSG:6675 変換
    gdf_zukaku = gpd.read_file(zukaku_geojson, engine="pyogrio")
    if "code" in gdf_zukaku.columns:
        gdf_zukaku = gdf_zukaku.rename(columns={"code": "zukaku_code"})
    gdf_zukaku = gdf_zukaku[["zukaku_code", "geometry"]]
    gdf_zukaku_6675 = gdf_zukaku.to_crs(epsg=6675)

    # 2. 35 件の .7z アーカイブの処理
    z_files = [f for f in os.listdir(downloads_dir) if f.endswith(".7z")]
    extracted_gdfs = []

    with tempfile.TemporaryDirectory() as temp_dir:
        for idx, z_file in enumerate(z_files, start=1):
            z_path = os.path.join(downloads_dir, z_file)
            sub_temp = os.path.join(temp_dir, f"sub_{idx}")
            os.makedirs(sub_temp, exist_ok=True)

            try:
                with py7zr.SevenZipFile(z_path, mode='r') as z:
                    z.extractall(path=sub_temp)

                gpkg_path = None
                for root, dirs, files in os.walk(sub_temp):
                    for fn in files:
                        if fn.endswith(".gpkg"):
                            gpkg_path = os.path.join(root, fn)
                            break

                if gpkg_path:
                    gdf_mesh = gpd.read_file(gpkg_path, engine="pyogrio", layer=0)
                    if len(gdf_mesh) > 0:
                        gdf_joined = gpd.sjoin(gdf_mesh, gdf_zukaku_6675, how="inner", predicate="intersects")
                        if "index_right" in gdf_joined.columns:
                            gdf_joined = gdf_joined.drop(columns=["index_right"])
                        if len(gdf_joined) > 0:
                            extracted_gdfs.append(gdf_joined)
            except Exception as e:
                print(f"Error processing {z_file}: {e}")

    # 3. GeoPackage への一括書き出し
    if extracted_gdfs:
        gdf_final = pd.concat(extracted_gdfs, ignore_index=True)
        if os.path.exists(output_gpkg):
            os.remove(output_gpkg)
            
        print(f"GeoPackage ファイルを絶対パスに保存中: {output_gpkg}")
        gdf_final.to_file(output_gpkg, layer="ishikawa_forest_mesh_2500", driver="GPKG", engine="pyogrio")
        gdf_zukaku_6675.to_file(output_gpkg, layer="ishikawa_zukaku_2500_boundary", driver="GPKG", engine="pyogrio")

        sz_mb = os.path.getsize(output_gpkg) / (1024 * 1024)
        print(f"✓ 保存完了! ファイルサイズ: {sz_mb:.2f} MB")
        print(f" - 総抽出メッシュ数: {len(gdf_final)} 件")
    else:
        print("エラー: 抽出データがありません。")

if __name__ == "__main__":
    main()
