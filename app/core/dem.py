# -*- coding: utf-8 -*-
"""
国土地理院 標高タイル (DEM 5m / 10m) 取得・結合・傾斜分布図 (Slope Map) 解析モジュール
"""

import math
import io
import os
import requests
import numpy as np
from PIL import Image
import concurrent.futures
from typing import Tuple, Dict, Any, List, Optional
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS

# DEM タイル URL テンプレート
DEM_URLS = {
    "5m": [
        "https://cyberjapandata.gsi.go.jp/xyz/dem5a_png/{z}/{x}/{y}.png",
        "https://cyberjapandata.gsi.go.jp/xyz/dem5b_png/{z}/{x}/{y}.png",
        "https://cyberjapandata.gsi.go.jp/xyz/dem5c_png/{z}/{x}/{y}.png",
    ],
    "10m": [
        "https://cyberjapandata.gsi.go.jp/xyz/dem10b_png/{z}/{x}/{y}.png",
        "https://cyberjapandata.gsi.go.jp/xyz/dem_png/{z}/{x}/{y}.png",
    ]
}

ZOOM_LEVELS = {
    "5m": 15,
    "10m": 14
}

def latlon_to_tile(lat: float, lon: float, zoom: int) -> Tuple[int, int]:
    """緯度経度から Web メルカトル タイル座標 (x, y) を計算"""
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return xtile, ytile

def tile_to_latlon_bounds(xtile: int, ytile: int, zoom: int) -> Tuple[float, float, float, float]:
    """タイル座標から緯度経度バウンディングボックス (min_lon, min_lat, max_lon, max_lat) を計算"""
    n = 2.0 ** zoom
    min_lon = xtile / n * 360.0 - 180.0
    max_lon = (xtile + 1) / n * 360.0 - 180.0
    
    lat_rad_max = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_rad_min = math.atan(math.sinh(math.pi * (1 - 2 * (ytile + 1) / n)))
    
    min_lat = math.degrees(lat_rad_min)
    max_lat = math.degrees(lat_rad_max)
    return min_lon, min_lat, max_lon, max_lat

def decode_dem_tile_png(img: Image.Image) -> np.ndarray:
    """
    国土地理院 標高タイル PNG (RGB) を標高値 (メートル) の 2D NumPy 配列に変換
    標高計算式:
      x = 2^16 * R + 2^8 * G + B
      x < 2^23  => h = x * 0.01
      x = 2^23  => 無効値 (np.nan)
      x > 2^23  => h = (x - 2^24) * 0.01
    """
    img_rgb = img.convert("RGB")
    arr = np.array(img_rgb, dtype=np.uint32)
    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]
    
    x = (r << 16) + (g << 8) + b
    
    elevation = np.full(x.shape, np.nan, dtype=np.float32)
    
    valid_pos = x < 8388608
    elevation[valid_pos] = x[valid_pos] * 0.01
    
    valid_neg = x > 8388608
    elevation[valid_neg] = (x[valid_neg] - 16777216) * 0.01
    
    return elevation

def fetch_single_tile(x: int, y: int, z: int, resolution: str) -> Optional[np.ndarray]:
    """単一タイルの取得とデコード (フォールバック対応)"""
    urls = DEM_URLS.get(resolution, DEM_URLS["10m"])
    headers = {"User-Agent": "Mozilla/5.0 (Japan-GIS-Mesh-Builder)"}
    
    for url_fmt in urls:
        url = url_fmt.format(x=x, y=y, z=z)
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content))
                dem_data = decode_dem_tile_png(img)
                if not np.all(np.isnan(dem_data)):
                    return dem_data
        except Exception:
            continue
    return None

def check_dem_availability(bounds: Tuple[float, float, float, float]) -> Dict[str, bool]:
    """
    指定バウンディングボックス (min_lon, min_lat, max_lon, max_lat) において
    5m および 10m DEM が利用可能かをサンプル判定
    """
    min_lon, min_lat, max_lon, max_lat = bounds
    center_lon = (min_lon + max_lon) / 2.0
    center_lat = (min_lat + max_lat) / 2.0
    
    result = {"5m": False, "10m": False}
    
    for res in ["5m", "10m"]:
        z = ZOOM_LEVELS[res]
        points = [
            (center_lat, center_lon),
            (min_lat, min_lon),
            (max_lat, max_lon),
            (min_lat, max_lon),
            (max_lat, min_lon)
        ]
        
        for lat, lon in points:
            xtile, ytile = latlon_to_tile(lat, lon, z)
            tile_data = fetch_single_tile(xtile, ytile, z, res)
            if tile_data is not None and not np.all(np.isnan(tile_data)):
                result[res] = True
                break
                
    return result

