import os
import sys
import geopandas as gpd
import pandas as pd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def main():
    g_dir = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson\gpkg_by_zukaku"
    gpkgs = [os.path.join(g_dir, f) for f in os.listdir(g_dir) if f.startswith("ishikawa_fr_mesh_20_") and f.endswith(".gpkg")]

    tree_counts = pd.Series(dtype=int)

    for p in gpkgs:
        df = pyogrio.read_dataframe(p, layer="ishikawa_fr_mesh_20", columns=["森林簿樹種1"])
        counts = df["森林簿樹種1"].value_counts()
        tree_counts = tree_counts.add(counts, fill_value=0)

    tree_counts = tree_counts.astype(int).sort_values(ascending=False)

    print("=== 森林簿樹種1 内訳 ===")
    print(f"ユニーク樹種数: {len(tree_counts)} 種類")
    for idx, (sp, cnt) in enumerate(tree_counts.items(), start=1):
        print(f" {idx:2d}. {sp:<15}: {cnt:10,} 件")

if __name__ == "__main__":
    main()
