import math
import requests
import pandas as pd
import numpy as np

def latlon_to_tile(lat, lon, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return xtile, ytile

def estimate_canopy_height(species, age):
    """
    樹種と林齢に基づく DCHM (樹高モデル) の推定関数 (単位: m)
    """
    if pd.isna(age) or age <= 0:
        return 0.0
    
    sp = str(species) if pd.notna(species) else "その他"
    
    if "スギ" in sp:
        h = 32.0 * ((1.0 - math.exp(-0.035 * age)) ** 1.3)
    elif "ヒノキ" in sp:
        h = 28.0 * ((1.0 - math.exp(-0.032 * age)) ** 1.2)
    elif "アテ" in sp or "アテ(アスナロ)" in sp or "アスナロ" in sp:
        h = 26.0 * ((1.0 - math.exp(-0.030 * age)) ** 1.2)
    elif "マツ" in sp or "アカマツ" in sp or "クロマツ" in sp:
        h = 24.0 * ((1.0 - math.exp(-0.038 * age)) ** 1.4)
    elif "広葉樹" in sp or "ナラ" in sp or "ブナ" in sp or "クヌギ" in sp:
        h = 22.0 * ((1.0 - math.exp(-0.040 * age)) ** 1.5)
    else:
        h = 20.0 * ((1.0 - math.exp(-0.035 * age)) ** 1.3)
        
    return round(max(0.0, h), 2)

# テスト
print("石川県（金沢周辺: 緯度36.56, 経度136.65, ズーム14）の標高タイルインデックス計算:")
x, y = latlon_to_tile(36.56, 136.65, 14)
print(f"Tile Z=14: X={x}, Y={y}")

print("\nDCHM 樹高推定テスト:")
test_cases = [
    ("スギ", 30),
    ("ヒノキ", 50),
    ("アテ", 40),
    ("広葉樹", 60),
    ("その他", 10),
    (None, 0)
]
for sp, age in test_cases:
    h = estimate_canopy_height(sp, age)
    print(f" - 樹種: {sp}, 林齢: {age}年 -> 推定樹高 (DCHM): {h} m")
