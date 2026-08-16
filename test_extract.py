import os
import py7zr
import geopandas as gpd

extract_dir = "temp_extracted"
os.makedirs(extract_dir, exist_ok=True)

downloads_dir = "downloads"
files = [f for f in os.listdir(downloads_dir) if f.endswith(".7z")]

sample_file = os.path.join(downloads_dir, files[0])
print(f"解凍テスト: {sample_file}")

with py7zr.SevenZipFile(sample_file, mode='r') as z:
    z.extractall(path=extract_dir)

print("解凍されたファイル一覧:")
extracted_files = []
for root, dirs, f_names in os.walk(extract_dir):
    for fn in f_names:
        full_p = os.path.join(root, fn)
        extracted_files.append(full_p)
        print(" -", full_p)

# 拡張子の確認と GeoDataFrame での試行読み込み
shp_files = [f for f in extracted_files if f.endswith('.shp') or f.endswith('.parquet') or f.endswith('.gpkg') or f.endswith('.geojson')]
if shp_files:
    print(f"\nベクタデータファイルの読み込みテスト: {shp_files[0]}")
    gdf = gpd.read_file(shp_files[0], engine="pyogrio")
    print("CRS:", gdf.crs)
    print("件数:", len(gdf))
    print("カラム一覧:", gdf.columns.tolist())
    print("先頭3件:")
    print(gdf.head(3))
