# -*- coding: utf-8 -*-
"""
日本語市区町村名から純粋 ASCII ローマ字（ヘボン式）ヘ変換するヘルパーモジュール
"""

import re
import unicodedata

# 主要市区町村および文字置換マップ
MUNI_ROMAJI_MAP = {
    # 石川県
    "金沢市": "kanazawa", "七尾市": "nanao", "小松市": "komatsu", "輪島市": "wajima", "珠洲市": "suzu",
    "加賀市": "kaga", "羽咋市": "hakui", "かほく市": "kahoku", "白山市": "hakusan", "能美市": "nomi",
    "野々市市": "nonoichi", "川北町": "kawakita", "津幡町": "tsubata", "内灘町": "uchinada",
    "志賀町": "shika", "宝達志水町": "hodatsushimizu", "中能登町": "nakanoto", "穴水町": "anamizu", "能登町": "noto",
    # 東京都
    "千代田区": "chiyoda", "中央区": "chuo", "港区": "minato", "新宿区": "shinjuku", "文京区": "bunkyo",
    "台東区": "taito", "墨田区": "sumida", "江東区": "koto", "品川区": "shinagawa", "目黒区": "meguro",
    "大田区": "ota", "世田谷区": "setagaya", "渋谷区": "shibuya", "中野区": "nakano", "杉並区": "suginami",
    "豊島区": "toshima", "北区": "kita", "荒川区": "arakawa", "板橋区": "itabashi", "練馬区": "nerima",
    "足立区": "adachi", "葛飾区": "katsushika", "江戸川区": "edogawa", "八王子市": "hachioji", "立川市": "tachikawa",
    "武蔵野市": "musashino", "三鷹市": "mitaka", "青梅市": "ome", "府中市": "fuchu", "昭島市": "akishima",
    "調布市": "chofu", "町田市": "machida", "小金井市": "koganei", "小平市": "kodaira", "日野市": "hino",
    "東村山市": "higashimurayama", "国分寺市": "kokubunji", "国立市": "kunitachi", "福生市": "fussa",
    "狛江市": "komae", "東大和市": "higashiyamato", "清瀬市": "kiyose", "東久留米市": "higashikurume",
    "武蔵村山市": "musashimurayama", "多摩市": "tama", "稲城市": "inagi", "羽村市": "hamura",
    "あきる野市": "akiruno", "西東京市": "nishitokyo",
    # 大阪府
    "大阪市": "osaka", "堺市": "sakai", "岸和田市": "kishiwada", "豊中市": "toyonaka", "池田市": "ikeda",
    "吹田市": "suita", "泉大津市": "izumiotsu", "高槻市": "takatsuki", "貝塚市": "kaizuka", "守口市": "moriguchi",
    "枚方市": "hirakata", "茨木市": "ibaraki", "八尾市": "yao", "泉佐野市": "izumisano", "富田林市": "tondabayashi",
    "寝屋川市": "neyagawa", "河内長野市": "kawachinagano", "松原市": "matsubara", "大東市": "daito",
    "和泉市": "izumi", "箕面市": "minoh", "柏原市": "kashiwara", "羽曳野市": "habikino", "門真市": "kadoma",
    "摂津市": "settsu", "高石市": "takaishi", "藤井寺市": "fujiidera", "東大阪市": "higashiosaka",
    "泉南市": "sennan", "四條畷市": "shijonawate", "交野市": "katano", "大阪狭山市": "osakasayama", "阪南市": "hannan"
}

def kanji_to_romaji(text: str) -> str:
    """
    市区町村名を純粋 ASCII アルファベット小文字に変換
    """
    if not text:
        return "area"

    if text in MUNI_ROMAJI_MAP:
        return MUNI_ROMAJI_MAP[text]

    # マップ未登録の場合の安全な ASCII 抽出
    normalized = unicodedata.normalize('NFKD', text)
    ascii_only = re.sub(r'[^a-zA-Z0-9_]', '', normalized)
    
    if ascii_only:
        return ascii_only.lower()

    # ハッシュ等によるフォールバック ASCII 識別子生成
    import hashlib
    h = hashlib.md5(text.encode('utf-8')).hexdigest()[:6]
    return f"city_{h}"
