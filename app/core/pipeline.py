# -*- coding: utf-8 -*-
"""
全国都道府県 & 市区町村対応 1/2,500 公共測量図郭 & 国土地理院 DEM (5m/10m)・傾斜分布図 構築パイプライン
"""

import os
import sys
import gc
import shutil
import tempfile
import zipfile
import numpy as np
import pandas as pd
import geopandas as gpd
import pyogrio
from shapely.geometry import Polygon
from japan_basic_section.grid import Grid

from app.core.prefectures import get_pref_info, to_ascii_identifier
from app.core.prefectures import get_pref_info, to_ascii_identifier
from app.core.romaji import kanji_to_romaji
from app.core.dem import (
    download_and_merge_dem, calculate_slope, calculate_aspect,
    calculate_hillshade, calculate_curvature, generate_cs_map,
    calculate_twi, calculate_viewshed, save_geotiff, save_rgb_geotiff
)

class TaskCanceledException(Exception):
    pass

class PipelineRunner:
    def __init__(
        self,
        pref_key: str,
        output_base_dir: str,
        city_name: str = None,
        resolution: str = "5m",
        generate_slope: bool = True,
        analysis_options: dict = None,
        auto_cleanup: bool = True,
        log_callback=None,
        cancel_check=None
    ):
        self.pref_info = get_pref_info(pref_key)
        if not self.pref_info:
            raise ValueError(f"指定された都道府県情報が見つかりません: {pref_key}")

        self.pref_code = self.pref_info["code"]
        self.pref_name = self.pref_info["name"]
        self.pref_romaji = self.pref_info.get("romaji", "pref")
        self.system_no = self.pref_info["system"]
        self.epsg = self.pref_info["epsg"]
        self.city_name = city_name if (city_name and city_name != "ALL") else None
        self.resolution = resolution if resolution in ["5m", "10m"] else "5m"
        self.generate_slope = generate_slope
        self.analysis_options = analysis_options or {
            "slope": generate_slope,
            "aspect": False,
            "hillshade": False,
            "curvature": False,
            "csmap": False,
            "twi": False,
            "viewshed": False
        }
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

        self.pref_out_dir = os.path.join(output_base_dir, f"output_{self.target_folder_id}")
        self.spatial_dir = os.path.join(self.pref_out_dir, "spatial_layers_by_zukaku")

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
        全パイプラインの一括実行 (行政境界GeoJSON, 公共図郭GeoJSON, DEM GeoTIFF, 各種多角解析GeoTIFF)
        """
        self.log(f"=== {self.target_display_name}（DEM解像度: {self.resolution}）の構築を開始 ===", 5)

        # 1. 行政境界 GeoJSON の取得 / 準備 & 自治体内に厳密に限定した 1/2,500 図郭抽出
        self.log(f"1. {self.target_display_name} の行政境界ポリゴンおよび 1/2,500 図郭メッシュの生成中...", 10)
        gdf_zukaku_6675, _, zukaku_geojson_path = self._generate_zukaku_mesh()

        gdf_zukaku_wgs84 = gpd.read_file(zukaku_geojson_path, engine="pyogrio")
        total_zukaku = len(gdf_zukaku_wgs84)
        bounds = tuple(gdf_zukaku_wgs84.total_bounds) # (min_lon, min_lat, max_lon, max_lat)

        # 2. 国土地理院 DEM のダウンロード & 結合
        self.log(f"2. 国土地理院 標高タイル ({self.resolution}メッシュ) を取得・1ファイルに一括結合中...", 25)
        
        def progress_cb(completed, total):
            self.check_cancel()
            pct = 25 + int((completed / max(total, 1)) * 40)
            if completed % max(1, total // 10) == 0 or completed == total:
                self.log(f"   DEM タイル取得中: {completed}/{total} タイル完了 ({pct}%)", pct)

        dem_array, actual_bounds, zoom = download_and_merge_dem(
            bounds,
            resolution=self.resolution,
            max_workers=8,
            progress_callback=progress_cb
        )

        dem_geotiff_name = f"dem_{self.resolution}_{self.ascii_label}.tif"
        dem_geotiff_path = os.path.join(self.spatial_dir, dem_geotiff_name)
        save_geotiff(dem_geotiff_path, dem_array, actual_bounds, crs_epsg=4326)
        self.log(f"   [OK] DEM GeoTIFF '{dem_geotiff_name}' 出力完了", 68)

        # 標高統計の計算
        valid_elev = dem_array[~np.isnan(dem_array)]
        min_elev = float(np.min(valid_elev)) if len(valid_elev) > 0 else 0.0
        max_elev = float(np.max(valid_elev)) if len(valid_elev) > 0 else 0.0
        mean_elev = float(np.mean(valid_elev)) if len(valid_elev) > 0 else 0.0

        # 3. 多角GIS合成解析
        generated_layers = {}
        opts = self.analysis_options

        if opts.get("slope", False):
            self.log(f"3-1. 傾斜角度 (Slope Map) の合成解析中...", 72)
            slope_arr = calculate_slope(dem_array, actual_bounds)
            name = f"slope_{self.resolution}_{self.ascii_label}.tif"
            save_geotiff(os.path.join(self.spatial_dir, name), slope_arr, actual_bounds)
            generated_layers["slope"] = name

        if opts.get("aspect", False):
            self.log(f"3-2. 斜面方位 (Aspect Map) の合成解析中...", 75)
            aspect_arr = calculate_aspect(dem_array, actual_bounds)
            name = f"aspect_{self.resolution}_{self.ascii_label}.tif"
            save_geotiff(os.path.join(self.spatial_dir, name), aspect_arr, actual_bounds)
            generated_layers["aspect"] = name

        if opts.get("hillshade", False):
            self.log(f"3-3. 陰影起伏 (Hillshade) の合成解析中...", 78)
            hillshade_arr = calculate_hillshade(dem_array, actual_bounds)
            name = f"hillshade_{self.resolution}_{self.ascii_label}.tif"
            save_geotiff(os.path.join(self.spatial_dir, name), hillshade_arr, actual_bounds)
            generated_layers["hillshade"] = name

        if opts.get("curvature", False):
            self.log(f"3-4. 地形曲率 (Curvature) の合成解析中...", 81)
            curv_arr = calculate_curvature(dem_array, actual_bounds)
            name = f"curvature_{self.resolution}_{self.ascii_label}.tif"
            save_geotiff(os.path.join(self.spatial_dir, name), curv_arr, actual_bounds)
            generated_layers["curvature"] = name

        if opts.get("csmap", False):
            self.log(f"3-5. CS立体図 (CS Map RGB GeoTIFF) の合成解析中...", 84)
            cs_rgb = generate_cs_map(dem_array, actual_bounds)
            name = f"csmap_{self.resolution}_{self.ascii_label}.tif"
            save_rgb_geotiff(os.path.join(self.spatial_dir, name), cs_rgb, actual_bounds)
            generated_layers["csmap"] = name

        if opts.get("twi", False):
            self.log(f"3-6. 地形湿潤指数 (TWI) の合成解析中...", 86)
            twi_arr = calculate_twi(dem_array, actual_bounds)
            name = f"twi_{self.resolution}_{self.ascii_label}.tif"
            save_geotiff(os.path.join(self.spatial_dir, name), twi_arr, actual_bounds)
            generated_layers["twi"] = name

        if opts.get("viewshed", False):
            self.log(f"3-7. 可視領域 (Viewshed) の合成解析中...", 88)
            viewshed_arr = calculate_viewshed(dem_array, actual_bounds)
            name = f"viewshed_{self.resolution}_{self.ascii_label}.tif"
            save_geotiff(os.path.join(self.spatial_dir, name), viewshed_arr, actual_bounds)
            generated_layers["viewshed"] = name

        self.log(f"   [OK] 全選択GIS層の GeoTIFF 合成完了", 89)

        # 4. ZIP アーカイブの自動生成
        self.log("4. 成果物 ZIP パッケージ (GeoJSON & GeoTIFF) の作成中...", 90)
        zip_path = self._create_zip_archive()

        gc.collect()

        summary_stats = {
            "total_zukaku": total_zukaku,
            "resolution": self.resolution,
            "dem_geotiff": dem_geotiff_name,
            "generated_layers": generated_layers,
            "min_elevation_m": round(min_elev, 1),
            "max_elevation_m": round(max_elev, 1),
            "mean_elevation_m": round(mean_elev, 1),
            "bounds": actual_bounds
        }


        self.log(f"[OK] {self.target_display_name} の DEM・傾斜パッケージ構築が完了いたしました！ (対象図郭数: {total_zukaku}区画, 標高範囲: {min_elev:.1f}m ~ {max_elev:.1f}m)", 100)

        return {
            "pref": self.pref_info,
            "city_name": self.city_name,
            "target_folder_id": self.target_folder_id,
            "summary": summary_stats,
            "zip_path": zip_path,
            "output_dir": self.pref_out_dir
        }

    def _generate_zukaku_mesh(self):
        zukaku_geojson = os.path.join(self.spatial_dir, f"zukaku_2500_master_{self.ascii_label}.geojson")

        self.log(f"   {self.target_display_name} の行政境界ポリゴンを取得中...")
        from app.core.boundary import fetch_boundary_geojson
        gdf_boundary = fetch_boundary_geojson(self.pref_code, self.city_name)
        if gdf_boundary is None or len(gdf_boundary) == 0:
            raise RuntimeError(f"{self.target_display_name} の行政境界 GeoJSON の取得に失敗しました。")

        city_boundary_path = os.path.join(self.spatial_dir, f"city_boundary_{self.ascii_label}.geojson")
        try:
            gdf_boundary.to_crs(epsg=4326).to_file(city_boundary_path, driver="GeoJSON", engine="pyogrio")
            self.log(f"   [OK] 行政境界 GeoJSON '{os.path.basename(city_boundary_path)}' を成果物パックに追加しました。")
        except Exception as e:
            self.log(f"   警告: 行政境界 GeoJSON の保存に失敗しました: {e}")

        self.log(f"   [OK] {self.target_display_name} 境界ポリゴン取得完了。第{self.system_no}系 1/2,500 全図郭から高精度空間抽出中...")
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

    def _create_zip_archive(self):
        zip_filename = f"{self.ascii_label}_dem_spatial_pack.zip"
        zip_filepath = os.path.join(self.pref_out_dir, zip_filename)

        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(self.spatial_dir):
                for fn in files:
                    fp = os.path.join(root, fn)
                    rel_p = os.path.relpath(fp, self.spatial_dir)
                    zf.write(fp, arcname=os.path.join("spatial_layers_by_zukaku", rel_p))

        return zip_filepath
