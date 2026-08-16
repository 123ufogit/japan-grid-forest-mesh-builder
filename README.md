# 🌲 全国公共測量図郭 & 森林資源メッシュ全自動構築ツール (Japan GIS Grid & Forest Mesh Builder)

全47都道府県の **1/2,500 公共測量図郭 GeoJSON** および **20m 森林資源メッシュ GeoPackage (.gpkg)** を自動解析・空間結合し、Web GUI 上でリアルタイムに可視化・パッケージ構築するオープンソース GIS ツールです。

---

## ✨ 主な特長

* 🗺️ **全47都道府県 & 市町村別厳密抽出**  
  JIS 自治体コード（例: 福岡県 糸島市, 石川県 野々市市 等）に基づいて境界ポリゴンを自動取得し、高精度空間交差判定 (`intersects` / `make_valid`) により対象領域の図郭のみをピンポイント抽出。
* 📊 **「20mメッシュ情報」自動判定 & 3色別マッププレビュー**  
  図郭内の 20m メッシュデータ存在状況を自動判定（🟢 **取得** / 🟠 **一部取得** / ⚪ **未取得**）し、Leaflet マップ上に鮮やかにリアルタイム色分け描画。
* ⚡ **100vh スクロール不要のモダン GUI**  
  操作パネル、進捗ログ、大画面リアルタイム可視化マップが一画面に収まるレスポンシブ・フルビューレイアウトを採用。
* 📦 **GIS 互換性を確保した ASCII 出力 & 行政境界 GeoJSON 同梱**  
  QGIS / ArcGIS / GDAL 等での文字化けやトラブルを防ぐため、全成果物ファイル名を完全 ASCII (アルファベット) に統一。ZIP パック内には選択した自治体の行政境界 GeoJSON も自動同梱。
* 🚀 **`uv` 前提の高速パッケージ管理**  
  `uv` に対応し、依存関係のインストールからサーバー起動まで一発で実行可能。

---

## 💻 動作環境・必須ツール

* **Python**: `3.10` 以上
* **パッケージマネージャー**: [`uv`](https://github.com/astral-sh/uv) (おすすめ) または `pip`

---

## 🚀 クイックスタート (`uv` を使用する場合)

### 1. リポジトリのクローン
```bash
git clone https://github.com/YOUR_USERNAME/japan-grid-forest-mesh-builder.git
cd japan-grid-forest-mesh-builder
```

### 2. 依存関係のセットアップ
`uv` を使って一括で仮想環境作成とライブラリインストールを行います：
```bash
uv sync
```

### 3. アプリケーションの起動
```bash
uv run python run_app.py
```

起動後、ブラウザで以下の URL にアクセスしてください：
👉 **http://localhost:8000** (または http://127.0.0.1:8000)

---

## 📁 ディレクトリ構造

```text
.
├── app/
│   ├── core/
│   │   ├── boundary.py       # 自治体・都道府県境界 GeoJSON 取得モジュール
│   │   └── pipeline.py       # 空間交差判定・20mメッシュ結合・7林種集計パイプライン
│   ├── static/
│   │   ├── app.js            # フロントエンド Leaflet マップ & SSE ログリアルタイム描画
│   │   └── style.css         # 100vh フルビュー・ダークテーマ CSS
│   ├── templates/
│   │   └── index.html        # Web GUI HTML
│   └── main.py               # FastAPI バックエンドサーバー
├── pyproject.toml            # uv プロジェクト & 依存ライブラリ定義
├── run_app.py                # アプリ起動エントリーポイント
├── README.md                 # ドキュメント (本ファイル)
└── .gitignore                # Git 除外設定ファイル
```

---

## 📄 データ出典・謝意・ライセンス (Data Credits & Licenses)

本ツールはオープンソースソフトウェアおよび各公共機関・オープンデータ提供元によるオープンデータ・成果物を活用して構築されています。

### 1. 外部ライブラリおよびライセンス
本ツールの構築には以下のオープンソースライブラリが使用されています：
* **`japan-basic-section`**: MIT License (公共測量 1/2,500 図郭メッシュ計算)
* **`GeoPandas` / `Shapely` / `PyPROJ` / `PyOGRIO`**: BSD / MIT License (空間データ解析)
* **`FastAPI` / `Uvicorn`**: MIT License (Web バックエンドサーバー)
* **`Leaflet.js`**: BSD 2-Clause License (インタラクティブ Web 地図描画)

### 2. 利用データ・オープンデータ出典表記
本ツールで取得・加工・解析しているデータセットの出典および利用条件は以下の通りです：

* **森林資源メッシュデータ (20mメッシュ)**
  * **出典**: 林野庁「森林資源メッシュデータ」（[G空間情報センター](https://www.geospatial.jp/) 経由で取得）
  * **利用条件**: 利用規約に基づき、出典を明記のうえ加工・分析・成果物利用を行っています。
* **行政区域境界データ**
  * **出典**: 国土交通省「国土数値情報（行政区域データ N03）」（[niiyz/JapanCityGeoJson](https://github.com/niiyz/JapanCityGeoJson) および [amay077/JapanPrefGeoJson](https://github.com/amay077/JapanPrefGeoJson) を参照・利用）
* **背景地図タイル**
  * **出典**: © [OpenStreetMap](https://www.openstreetmap.org/) contributors (ODbL)

### 3. 本ツールのライセンス
本ツールのソースコード自体は **[MIT License](LICENSE)** のもとで公開されています。

---

## 📄 ライセンス本文

```text
MIT License

Copyright (c) 2026 123ufogit

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

