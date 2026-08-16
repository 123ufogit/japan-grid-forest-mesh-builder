import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

def main():
    g_dir = r"C:\Users\seafi\Antigravity\ishikawa_grid_geojson\gpkg_by_zukaku"
    files = os.listdir(g_dir)
    
    print("=== 不要な作業用一時ファイルの削除処理 ===")
    
    removed_count = 0
    for f in files:
        # 正規の成果物（例: ishikawa_fr_mesh_20_07XX.gpkg, ishikawa_zukaku_2500_boundary_all.gpkg）以外の二重拡張子や temp_ ファイル
        if f.startswith("temp_") or f.endswith(".clean_fix.gpkg") or f.endswith(".nullified.gpkg") or f.endswith(".clean_drop.gpkg") or f.count(".gpkg") > 1:
            f_path = os.path.join(g_dir, f)
            try:
                os.remove(f_path)
                print(f" - 削除完了: {f}")
                removed_count += 1
            except Exception as e:
                print(f" - 削除失敗 ({f}): {e}")

    print(f"\n✓ 計 {removed_count} 件の不要な一時ファイルをクリーンアップしました。")

if __name__ == "__main__":
    main()
