import os
import sys
import geopandas as gpd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    g_dir = os.path.join(base, "gpkg_by_zukaku")

    files = [os.path.join(g_dir, f) for f in os.listdir(g_dir) if f.endswith(".gpkg")]
    files.append(os.path.join(base, "ishikawa_forest_mesh_2500.gpkg"))

    print("=== GeoPackage 図郭境界レイヤーの '平均標高' カラムの完全削除・リセット処理 ===")

    for f in files:
        if not os.path.exists(f):
            continue
        try:
            layers = [l[0] for l in pyogrio.list_layers(f)]
            if "ishikawa_zukaku_2500_boundary" not in layers:
                continue

            print(f"処理中: {os.path.basename(f)} ...", end="", flush=True)
            gdfs = {}
            for l in layers:
                gdf = gpd.read_file(f, layer=l, engine="pyogrio")
                if l == "ishikawa_zukaku_2500_boundary" and "平均標高" in gdf.columns:
                    gdf = gdf.drop(columns=["平均標高"])
                gdfs[l] = gdf

            tmp = f + ".clean_drop.gpkg"
            if os.path.exists(tmp):
                os.remove(tmp)

            for l_name, gdf in gdfs.items():
                gdf.to_file(tmp, layer=l_name, driver="GPKG", engine="pyogrio")

            if os.path.exists(f):
                os.remove(f)
            os.rename(tmp, f)
            print(" ✓ 削除完了")
        except Exception as e:
            print(f" Error: {e}")

    print("\n✓ すべての GeoPackage の図郭境界レイヤーから '平均標高' 属性が完全に除去されました。")

if __name__ == "__main__":
    main()
