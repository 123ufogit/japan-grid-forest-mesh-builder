import os
import sys
import geopandas as gpd
import pandas as pd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def main():
    g_dir = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson\gpkg_by_zukaku"
    gpkgs = [os.path.join(g_dir, f) for f in os.listdir(g_dir) if f.startswith("ishikawa_fr_mesh_20_") and f.endswith(".gpkg")]

    print("=== ishikawa_fr_mesh_20 『林種』種類・分布集計処理 ===")
    print(f"対象 GeoPackage ファイル数: {len(gpkgs)} 件\n")

    forest_type_counts = pd.Series(dtype=int)

    for idx, p in enumerate(gpkgs, start=1):
        print(f"[{idx}/{len(gpkgs)}] 集計中: {os.path.basename(p)} ...", end="", flush=True)
        try:
            # 属性テーブルのみ高速読み込み
            info = pyogrio.read_info(p, layer="ishikawa_fr_mesh_20")
            df = pyogrio.read_dataframe(p, layer="ishikawa_fr_mesh_20", columns=["林種"])
            counts = df["林種"].fillna("（データなし / 無林木地）").value_counts()
            forest_type_counts = forest_type_counts.add(counts, fill_value=0)
            print(" ✓ OK")
        except Exception as e:
            print(f" Error: {e}")

    forest_type_counts = forest_type_counts.astype(int).sort_values(ascending=False)
    total_mesh = forest_type_counts.sum()

    print("\n================ 集計結果 ================")
    print(f"総メッシュ数: {total_mesh:,} 件")
    print(f"『林種』のユニーク種類数: {len(forest_type_counts)} 種類\n")
    print("【林種ごとの内訳】")
    for r_idx, (ftype, cnt) in enumerate(forest_type_counts.items(), start=1):
        pct = (cnt / total_mesh) * 100.0
        print(f" {r_idx:2d}. {ftype:<20}: {cnt:10,} 件 ({pct:5.2f}%)")

if __name__ == "__main__":
    main()
