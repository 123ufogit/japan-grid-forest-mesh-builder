# -*- coding: utf-8 -*-
"""
都道府県および市区町村境界 GeoJSON 高精度・高速取得モジュール
(自己交差・不正ジオメトリの自動修復 make_valid / buffer(0) 対応)
"""

import os
import json
import requests
import geopandas as gpd
from shapely.geometry import shape
from shapely.ops import unary_union
from shapely.validation import make_valid

RAW_BASE_URL = "https://raw.githubusercontent.com/niiyz/JapanCityGeoJson/master/geojson/"
PREF_RAW_BASE_URL = "https://raw.githubusercontent.com/amay077/JapanPrefGeoJson/master/prefs/"

_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache_geojson")
os.makedirs(_CACHE_DIR, exist_ok=True)

# よく使われる市区町村コードのエイリアスマップ（キャッシュ）
KNOWN_CITY_CODES = {
    "40_糸島市": "40230",
    "17_野々市市": "17212",
    "17_金沢市": "17201",
    "17_七尾市": "17202",
    "17_小松市": "17203",
    "17_輪島市": "17204",
    "17_珠洲市": "17205",
    "17_加賀市": "17206",
    "17_羽咋市": "17207",
    "17_かほく市": "17209",
    "17_白山市": "17210",
    "17_能美市": "17211",
}

def fetch_boundary_geojson(pref_code: str, city_name: str = None) -> gpd.GeoDataFrame:
    """
    指定された都道府県コード・市区町村名から境界 GeoDataFrame (EPSG:4326) を取得
    """
    pref_code = f"{int(pref_code):02d}"
    
    if city_name:
        gdf = _fetch_city_boundary(pref_code, city_name)
        if gdf is not None and len(gdf) > 0:
            return gdf
        raise RuntimeError(f"指定された市区町村 '{city_name}' (都道府県コード: {pref_code}) の境界 GeoJSON を取得できませんでした。")
    else:
        gdf = _fetch_pref_boundary(pref_code)
        if gdf is not None and len(gdf) > 0:
            return gdf
        raise RuntimeError(f"都道府県 (コード: {pref_code}) の境界 GeoJSON を取得できませんでした。")

def _fetch_city_boundary(pref_code: str, city_name: str) -> gpd.GeoDataFrame:
    cache_path = os.path.join(_CACHE_DIR, f"city_{pref_code}_{city_name}.geojson")
    if os.path.exists(cache_path):
        try:
            gdf = gpd.read_file(cache_path, engine="pyogrio")
            if len(gdf) > 0:
                return gdf
        except Exception:
            pass

    lookup_key = f"{pref_code}_{city_name}"
    known_code = KNOWN_CITY_CODES.get(lookup_key)

    matched_geoms = []

    # 1. 既知コードがある場合は直接ダウンロード
    if known_code:
        url = f"{RAW_BASE_URL}{pref_code}/{known_code}.json"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                text = _decode_text(r.content)
                if text:
                    data = json.loads(text)
                    for feat in data.get("features", []):
                        g = shape(feat["geometry"])
                        if not g.is_valid:
                            g = make_valid(g)
                        matched_geoms.append(g)
        except Exception:
            pass

    # 2. 直接取得が成功しなかった場合は GitHub API で検索
    if not matched_geoms:
        try:
            tree_url = "https://api.github.com/repos/niiyz/JapanCityGeoJson/git/trees/master?recursive=1"
            r = requests.get(tree_url, timeout=10)
            if r.status_code == 200:
                tree = r.json().get("tree", [])
                prefix = f"geojson/{pref_code}/"
                target_files = [t["path"] for t in tree if t["path"].startswith(prefix) and t["path"].endswith(".json")]

                for rel_path in target_files:
                    url = f"https://raw.githubusercontent.com/niiyz/JapanCityGeoJson/master/{rel_path}"
                    try:
                        r_file = requests.get(url, timeout=5)
                        if r_file.status_code == 200:
                            text = _decode_text(r_file.content)
                            if text and city_name in text:
                                data = json.loads(text)
                                for feat in data.get("features", []):
                                    props = feat.get("properties", {})
                                    if any(city_name in str(val) for val in props.values()):
                                        g = shape(feat["geometry"])
                                        if not g.is_valid:
                                            g = make_valid(g)
                                        matched_geoms.append(g)
                                if matched_geoms:
                                    break
                    except Exception:
                        continue
        except Exception:
            pass

    if matched_geoms:
        merged_geom = unary_union(matched_geoms)
        if not merged_geom.is_valid:
            merged_geom = make_valid(merged_geom)
        gdf = gpd.GeoDataFrame(geometry=[merged_geom], crs="EPSG:4326")
        try:
            gdf.to_file(cache_path, driver="GeoJSON", engine="pyogrio")
        except Exception:
            pass
        return gdf

    return None

def _fetch_pref_boundary(pref_code: str) -> gpd.GeoDataFrame:
    cache_path = os.path.join(_CACHE_DIR, f"pref_{pref_code}.geojson")
    if os.path.exists(cache_path):
        try:
            gdf = gpd.read_file(cache_path, engine="pyogrio")
            if len(gdf) > 0:
                return gdf
        except Exception:
            pass

    url = f"{PREF_RAW_BASE_URL}{pref_code}.geojson"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            with open(cache_path, "wb") as f:
                f.write(r.content)
            gdf = gpd.read_file(cache_path, engine="pyogrio")
            if len(gdf) > 0 and not gdf.geometry.iloc[0].is_valid:
                gdf.geometry = gdf.geometry.apply(lambda g: make_valid(g) if not g.is_valid else g)
            return gdf
    except Exception as e:
        print(f"Warning: Failed to fetch pref boundary for {pref_code}: {e}")

    return None

def _decode_text(raw_bytes: bytes) -> str:
    for enc in ["shift_jis", "utf-8", "cp932"]:
        try:
            return raw_bytes.decode(enc)
        except Exception:
            continue
    return None