def download_and_merge_dem(
    bounds: Tuple[float, float, float, float],
    resolution: str = "5m",
    max_workers: int = 8,
    progress_callback=None
) -> Tuple[np.ndarray, Tuple[float, float, float, float], int]:
    """
    指定バウンディングボックスの全 DEM タイルを取得・2D配列へ結合
    戻り値: (dem_array, (min_lon, min_lat, max_lon, max_lat), zoom_level)
    """
    min_lon, min_lat, max_lon, max_lat = bounds
    zoom = ZOOM_LEVELS.get(resolution, 14)
    
    x1, y1 = latlon_to_tile(max_lat, min_lon, zoom)
    x2, y2 = latlon_to_tile(min_lat, max_lon, zoom)
    
    x_start, x_end = min(x1, x2), max(x1, x2)
    y_start, y_end = min(y1, y2), max(y1, y2)
    
    num_x = x_end - x_start + 1
    num_y = y_end - y_start + 1
    total_tiles = num_x * num_y
    
    merged_min_lon, merged_min_lat, _, _ = tile_to_latlon_bounds(x_start, y_end, zoom)
    _, _, merged_max_lon, merged_max_lat = tile_to_latlon_bounds(x_end, y_start, zoom)
    
    full_dem = np.full((num_y * 256, num_x * 256), np.nan, dtype=np.float32)
    
    completed = 0
    tile_coords = []
    for y_idx, y_tile in enumerate(range(y_start, y_end + 1)):
        for x_idx, x_tile in enumerate(range(x_start, x_end + 1)):
            tile_coords.append((x_idx, y_idx, x_tile, y_tile))
            
    def worker(item):
        x_idx, y_idx, x_tile, y_tile = item
        dem_tile = fetch_single_tile(x_tile, y_tile, zoom, resolution)
        return x_idx, y_idx, dem_tile

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, item) for item in tile_coords]
        for future in concurrent.futures.as_completed(futures):
            x_idx, y_idx, dem_tile = future.result()
            completed += 1
            if progress_callback:
                progress_callback(completed, total_tiles)
                
            if dem_tile is not None:
                full_dem[y_idx * 256 : (y_idx + 1) * 256, x_idx * 256 : (x_idx + 1) * 256] = dem_tile

    actual_bounds = (merged_min_lon, merged_min_lat, merged_max_lon, merged_max_lat)
    return full_dem, actual_bounds, zoom

def calculate_slope(
    dem_array: np.ndarray,
    bounds: Tuple[float, float, float, float]
) -> np.ndarray:
    """
    DEM 標高グリッドから傾斜角度 (度: degrees) を算出
    """
    min_lon, min_lat, max_lon, max_lat = bounds
    rows, cols = dem_array.shape
    
    lat_center = (min_lat + max_lat) / 2.0
    lat_m_per_deg = 111132.92 - 559.82 * math.cos(2 * math.radians(lat_center))
    lon_m_per_deg = 111412.84 * math.cos(math.radians(lat_center))
    
    dx = abs(max_lon - min_lon) / cols * lon_m_per_deg
    dy = abs(max_lat - min_lat) / rows * lat_m_per_deg
    
    filled_dem = dem_array.copy()
    nan_mask = np.isnan(filled_dem)
    if np.any(nan_mask):
        mean_val = np.nanmean(filled_dem)
        filled_dem[nan_mask] = mean_val if not np.isnan(mean_val) else 0.0
        
    grad_y, grad_x = np.gradient(filled_dem, dy, dx)
    slope_rad = np.arctan(np.sqrt(grad_x**2 + grad_y**2))
    slope_deg = np.degrees(slope_rad).astype(np.float32)
    
    slope_deg[nan_mask] = np.nan
    return slope_deg

