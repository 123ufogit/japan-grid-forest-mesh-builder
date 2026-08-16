import os
import sys
import geopandas as gpd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def main():
    gpkg_ic = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson\gpkg_by_zukaku\ishikawa_fr_mesh_20_07IC.gpkg"
    tmp_ic = gpkg_ic + ".tmp_clean.gpkg"

    print("=== ishikawa_fr_mesh_20_07IC.gpkg の確実なフィールド削除処理 ===")
    
    layers = [l[0] for l in pyogrio.list_layers(gpkg_ic)]
    gdfs = {}
    for l in layers:
        gdf = gpd.read_file(gpkg_ic, layer=l, engine="pyogrio")
        cols_to_drop = [c for c in ["標高", "樹高", "平均標高"] if c in gdf.columns]
        if cols_to_drop:
            gdf = gdf.drop(columns=cols_to_drop)
        gdfs[l] = gdf

    if os.path.exists(tmp_ic):
        os.remove(tmp_ic)
        
    for l_name, gdf in gdfs.items():
        gdf.to_file(tmp_ic, layer=l_name, driver="GPKG", engine="pyogrio")

    if os.path.exists(gpkg_ic):
        os.remove(gpkg_ic)
    os.rename(tmp_ic, gpkg_ic)
    print("✓ ishikawa_fr_mesh_20_07IC.gpkg のクリーン化完了!")

if __name__ == "__main__":
    main()
