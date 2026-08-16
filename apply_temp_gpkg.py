import os
import sys
import shutil
import pyogrio

sys.stdout.reconfigure(encoding='utf-8')

base_dir = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
gpkg_path = os.path.join(base_dir, "ishikawa_forest_mesh_2500.gpkg")
temp_gpkg = os.path.join(base_dir, "temp_updated.gpkg")

if os.path.exists(temp_gpkg):
    print(f"一時更新ファイルを発見: {temp_gpkg} ({os.path.getsize(temp_gpkg)/(1024*1024):.2f} MB)")
    if os.path.exists(gpkg_path):
        os.remove(gpkg_path)
    shutil.move(temp_gpkg, gpkg_path)
    print(f"✓ 置換成功: {gpkg_path}")

if os.path.exists(gpkg_path):
    print("=== FINAL VERIFICATION ===")
    layers = pyogrio.list_layers(gpkg_path)
    for l in layers:
        print(f" - Layer: {l[0]}, Type: {l[1]}")
        info = pyogrio.read_info(gpkg_path, layer=l[0])
        print(f"   Fields: {list(info['fields'])}")
