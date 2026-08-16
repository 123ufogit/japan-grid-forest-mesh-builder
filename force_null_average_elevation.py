import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

def force_null(path):
    if not os.path.exists(path):
        return
    try:
        layers = [l[0] for l in pyogrio.list_layers(path)]
        if "ishikawa_zukaku_2500_boundary" not in layers:
            return
            
        print(f"Applying NULL to {os.path.basename(path)}...", end="", flush=True)
        gdfs = {}
        for l in layers:
            gdfs[l] = gpd.read_file(path, layer=l, engine="pyogrio")
            
        b_gdf = gdfs["ishikawa_zukaku_2500_boundary"]
        b_gdf["平均標高"] = None
        gdfs["ishikawa_zukaku_2500_boundary"] = b_gdf
        
        tmp = path + ".tmp.gpkg"
        if os.path.exists(tmp):
            os.remove(tmp)
            
        for l_name, gdf in gdfs.items():
            gdf.to_file(tmp, layer=l_name, driver="GPKG", engine="pyogrio")
            
        os.remove(path)
        os.rename(tmp, path)
        print(" ✓ SUCCESS")
    except Exception as e:
        print(f" Error: {e}")

def main():
    base = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    g_dir = os.path.join(base, "gpkg_by_zukaku")

    if os.path.exists(g_dir):
        for f in os.listdir(g_dir):
            if f.endswith(".gpkg"):
                force_null(os.path.join(g_dir, f))
                
    force_null(os.path.join(base, "ishikawa_forest_mesh_2500.gpkg"))

if __name__ == "__main__":
    main()
