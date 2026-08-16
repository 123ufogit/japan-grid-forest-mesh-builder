import os
import sys
import geopandas as gpd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    g_dir = os.path.join(base, "gpkg_by_zukaku")

    files = [
        os.path.join(g_dir, f)
        for f in os.listdir(g_dir)
        if f.endswith(".gpkg") and f != "ishikawa_zukaku_2500_boundary_all.gpkg"
    ]

    print("=== 地区別 GPKG ファイルから図郭境界レイヤー (ishikawa_zukaku_2500_boundary) の除外処理 ===")

    for f in files:
        if not os.path.exists(f):
            continue
            
        print(f"処理中: {os.path.basename(f)} ...", end="", flush=True)
        try:
            # ishikawa_fr_mesh_20 レイヤーのみを読み込んで新規保存
            gdf_mesh = gpd.read_file(f, layer="ishikawa_fr_mesh_20", engine="pyogrio")
            
            tmp = f + ".mesh_only.gpkg"
            if os.path.exists(tmp):
                os.remove(tmp)

            gdf_mesh.to_file(tmp, layer="ishikawa_fr_mesh_20", driver="GPKG", engine="pyogrio")

            os.remove(f)
            os.rename(tmp, f)
            print(" ✓ レイヤー除外完了 (ishikawa_fr_mesh_20 のみ)")
        except Exception as e:
            print(f" Error: {e}")

    print("\n✓ すべての地区別 GeoPackage ファイルが 'ishikawa_fr_mesh_20' 単一レイヤー構造に更新されました。")

if __name__ == "__main__":
    main()
