import os
import sys
import glob
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

def main():
    base = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson"
    g_dir = os.path.join(base, "gpkg_by_zukaku")

    # 一時ファイルの完全清掃
    for pat in ["*.tmp*", "*.final*", "*.strict*", "*.dropped*", "*.clean*", "*.mesh_only*"]:
        for tmp_f in glob.glob(os.path.join(g_dir, pat)):
            try:
                os.remove(tmp_f)
            except Exception:
                pass

    files = [
        os.path.join(g_dir, f)
        for f in os.listdir(g_dir)
        if f.endswith(".gpkg") and f != "ishikawa_zukaku_2500_boundary_all.gpkg"
    ]

    print("=== SQLite 直接操作による図郭境界レイヤー (ishikawa_zukaku_2500_boundary) 削除処理 ===")

    for f in files:
        if not os.path.exists(f):
            continue
        print(f"処理中: {os.path.basename(f)} ...", end="", flush=True)
        try:
            conn = sqlite3.connect(f)
            cur = conn.cursor()

            cur.execute("DROP TABLE IF EXISTS ishikawa_zukaku_2500_boundary;")
            cur.execute("DELETE FROM gpkg_contents WHERE table_name = 'ishikawa_zukaku_2500_boundary';")
            cur.execute("DELETE FROM gpkg_geometry_columns WHERE table_name = 'ishikawa_zukaku_2500_boundary';")

            conn.commit()
            conn.close()
            print(" ✓ レイヤー削除完了")
        except Exception as e:
            print(f" Error: {e}")

    print("\n✓ すべての地区別 GeoPackage ファイルから図郭境界レイヤーが完全除外されました。")

if __name__ == "__main__":
    main()
