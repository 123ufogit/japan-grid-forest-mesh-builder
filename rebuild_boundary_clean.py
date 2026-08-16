import os
import sys
import geopandas as gpd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    zukaku_geojson = os.path.join(base, "ishikawa_zukaku_2500.geojson")
    g_dir = os.path.join(base, "gpkg_by_zukaku")

    print("=== 図郭境界レイヤーの完全クリーン再構築処理 ===")

    gdf_z = gpd.read_file(zukaku_geojson, engine="pyogrio").rename(columns={"code": "zukaku_code"})[["zukaku_code", "geometry"]]
    gdf_z_6675 = gdf_z.to_crs(epsg=6675)

    for f in os.listdir(g_dir):
        if f.endswith(".gpkg") and f != "ishikawa_zukaku_2500_boundary_all.gpkg":
            p = os.path.join(g_dir, f)
            print(f"処理中: {f} ...", end="", flush=True)
            try:
                gdf_m = gpd.read_file(p, layer="ishikawa_fr_mesh_20", engine="pyogrio")
                codes = gdf_m["zukaku_code"].unique()
                sub_b = gdf_z_6675[gdf_z_6675["zukaku_code"].isin(codes)].copy()

                tmp = p + ".clean.gpkg"
                if os.path.exists(tmp):
                    os.remove(tmp)

                gdf_m.to_file(tmp, layer="ishikawa_fr_mesh_20", driver="GPKG", engine="pyogrio")
                sub_b.to_file(tmp, layer="ishikawa_zukaku_2500_boundary", driver="GPKG", engine="pyogrio")

                if os.path.exists(p):
                    os.remove(p)
                os.rename(tmp, p)
                print(" ✓ クリーン書き出し完了")
            except Exception as e:
                print(f" Error: {e}")

    # マスターファイル
    all_p = os.path.join(g_dir, "ishikawa_zukaku_2500_boundary_all.gpkg")
    print("処理中: ishikawa_zukaku_2500_boundary_all.gpkg ...", end="", flush=True)
    if os.path.exists(all_p):
        os.remove(all_p)
    gdf_z_6675.to_file(all_p, layer="ishikawa_zukaku_2500_boundary", driver="GPKG", engine="pyogrio")
    print(" ✓ クリーン書き出し完了")

    print("\n✓ すべての GeoPackage の図郭境界レイヤーが '平均標高' カラム非保持のクリーン状態に再構築されました。")

if __name__ == "__main__":
    main()
