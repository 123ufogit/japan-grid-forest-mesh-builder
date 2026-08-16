# -*- coding: utf-8 -*-
"""
全国都道府県 & 市区町村対応 1/2,500 公共測量図郭 & 20m 森林資源メッシュ構築パイプライン
(メモリ保護・OOMクラッシュ防止・自動ガベージコレクション対応版)
"""

import os
import sys
import gc
import shutil
import tempfile
import zipfile
import requests
import py7zr
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio
from shapely.geometry import Polygon
from japan_basic_section.grid import Grid

from app.core.prefectures import get_pref_info, to_ascii_identifier
from app.core.romaji import kanji_to_romaji

categories = ["天然林", "人工林", "その他", "未立木地", "竹林", "伐採跡地", "無林木地"]

class TaskCanceledException(Exception):
    pass

class PipelineRunner:
    def __init__(self, pref_key: str, output_base_dir: str, city_name: str = None, auto_cleanup: bool = True, log_callback=None, cancel_check=None):
        self.pref_info = get_pref_info(pref_key)
        if not self.pref_info:
            raise ValueError(f"指定された都道府県情報が見つかりません: {pref_key}")

        self.pref_code = self.pref_info["code"]
        self.pref_name = self.pref_info["name"]
        self.pref_romaji = self.pref_info.get("romaji", "pref")
        self.system_no = self.pref_info["system"]
        self.epsg = self.pref_info["epsg"]
        self.mesh_key = self.pref_info["mesh_key"]
        self.city_name = city_name if (city_name and city_name != "ALL") else None
        self.auto_cleanup = auto_cleanup

        self.output_base_dir = output_base_dir
        
        if self.city_name:
            self.target_folder_id = f"{self.pref_code}_{self.pref_name}_{self.city_name}"
            self.target_display_name = f"{self.pref_name} {self.city_name}"
            city_ascii = kanji_to_romaji(self.city_name)
            self.ascii_label = f"pref{self.pref_code}_{self.pref_romaji}_{city_ascii}"
        else:
            self.target_folder_id = f"{self.pref_code}_{self.pref_name}"
            self.target_display_name = f"{self.pref_name}全域"
            self.ascii_label = f"pref{self.pref_code}_{self.pref_romaji}"

        self.boundary_layer_name = f"{self.ascii_label}_zukaku_2500_boundary"
        self.mesh_layer_name = f"{self.ascii_label}_fr_mesh_20"
        self.pref_out_dir = os.path.join(output_base_dir, f"output_{self.target_folder_id}")
        self.spatial_dir = os.path.join(self.pref_out_dir, "spatial_layers_by_zukaku")
        self.downloads_dir = os.path.join(self.pref_out_dir, "downloads")

        os.makedirs(self.downloads_dir, exist_ok=True)
        os.makedirs(self.spatial_dir, exist_ok=True)

        self.log_callback = log_callback or (lambda msg, pct: print(f"[{pct}%] {msg}"))
        self.cancel_check = cancel_check or (lambda: False)

    def log(self, message: str, pct: int = 0):
        if self.cancel_check():
            raise TaskCanceledException("ユーザーによって処理が中止されました。")
        self.log_callback(message, pct)

    def check_cancel(self):
        if self.cancel_check():
            raise TaskCanceledException("ユーザーによって処理が中止されました。")

    def run(self):
        """
        全パイプラインの一括実行 (図郭＝GeoJSON, メッシュ＝GPKG ハイブリッド版)
        """
        self.log(f"=== {self.target_display_name}（第{self.system_no}系, EPSG:{self.epsg}）の構築を開始 ===", 5)

        # 1. 行政境界 GeoJSON の取得 / 準備 & 自治体内に厳密に限定した 1/2,500 図郭抽出
        self.log(f"1. {self.target_display_name} の境界ポリゴンおよび 1/2,500 図郭メッシュの生成中...", 10)
        gdf_zukaku_6675, pref_geojson_path, zukaku_geojson_path = self._generate_zukaku_mesh()

        target_district_codes = set()
        for code in gdf_zukaku_6675["zukaku_code"]:
            if len(code) >= 4:
                target_district_codes.add(code[:4].upper())

        self.log(f"   対象地域に該当する 1/50,000 地区コード: {len(target_district_codes)} 地区 ({', '.join(sorted(list(target_district_codes))[:6])}...)")

        # 2. G空間情報センター CKAN リソース探索 & ピンポイント自動ダウンロード
        self.log(f"2. G空間情報センターより『全国森林資源メッシュ（第{self.system_no}系）』の該当データをピンポイント検索・ダウンロード中...", 25)
        downloaded_files = self._download_forest_resources(target_district_codes)

        if not downloaded_files:
            raise RuntimeError(f"G空間情報センターから {self.target_display_name} のデータが見つかりませんでした。")

        # 3. 20m メッシュデータ (GPKG) & マスター図郭境界 (GeoJSON) の生成
        self.log("3. 20m 森林資源メッシュ (.gpkg) および図郭境界 GeoJSON の生成中...", 50)
        summary_stats = self._build_spatial_layers(downloaded_files, gdf_zukaku_6675, zukaku_geojson_path)

        # 4. ZIP アーカイブの自動生成 (GeoPackage & GeoJSON パッケージ)
        self.log("4. 成果物 ZIP パッケージ (GPKG & GeoJSON) の作成中...", 85)
        zip_path = self._create_zip_archive()

        # 5. ストレージ無駄圧迫防止の自動クリーンアップ
        if self.auto_cleanup:
            self.log("5. ストレージ無駄圧迫防止のため元データ (.7z) をクリーンアップ中...", 95)
            self._cleanup_downloads()

        # ガベージコレクション強制回収
        gc.collect()

        self.log(f"[OK] {self.target_display_name} のデータ構築が完了いたしました！ (対象図郭数: {summary_stats['total_zukaku']}区画, 抽出メッシュ数: {summary_stats['total_mesh']:,}件)", 100)

        return {
            "pref": self.pref_info,
            "city_name": self.city_name,
            "target_folder_id": self.target_folder_id,
            "boundary_layer_name": self.boundary_layer_name,
            "mesh_layer_name": self.mesh_layer_name,
            "summary": summary_stats,
            "zip_path": zip_path,
            "output_dir": self.pref_out_dir
        }

    def _generate_zukaku_mesh(self):
        zukaku_geojson = os.path.join(self.pref_out_dir, f"{self.target_folder_id}_zukaku_2500.geojson")

        self.log(f"   {self.target_display_name} の境界ポリゴンを取得中...")
        from app.core.boundary import fetch_boundary_geojson
        gdf_boundary = fetch_boundary_geojson(self.pref_code, self.city_name)
        if gdf_boundary is None or len(gdf_boundary) == 0:
            raise RuntimeError(f"{self.target_display_name} の行政境界 GeoJSON の取得に失敗しました。")

        # 行政境界 GeoJSON を成果物フォルダ (spatial_layers_by_zukaku) に ASCII 名で出力・保存
        city_boundary_path = os.path.join(self.spatial_dir, f"city_boundary_{self.ascii_label}.geojson")
        try:
            gdf_boundary.to_crs(epsg=4326).to_file(city_boundary_path, driver="GeoJSON", engine="pyogrio")
            self.log(f"   [OK] 行政境界 GeoJSON '{os.path.basename(city_boundary_path)}' を成果物パックに追加しました。")
        except Exception as e:
            self.log(f"   警告: 行政境界 GeoJSON の保存に失敗しました: {e}")

        self.log(f"   [OK] {self.target_display_name} 境界ポリゴン取得完了。第{self.system_no}系 1/2,500 全図郭 (64,000区画) から高精度空間抽出中...")
        grid = Grid(system_number=self.system_no, level=2500)
        gdf_all = grid.make_grid().reset_index()
        if "index" in gdf_all.columns:
            gdf_all = gdf_all.rename(columns={"index": "code"})
        elif "code" not in gdf_all.columns:
            gdf_all["code"] = gdf_all.index

        gdf_all_6675 = gdf_all.set_crs(epsg=self.epsg)

        from pyproj import Transformer
        transformer = Transformer.from_crs(f"EPSG:{self.epsg}", "EPSG:4326", always_xy=True)
        geoms_4326 = [Polygon([transformer.transform(y, x) for y, x in g.exterior.coords]) for g in gdf_all.geometry]
        gdf_all_wgs84 = gpd.GeoDataFrame(gdf_all, geometry=geoms_4326, crs="EPSG:4326")

        geom_union = gdf_boundary.geometry.union_all() if hasattr(gdf_boundary.geometry, 'union_all') else gdf_boundary.geometry.unary_union
        if hasattr(geom_union, 'is_valid') and not geom_union.is_valid:
            from shapely.validation import make_valid
            geom_union = make_valid(geom_union)

        intersects_mask = gdf_all_wgs84.intersects(geom_union)
        gdf_target_wgs84 = gdf_all_wgs84[intersects_mask].copy()

        if len(gdf_target_wgs84) == 0:
            raise RuntimeError(f"{self.target_display_name} 領域と交差する 1/2,500 図郭が見つかりませんでした。")

        gdf_target_wgs84.to_file(zukaku_geojson, driver="GeoJSON", engine="pyogrio")
        gdf_target_6675 = gdf_all_6675[gdf_all_6675["code"].isin(gdf_target_wgs84["code"])].copy()
        gdf_target_6675 = gdf_target_6675.rename(columns={"code": "zukaku_code"})

        self.log(f"   [OK] {self.target_display_name} に含まれる 1/2,500 図郭数: {len(gdf_target_6675)} 区画")
        return gdf_target_6675, None, zukaku_geojson

    def _download_forest_resources(self, target_district_codes: set):
        package_id = f"mesh_{self.system_no}"
        ckan_api_url = f"https://www.geospatial.jp/ckan/api/3/action/package_show?id={package_id}"
        
        resources = []
        try:
            r = requests.get(ckan_api_url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                resources = data.get("result", {}).get("resources", [])
        except Exception as e:
            self.log(f"   CKAN API 接続エラー: {e}")

        matched_z_resources = []
        for res in resources:
            url = res.get("url", "")
            if not url.endswith(".7z"):
                continue

            fname = url.split("/")[-1].upper()
            parts = fname.replace('.7Z', '').split('_')
            file_district = None
            for p in parts:
                if len(p) >= 4 and p[:2].isdigit():
                    file_district = p[:4]
                    break

            if file_district and file_district in target_district_codes:
                matched_z_resources.append(res)

        self.log(f"   第{self.system_no}系データから、{self.target_display_name}（{len(target_district_codes)}地区）に該当する {len(matched_z_resources)} ファイルのみを厳密抽出DL中...")

        downloaded = []
        total_z = len(matched_z_resources)
        for idx, res in enumerate(matched_z_resources, start=1):
            self.check_cancel()
            url = res.get("url")
            fname = url.split("/")[-1]
            out_p = os.path.join(self.downloads_dir, fname)

            if os.path.exists(out_p) and os.path.getsize(out_p) > 1024:
                downloaded.append(out_p)
                continue

            try:
                r_dl = requests.get(url, stream=True, timeout=60)
                if r_dl.status_code == 200:
                    with open(out_p, "wb") as f:
                        for chunk in r_dl.iter_content(chunk_size=65536):
                            self.check_cancel()
                            f.write(chunk)
                    downloaded.append(out_p)
                    self.log(f"   [{idx}/{total_z}] DL完了: {fname}", 25 + int((idx/total_z)*20))
            except TaskCanceledException:
                raise
            except Exception as e:
                self.log(f"   エラー ({fname}): {e}")

        return downloaded

    def _build_spatial_layers(self, z_files, gdf_zukaku_6675, zukaku_geojson_path):
        mesh_groups = {}
        for z_file in z_files:
            fname = os.path.basename(z_file)
            parts = fname.replace('.7z', '').split('_')
            code_part = None
            for p in parts:
                if len(p) >= 4 and p[:2].isdigit():
                    code_part = p.upper()[:4]
                    break
            if not code_part:
                code_part = f"{self.system_no:02d}ALL"
            
            mesh_groups.setdefault(code_part, []).append(z_file)

        all_mesh_records = []
        valid_zukaku_codes = set(gdf_zukaku_6675["zukaku_code"])

        with tempfile.TemporaryDirectory() as temp_dir:
            total_groups = len(mesh_groups)
            for g_idx, (g_code, files) in enumerate(sorted(mesh_groups.items()), start=1):
                self.check_cancel()
                # 20m メッシュは GeoPackage (.gpkg) 形式で ASCII 名保存
                out_mesh_gpkg = os.path.join(self.spatial_dir, f"mesh_20m_{self.ascii_label}_{g_code}.gpkg")
                group_gdfs = []

                for z_path in files:
                    self.check_cancel()
                    z_name = os.path.basename(z_path)
                    sub_temp = os.path.join(temp_dir, f"{g_code}_{z_name}")
                    os.makedirs(sub_temp, exist_ok=True)
                    try:
                        with py7zr.SevenZipFile(z_path, mode='r') as z:
                            z.extractall(path=sub_temp)
                        gpkg_path = None
                        for root, dirs, f_list in os.walk(sub_temp):
                            for fn in f_list:
                                if fn.endswith(".gpkg"):
                                    gpkg_path = os.path.join(root, fn)
                                    break

                        if gpkg_path:
                            gdf_mesh = gpd.read_file(gpkg_path, engine="pyogrio", layer=0)
                            if len(gdf_mesh) > 0:
                                gdf_j = gpd.sjoin(gdf_mesh, gdf_zukaku_6675[["zukaku_code", "geometry"]], how="inner", predicate="intersects")
                                if "index_right" in gdf_j.columns:
                                    gdf_j = gdf_j.drop(columns=["index_right"])

                                gdf_j = gdf_j[gdf_j["zukaku_code"].isin(valid_zukaku_codes)]

                                for bad in ["標高", "樹高", "平均標高"]:
                                    if bad in gdf_j.columns:
                                        gdf_j = gdf_j.drop(columns=[bad])

                                if len(gdf_j) > 0:
                                    group_gdfs.append(gdf_j)
                                    all_mesh_records.append(gdf_j[["zukaku_code", "林種"]])
                    except TaskCanceledException:
                        raise
                    except Exception as e:
                        self.log(f"   エラー ({z_name}): {e}")

                if group_gdfs:
                    gdf_g_mesh = pd.concat(group_gdfs, ignore_index=True)
                    if len(gdf_g_mesh) > 0:
                        if os.path.exists(out_mesh_gpkg):
                            os.remove(out_mesh_gpkg)
                        # 20m メッシュを GPKG 形式で出力
                        layer_sub_name = f"mesh_20m_{self.ascii_label}_{g_code}"
                        gdf_g_mesh.to_file(out_mesh_gpkg, driver="GPKG", layer=layer_sub_name, engine="pyogrio")
                        self.log(f"   [OK] 地区 '{g_code}' 20mメッシュ GPKG 作成完了 ({len(gdf_g_mesh)} メッシュ)", 50 + int((g_idx/total_groups)*35))

                # ループごとのメモリ解放
                del group_gdfs
                gc.collect()

        # 属性集計 (林種7分類面積 ha & 人工林率 % & 20mメッシュ情報) およびマスター GeoJSON / GPKG の生成
        if all_mesh_records:
            df_all = pd.concat(all_mesh_records, ignore_index=True)
            df_all["林種"] = df_all["林種"].fillna("無林木地")
            ct = pd.crosstab(df_all["zukaku_code"], df_all["林種"])

            mesh_counts = df_all["zukaku_code"].value_counts()

            for cat in categories:
                if cat not in ct.columns:
                    ct[cat] = 0

            area_df = (ct[categories] * 0.04).round(3).reset_index()
            area_df["合計"] = (area_df["天然林"] + area_df["人工林"] + area_df["その他"] + area_df["未立木地"] + area_df["竹林"] + area_df["伐採跡地"]).round(3)
            area_df["人工林率"] = np.where(area_df["合計"] > 0, (area_df["人工林"] / area_df["合計"] * 100.0).round(2), np.nan)
            
            # 20mメッシュ情報 判定
            area_df["mesh_count"] = area_df["zukaku_code"].map(mesh_counts).fillna(0)
            area_df["20mメッシュ情報"] = np.where(
                area_df["mesh_count"] >= 3000, "取得",
                np.where(area_df["mesh_count"] > 0, "一部取得", "未取得")
            )
            area_df = area_df.drop(columns=["mesh_count"])

            gdf_master = gdf_zukaku_6675.merge(area_df, on="zukaku_code", how="left")
            gdf_master["20mメッシュ情報"] = gdf_master["20mメッシュ情報"].fillna("未取得")

            for cat in categories + ["合計"]:
                gdf_master[cat] = gdf_master[cat].fillna(0.000)

            # 図郭境界マスターは ASCII GeoJSON 形式で出力
            master_boundary_path = os.path.join(self.spatial_dir, f"zukaku_2500_master_{self.ascii_label}.geojson")
            if os.path.exists(master_boundary_path):
                os.remove(master_boundary_path)
            gdf_master_wgs84 = gdf_master.to_crs(epsg=4326)
            gdf_master_wgs84.to_file(master_boundary_path, driver="GeoJSON", engine="pyogrio")
            self.log(f"   [OK] 図郭境界マスター GeoJSON '{os.path.basename(master_boundary_path)}' 出力完了")

            total_mesh = len(df_all)
            total_zukaku = len(gdf_master)
            total_forest_ha = area_df["合計"].sum().round(2)
            avg_人工林率 = area_df["人工林率"].mean().round(2)

            del df_all, ct, area_df, gdf_master, gdf_master_wgs84
            gc.collect()
        else:
            gdf_master = gdf_zukaku_6675.copy()
            gdf_master["20mメッシュ情報"] = "未取得"
            for cat in categories + ["合計"]:
                gdf_master[cat] = 0.000
            gdf_master["人工林率"] = np.nan

            master_boundary_path = os.path.join(self.spatial_dir, f"zukaku_2500_master_{self.ascii_label}.geojson")
            if os.path.exists(master_boundary_path):
                os.remove(master_boundary_path)
            gdf_master_wgs84 = gdf_master.to_crs(epsg=4326)
            gdf_master_wgs84.to_file(master_boundary_path, driver="GeoJSON", engine="pyogrio")

            total_mesh = 0
            total_zukaku = len(gdf_zukaku_6675)
            total_forest_ha = 0.0
            avg_人工林率 = 0.0

        return {
            "total_mesh": total_mesh,
            "total_zukaku": total_zukaku,
            "total_forest_ha": total_forest_ha,
            "avg_人工林率": avg_人工林率,
            "districts_count": len(mesh_groups)
        }

    def _create_zip_archive(self):
        zip_filename = f"{self.ascii_label}_spatial_pack.zip"
        zip_filepath = os.path.join(self.pref_out_dir, zip_filename)

        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(self.spatial_dir):
                for fn in files:
                    fp = os.path.join(root, fn)
                    rel_p = os.path.relpath(fp, self.spatial_dir)
                    zf.write(fp, arcname=os.path.join("spatial_layers_by_zukaku", rel_p))

        return zip_filepath

    def _cleanup_downloads(self):
        if os.path.exists(self.downloads_dir):
            try:
                shutil.rmtree(self.downloads_dir)
            except Exception:
                pass
