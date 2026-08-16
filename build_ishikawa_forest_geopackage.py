import os
import sys
import shutil
import tempfile
import py7zr
import geopandas as gpd
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("=== 石川県 1/2,500 図郭限定 森林資源メッシュ GeoPackage 作成処理 ===")
    
    zukaku_geojson = "ishikawa_zukaku_2500.geojson"
    downloads_dir = "downloads"
    output_gpkg = "ishikawa_forest_mesh_2500.gpkg"
    
    if not os.path.exists(zukaku_geojson):
        print(f"エラー: 図郭ファイル '{zukaku_geojson}' が見つかりません。")
        return

    # 1. 石川県 1/2,500 図郭ポリゴンの読み込みと CRS 変換
    print("1. 石川県 1/2,500 図郭ポリゴンデータの読み込み中...")
    gdf_zukaku = gpd.read_file(zukaku_geojson, engine="pyogrio")
    
    # 属性名を 'zukaku_code' に明確化
    if "code" in gdf_zukaku.columns:
        gdf_zukaku = gdf_zukaku.rename(columns={"code": "zukaku_code"})
    gdf_zukaku = gdf_zukaku[["zukaku_code", "geometry"]]
    
    # 平面直角座標系第7系 (EPSG:6675) へ変換
    print(" - 座標系を JGD2011 平面直角座標系第7系 (EPSG:6675) へ変換中...")
    gdf_zukaku_6675 = gdf_zukaku.to_crs(epsg=6675)
    print(f" - 対象図郭数: {len(gdf_zukaku_6675)} 区画")

    # 2. 35 件の .7z アーカイブの処理
    z_files = [f for f in os.listdir(downloads_dir) if f.endswith(".7z")]
    print(f"\n2. 全 {len(z_files)} 件の .7z アーカイブの解凍・図郭抽出処理開始...")
    
    extracted_gdfs = []
    total_raw_features = 0
    total_extracted_features = 0
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for idx, z_file in enumerate(z_files, start=1):
            z_path = os.path.join(downloads_dir, z_file)
            print(f"[{idx}/{len(z_files)}] 処理中: {z_file} ...", end="", flush=True)
            
            # 各7zごとにクリーンな一時ディレクトリへ解凍
            sub_temp = os.path.join(temp_dir, f"sub_{idx}")
            os.makedirs(sub_temp, exist_ok=True)
            
            try:
                with py7zr.SevenZipFile(z_path, mode='r') as z:
                    z.extractall(path=sub_temp)
                
                # 解凍された .gpkg ファイルの探索
                gpkg_path = None
                for root, dirs, files in os.walk(sub_temp):
                    for fn in files:
                        if fn.endswith(".gpkg"):
                            gpkg_path = os.path.join(root, fn)
                            break
                    if gpkg_path:
                        break
                        
                if not gpkg_path:
                    print(" GPKGファイルが見つかりません (スキップ)")
                    continue

                # 森林メッシュデータの読み込み (EPSG:6675)
                gdf_mesh = gpd.read_file(gpkg_path, engine="pyogrio", layer=0)
                raw_count = len(gdf_mesh)
                total_raw_features += raw_count
                
                if raw_count == 0:
                    print(" 0件 (スキップ)")
                    continue
                
                # 空間結合 (Spatial Join: intersects)
                # 森林メッシュデータに交差する図郭コード (zukaku_code) を付与
                gdf_joined = gpd.sjoin(gdf_mesh, gdf_zukaku_6675, how="inner", predicate="intersects")
                
                # 重複インデックスの整理 (index_right を削除)
                if "index_right" in gdf_joined.columns:
                    gdf_joined = gdf_joined.drop(columns=["index_right"])
                    
                extracted_count = len(gdf_joined)
                total_extracted_features += extracted_count
                
                print(f" 元データ: {raw_count} 件 -> 抽出: {extracted_count} 件")
                
                if extracted_count > 0:
                    extracted_gdfs.append(gdf_joined)
                    
            except Exception as e:
                print(f" エラー発生 ({e})")

    # 3. 抽出結果の結合と GeoPackage 保存
    print(f"\n3. 抽出結果の結合と GeoPackage への保存処理...")
    if not extracted_gdfs:
        print("エラー: 抽出されたデータがありません。")
        return
        
    print(f" - 全アーカイブ合計元データ数: {total_raw_features} 件")
    print(f" - 図郭に含まれる総メッシュ数: {total_extracted_features} 件")
    
    gdf_final = pd.concat(extracted_gdfs, ignore_index=True)
    
    # メッシュコード重複排除（必要な場合）
    # 同一20mメッシュが複数図郭の境界に跨がる場合は図郭コード付きで保持
    print(f" - GeoPackage ファイルへ書き出し中: '{output_gpkg}' ...")
    
    # 既存の出力ファイルがあれば削除
    if os.path.exists(output_gpkg):
        os.remove(output_gpkg)
        
    # レイヤー1: 1/2,500図郭切り出し後の20m森林資源メッシュデータ
    gdf_final.to_file(output_gpkg, layer="ishikawa_forest_mesh_2500", driver="GPKG", engine="pyogrio")
    
    # レイヤー2: 1/2,500図郭ポリゴン境界データ (参照用)
    gdf_zukaku_6675.to_file(output_gpkg, layer="ishikawa_zukaku_2500_boundary", driver="GPKG", engine="pyogrio")
    
    file_size_mb = os.path.getsize(output_gpkg) / (1024 * 1024)
    print(f"\n✓ 処理完了!")
    print(f" - 出力 GeoPackage: {output_gpkg}")
    print(f" - レイヤー 1: 'ishikawa_forest_mesh_2500' ({len(gdf_final)} メッシュ)")
    print(f" - レイヤー 2: 'ishikawa_zukaku_2500_boundary' ({len(gdf_zukaku_6675)} 区画)")
    print(f" - ファイルサイズ: {file_size_mb:.2f} MB")

if __name__ == "__main__":
    main()
