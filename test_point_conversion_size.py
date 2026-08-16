import os
import sys
import tempfile
import geopandas as gpd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def main():
    g_dir = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson\gpkg_by_zukaku"
    sample_gpkg = os.path.join(g_dir, "ishikawa_fr_mesh_20_07ED.gpkg")

    if not os.path.exists(sample_gpkg):
        print("サンプルファイルが見つかりません")
        return

    orig_sz_mb = os.path.getsize(sample_gpkg) / (1024 * 1024)
    print(f"=== 幾何構造変換 (Polygon -> Point) サイズ比較検証 ===")
    print(f"検証対象ファイル: {os.path.basename(sample_gpkg)}")
    print(f"元のPolygon GeoPackage サイズ: {orig_sz_mb:.2f} MB")

    # 1. 読み込み
    print("\n1. メッシュデータ読み込み中...")
    gdf = gpd.read_file(sample_gpkg, engine="pyogrio")
    total_features = len(gdf)
    print(f" - 総フィーチャ数: {total_features} 件")

    # 2. Polygon -> Point (Centroid) 変換
    print("\n2. ポリゴンをメッシュ中心点 (Centroid Point) に変換中...")
    gdf_point = gdf.copy()
    gdf_point.geometry = gdf_point.geometry.centroid

    # 3. テスト保存
    with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as tmp:
        tmp_path = tmp.name

    gdf_point.to_file(tmp_path, layer="ishikawa_fr_mesh_20_point", driver="GPKG", engine="pyogrio")
    
    new_sz_mb = os.path.getsize(tmp_path) / (1024 * 1024)
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    reduction_mb = orig_sz_mb - new_sz_mb
    reduction_pct = (reduction_mb / orig_sz_mb) * 100.0

    print(f"\n=== 実測検証結果 ===")
    print(f" - 変換前 (Polygon): {orig_sz_mb:.2f} MB")
    print(f" - 変換後 (Point)  : {new_sz_mb:.2f} MB")
    print(f" - サイズ削減量   : -{reduction_mb:.2f} MB (約 {reduction_pct:.1f}% 削減)")
    print(f" - データ容量比較 : 変換後は元の約 {100.0 - reduction_pct:.1f}% の大きさ（約 {orig_sz_mb / new_sz_mb:.1f} 分の 1）になります。")

if __name__ == "__main__":
    main()
