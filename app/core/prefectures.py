# -*- coding: utf-8 -*-
"""
全国 47 都道府県と JGD2011 平面直角座標系 (第1系〜第19系) のマスター設定
および英字ローマ字表記、市区町村リスト取得機能
"""

import requests
from app.core.municipality_data import MUNICIPALITY_MASTER

PREFECTURE_MASTER = [
    {"code": "01", "name": "北海道", "romaji": "hokkaido", "system": 1, "epsg": 6669, "region": "北海道", "mesh_key": "mesh_1"},
    {"code": "02", "name": "青森県", "romaji": "aomori", "system": 10, "epsg": 6678, "region": "東北", "mesh_key": "mesh_10"},
    {"code": "03", "name": "岩手県", "romaji": "iwate", "system": 10, "epsg": 6678, "region": "東北", "mesh_key": "mesh_10"},
    {"code": "04", "name": "宮城県", "romaji": "miyagi", "system": 10, "epsg": 6678, "region": "東北", "mesh_key": "mesh_10"},
    {"code": "05", "name": "秋田県", "romaji": "akita", "system": 10, "epsg": 6678, "region": "東北", "mesh_key": "mesh_10"},
    {"code": "06", "name": "山形県", "romaji": "yamagata", "system": 10, "epsg": 6678, "region": "東北", "mesh_key": "mesh_10"},
    {"code": "07", "name": "福島県", "romaji": "fukushima", "system": 10, "epsg": 6678, "region": "東北", "mesh_key": "mesh_10"},
    {"code": "08", "name": "茨城県", "romaji": "ibaraki", "system": 9, "epsg": 6677, "region": "関東", "mesh_key": "mesh_9"},
    {"code": "09", "name": "栃木県", "romaji": "tochigi", "system": 9, "epsg": 6677, "region": "関東", "mesh_key": "mesh_9"},
    {"code": "10", "name": "群馬県", "romaji": "gunma", "system": 9, "epsg": 6677, "region": "関東", "mesh_key": "mesh_9"},
    {"code": "11", "name": "埼玉県", "romaji": "saitama", "system": 9, "epsg": 6677, "region": "関東", "mesh_key": "mesh_9"},
    {"code": "12", "name": "千葉県", "romaji": "chiba", "system": 9, "epsg": 6677, "region": "関東", "mesh_key": "mesh_9"},
    {"code": "13", "name": "東京都", "romaji": "tokyo", "system": 9, "epsg": 6677, "region": "関東", "mesh_key": "mesh_9"},
    {"code": "14", "name": "神奈川県", "romaji": "kanagawa", "system": 9, "epsg": 6677, "region": "関東", "mesh_key": "mesh_9"},
    {"code": "15", "name": "新潟県", "romaji": "niigata", "system": 8, "epsg": 6676, "region": "中部", "mesh_key": "mesh_8"},
    {"code": "16", "name": "富山県", "romaji": "toyama", "system": 7, "epsg": 6675, "region": "中部", "mesh_key": "mesh_7"},
    {"code": "17", "name": "石川県", "romaji": "ishikawa", "system": 7, "epsg": 6675, "region": "中部", "mesh_key": "mesh_7"},
    {"code": "18", "name": "福井県", "romaji": "fukui", "system": 7, "epsg": 6675, "region": "中部", "mesh_key": "mesh_7"},
    {"code": "19", "name": "山梨県", "romaji": "yamanashi", "system": 8, "epsg": 6676, "region": "中部", "mesh_key": "mesh_8"},
    {"code": "20", "name": "長野県", "romaji": "nagano", "system": 8, "epsg": 6676, "region": "中部", "mesh_key": "mesh_8"},
    {"code": "21", "name": "岐阜県", "romaji": "gifu", "system": 7, "epsg": 6675, "region": "中部", "mesh_key": "mesh_7"},
    {"code": "22", "name": "静岡県", "romaji": "shizuoka", "system": 8, "epsg": 6676, "region": "中部", "mesh_key": "mesh_8"},
    {"code": "23", "name": "愛知県", "romaji": "aichi", "system": 7, "epsg": 6675, "region": "中部", "mesh_key": "mesh_7"},
    {"code": "24", "name": "三重県", "romaji": "mie", "system": 7, "epsg": 6675, "region": "近畿", "mesh_key": "mesh_7"},
    {"code": "25", "name": "滋賀県", "romaji": "shiga", "system": 6, "epsg": 6674, "region": "近畿", "mesh_key": "mesh_6"},
    {"code": "26", "name": "京都府", "romaji": "kyoto", "system": 6, "epsg": 6674, "region": "近畿", "mesh_key": "mesh_6"},
    {"code": "27", "name": "大阪府", "romaji": "osaka", "system": 6, "epsg": 6674, "region": "近畿", "mesh_key": "mesh_6"},
    {"code": "28", "name": "兵庫県", "romaji": "hyogo", "system": 5, "epsg": 6673, "region": "近畿", "mesh_key": "mesh_5"},
    {"code": "29", "name": "奈良県", "romaji": "nara", "system": 6, "epsg": 6674, "region": "近畿", "mesh_key": "mesh_6"},
    {"code": "30", "name": "和歌山県", "romaji": "wakayama", "system": 6, "epsg": 6674, "region": "近畿", "mesh_key": "mesh_6"},
    {"code": "31", "name": "鳥取県", "romaji": "tottori", "system": 5, "epsg": 6673, "region": "中国", "mesh_key": "mesh_5"},
    {"code": "32", "name": "島根県", "romaji": "shimane", "system": 5, "epsg": 6673, "region": "中国", "mesh_key": "mesh_5"},
    {"code": "33", "name": "岡山県", "romaji": "okayama", "system": 5, "epsg": 6673, "region": "中国", "mesh_key": "mesh_5"},
    {"code": "34", "name": "広島県", "romaji": "hiroshima", "system": 4, "epsg": 6672, "region": "中国", "mesh_key": "mesh_4"},
    {"code": "35", "name": "山口県", "romaji": "yamaguchi", "system": 3, "epsg": 6671, "region": "中国", "mesh_key": "mesh_3"},
    {"code": "36", "name": "徳島県", "romaji": "tokushima", "system": 4, "epsg": 6672, "region": "四国", "mesh_key": "mesh_4"},
    {"code": "37", "name": "香川県", "romaji": "kagawa", "system": 4, "epsg": 6672, "region": "四国", "mesh_key": "mesh_4"},
    {"code": "38", "name": "愛媛県", "romaji": "ehime", "system": 4, "epsg": 6672, "region": "四国", "mesh_key": "mesh_4"},
    {"code": "39", "name": "高知県", "romaji": "kochi", "system": 4, "epsg": 6672, "region": "四国", "mesh_key": "mesh_4"},
    {"code": "40", "name": "福岡県", "romaji": "fukuoka", "system": 2, "epsg": 6670, "region": "九州", "mesh_key": "mesh_2"},
    {"code": "41", "name": "佐賀県", "romaji": "saga", "system": 2, "epsg": 6670, "region": "九州", "mesh_key": "mesh_2"},
    {"code": "42", "name": "長崎県", "romaji": "nagasaki", "system": 2, "epsg": 6670, "region": "九州", "mesh_key": "mesh_2"},
    {"code": "43", "name": "熊本県", "romaji": "kumamoto", "system": 2, "epsg": 6670, "region": "九州", "mesh_key": "mesh_2"},
    {"code": "44", "name": "大分県", "romaji": "oita", "system": 2, "epsg": 6670, "region": "九州", "mesh_key": "mesh_2"},
    {"code": "45", "name": "宮崎県", "romaji": "miyazaki", "system": 2, "epsg": 6670, "region": "九州", "mesh_key": "mesh_2"},
    {"code": "46", "name": "鹿児島県", "romaji": "kagoshima", "system": 2, "epsg": 6670, "region": "九州", "mesh_key": "mesh_2"},
    {"code": "47", "name": "沖縄県", "romaji": "okinawa", "system": 15, "epsg": 6683, "region": "沖縄", "mesh_key": "mesh_15"},
]

PREF_MAP = {p["name"]: p for p in PREFECTURE_MASTER}
PREF_CODE_MAP = {p["code"]: p for p in PREFECTURE_MASTER}

def get_pref_info(pref_name_or_code: str):
    """
    都道府県名またはコードからマスター情報を取得
    """
    if pref_name_or_code in PREF_MAP:
        return PREF_MAP[pref_name_or_code]
    if pref_name_or_code in PREF_CODE_MAP:
        return PREF_CODE_MAP[pref_name_or_code]
    for p in PREFECTURE_MASTER:
        if p["name"].startswith(pref_name_or_code) or pref_name_or_code in p["name"]:
            return p
    return None

def get_municipalities(pref_code: str):
    """
    指定都道府県の市区町村一覧を取得
    """
    return MUNICIPALITY_MASTER.get(pref_code, [])

def to_ascii_identifier(text: str) -> str:
    """
    文字列を純粋な ASCII 英数字＋アンダースコア識別子に変換
    """
    import re
    # 非 ASCII 文字を除去/置換
    res = re.sub(r'[^a-zA-Z0-9_]', '', text)
    return res if res else "area"