def calculate_aspect(
    dem_array: np.ndarray,
    bounds: Tuple[float, float, float, float]
) -> np.ndarray:
    """斜面方位 (Aspect: 0°~360°, 北=0°) を算出"""
    min_lon, min_lat, max_lon, max_lat = bounds
    rows, cols = dem_array.shape
    lat_center = (min_lat + max_lat) / 2.0
    lat_m_per_deg = 111132.92 - 559.82 * math.cos(2 * math.radians(lat_center))
    lon_m_per_deg = 111412.84 * math.cos(math.radians(lat_center))
    dx = abs(max_lon - min_lon) / cols * lon_m_per_deg
    dy = abs(max_lat - min_lat) / rows * lat_m_per_deg
    
    filled_dem = dem_array.copy()
    nan_mask = np.isnan(filled_dem)
    if np.any(nan_mask):
        mean_val = np.nanmean(filled_dem)
        filled_dem[nan_mask] = mean_val if not np.isnan(mean_val) else 0.0
        
    grad_y, grad_x = np.gradient(filled_dem, dy, dx)
    aspect = np.degrees(np.arctan2(-grad_x, grad_y))
    aspect = np.where(aspect < 0, aspect + 360.0, aspect).astype(np.float32)
    aspect[nan_mask] = np.nan
    return aspect

def calculate_hillshade(
    dem_array: np.ndarray,
    bounds: Tuple[float, float, float, float],
    azimuth: float = 315.0,
    altitude: float = 45.0
) -> np.ndarray:
    """陰影起伏 (Hillshade: 0-255 輝度) を算出"""
    min_lon, min_lat, max_lon, max_lat = bounds
    rows, cols = dem_array.shape
    lat_center = (min_lat + max_lat) / 2.0
    lat_m_per_deg = 111132.92 - 559.82 * math.cos(2 * math.radians(lat_center))
    lon_m_per_deg = 111412.84 * math.cos(math.radians(lat_center))
    dx = abs(max_lon - min_lon) / cols * lon_m_per_deg
    dy = abs(max_lat - min_lat) / rows * lat_m_per_deg
    
    filled_dem = dem_array.copy()
    nan_mask = np.isnan(filled_dem)
    if np.any(nan_mask):
        mean_val = np.nanmean(filled_dem)
        filled_dem[nan_mask] = mean_val if not np.isnan(mean_val) else 0.0
        
    grad_y, grad_x = np.gradient(filled_dem, dy, dx)
    slope_rad = np.arctan(np.sqrt(grad_x**2 + grad_y**2))
    aspect_rad = np.arctan2(-grad_x, grad_y)
    
    zenith_rad = math.radians(90.0 - altitude)
    azimuth_rad = math.radians(360.0 - azimuth + 90.0)
    
    shaded = (np.cos(zenith_rad) * np.cos(slope_rad) +
              np.sin(zenith_rad) * np.sin(slope_rad) * np.cos(azimuth_rad - aspect_rad))
    
    hillshade = np.clip(255.0 * np.maximum(0.0, shaded), 0, 255).astype(np.float32)
    hillshade[nan_mask] = np.nan
    return hillshade

def calculate_curvature(
    dem_array: np.ndarray,
    bounds: Tuple[float, float, float, float]
) -> np.ndarray:
    """地形曲率 (Curvature: 正=尾根, 負=谷) を算出"""
    min_lon, min_lat, max_lon, max_lat = bounds
    rows, cols = dem_array.shape
    lat_center = (min_lat + max_lat) / 2.0
    lat_m_per_deg = 111132.92 - 559.82 * math.cos(2 * math.radians(lat_center))
    lon_m_per_deg = 111412.84 * math.cos(math.radians(lat_center))
    dx = abs(max_lon - min_lon) / cols * lon_m_per_deg
    dy = abs(max_lat - min_lat) / rows * lat_m_per_deg
    
    filled_dem = dem_array.copy()
    nan_mask = np.isnan(filled_dem)
    if np.any(nan_mask):
        mean_val = np.nanmean(filled_dem)
        filled_dem[nan_mask] = mean_val if not np.isnan(mean_val) else 0.0
        
    grad_y, grad_x = np.gradient(filled_dem, dy, dx)
    g_yy, _ = np.gradient(grad_y, dy, dx)
    _, g_xx = np.gradient(grad_x, dy, dx)
    
    laplacian = (g_xx + g_yy).astype(np.float32)
    laplacian[nan_mask] = np.nan
    return laplacian

def generate_cs_map(
    dem_array: np.ndarray,
    bounds: Tuple[float, float, float, float]
) -> np.ndarray:
    """CS立体図 (CS Map) 3チャンネル RGB 配列 (shape: 3, rows, cols) を生成"""
    slope_deg = calculate_slope(dem_array, bounds)
    curvature = calculate_curvature(dem_array, bounds)
    nan_mask = np.isnan(dem_array)
    
    slope_norm = np.clip(slope_deg / 45.0 * 255.0, 0, 255)
    curv_std = float(np.nanstd(curvature)) if not np.all(np.isnan(curvature)) else 1.0
    curv_std = max(curv_std, 1e-5)
    
    ridge = np.clip(curvature / (curv_std * 2.0) * 255.0, 0, 255)
    valley = np.clip(-curvature / (curv_std * 2.0) * 255.0, 0, 255)
    
    r_channel = np.clip(ridge + (255 - slope_norm) * 0.3, 0, 255).astype(np.uint8)
    g_channel = np.clip(255 - slope_norm * 0.8, 0, 255).astype(np.uint8)
    b_channel = np.clip(valley + (255 - slope_norm) * 0.3, 0, 255).astype(np.uint8)
    
    r_channel[nan_mask] = 0
    g_channel[nan_mask] = 0
    b_channel[nan_mask] = 0
    
    return np.stack([r_channel, g_channel, b_channel], axis=0)

def calculate_twi(
    dem_array: np.ndarray,
    bounds: Tuple[float, float, float, float]
) -> np.ndarray:
    """地形湿潤指数 (Topographic Wetness Index: TWI) を算出"""
    slope_deg = calculate_slope(dem_array, bounds)
    slope_rad = np.radians(np.maximum(slope_deg, 0.1))
    
    filled_dem = dem_array.copy()
    nan_mask = np.isnan(filled_dem)
    if np.any(nan_mask):
        mean_val = np.nanmean(filled_dem)
        filled_dem[nan_mask] = mean_val if not np.isnan(mean_val) else 0.0
        
    grad_y, grad_x = np.gradient(filled_dem)
    flow_mag = np.sqrt(grad_x**2 + grad_y**2) + 1e-4
    sca = 1.0 + (1.0 / flow_mag)
    
    twi = np.log(sca / np.tan(slope_rad))
    twi = np.clip(twi, -2.0, 20.0).astype(np.float32)
    twi[nan_mask] = np.nan
    return twi

def calculate_viewshed(
    dem_array: np.ndarray,
    bounds: Tuple[float, float, float, float]
) -> np.ndarray:
    """中心観測点からの可視領域解析 (1=可視, 0=視蔽/不可視)"""
    rows, cols = dem_array.shape
    nan_mask = np.isnan(dem_array)
    
    obs_r, obs_c = rows // 2, cols // 2
    obs_elev = float(dem_array[obs_r, obs_c]) if not np.isnan(dem_array[obs_r, obs_c]) else float(np.nanmean(dem_array))
    obs_elev += 2.0
    
    rr, cc = np.ogrid[:rows, :cols]
    dist = np.sqrt((rr - obs_r)**2 + (cc - obs_c)**2) + 1e-5
    
    elev_diff = dem_array - obs_elev
    viewshed = np.where(elev_diff / dist > 0.05, 0.0, 1.0).astype(np.float32)
    viewshed[nan_mask] = np.nan
    return viewshed

def save_geotiff(
    output_path: str,
    data_array: np.ndarray,
    bounds: Tuple[float, float, float, float],
    crs_epsg: int = 4326,
    nodata_val: float = -9999.0
) -> str:
    """2D NumPy 配列を GeoTIFF に保存"""
    min_lon, min_lat, max_lon, max_lat = bounds
    rows, cols = data_array.shape
    
    transform = from_bounds(min_lon, min_lat, max_lon, max_lat, cols, rows)
    
    out_data = data_array.copy()
    out_data[np.isnan(out_data)] = nodata_val
    
    with rasterio.open(
        output_path,
        'w',
        driver='GTiff',
        height=rows,
        width=cols,
        count=1,
        dtype=out_data.dtype,
        crs=CRS.from_epsg(crs_epsg),
        transform=transform,
        nodata=nodata_val,
        compress='lzw'
    ) as dst:
        dst.write(out_data, 1)
        
    return output_path

def save_rgb_geotiff(
    output_path: str,
    rgb_array: np.ndarray,
    bounds: Tuple[float, float, float, float],
    crs_epsg: int = 4326
) -> str:
    """3チャンネル uint8 RGB 配列を GeoTIFF に保存"""
    min_lon, min_lat, max_lon, max_lat = bounds
    bands, rows, cols = rgb_array.shape
    transform = from_bounds(min_lon, min_lat, max_lon, max_lat, cols, rows)
    
    with rasterio.open(
        output_path,
        'w',
        driver='GTiff',
        height=rows,
        width=cols,
        count=3,
        dtype=np.uint8,
        crs=CRS.from_epsg(crs_epsg),
        transform=transform,
        compress='lzw'
    ) as dst:
        dst.write(rgb_array)
    return output_path

