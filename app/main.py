# -*- coding: utf-8 -*-
"""
全国対応 公共測量図郭 & 森林資源メッシュ全自動構築 GUI Web App
FastAPI バックエンドメインサーバー (GeoJSON 完全一本化版)
"""

import os
import sys
import json
import asyncio
import zipfile
import numpy as np
from typing import Dict, Any, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse, Response
import geopandas as gpd

from app.core.prefectures import PREFECTURE_MASTER, get_pref_info, get_municipalities
from app.core.pipeline import PipelineRunner, TaskCanceledException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(
    title="全国公共測量図郭 & 森林資源メッシュ構築ツール",
    description="全47都道府県対応 1/2,500図郭および20m森林メッシュ一括構築パイプライン (GeoJSON 形式)",
    version="2.0.0"
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_BASE_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)

static_dir = os.path.join(BASE_DIR, "app", "static")
templates_dir = os.path.join(BASE_DIR, "app", "templates")
os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

current_task_status: Dict[str, Any] = {
    "status": "idle",
    "pref_code": None,
    "pref_name": None,
    "city_name": None,
    "progress": 0,
    "current_message": "待機中",
    "result": None,
    "error": None,
    "cancel_requested": False
}

log_queue = asyncio.Queue()

def log_event_sync(msg: str, pct: int = 0):
    current_task_status["current_message"] = msg
    current_task_status["progress"] = pct
    print(f"[{pct}%] {msg}")
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                log_queue.put({"msg": msg, "pct": pct, "status": current_task_status["status"]}), loop
            )
    except Exception:
        pass

def is_cancel_requested() -> bool:
    return current_task_status.get("cancel_requested", False)

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"prefectures": PREFECTURE_MASTER})

@app.get("/api/prefectures")
async def get_prefectures_api():
    return JSONResponse(content=PREFECTURE_MASTER)

@app.get("/api/municipalities/{pref_code}")
async def get_municipalities_api(pref_code: str):
    cities = get_municipalities(pref_code)
    return JSONResponse(content={"pref_code": pref_code, "municipalities": cities})

@app.get("/api/status")
async def get_status():
    return JSONResponse(content=current_task_status)

@app.get("/api/stream-logs")
async def stream_logs():
    async def event_generator():
        while True:
            data = await log_queue.get()
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

def run_pipeline_task(pref_code: str, city_name: Optional[str] = None):
    global current_task_status
    pref_info = get_pref_info(pref_code)
    if not pref_info:
        current_task_status["status"] = "error"
        current_task_status["error"] = "都道府県が見つかりません"
        return

    current_task_status["status"] = "running"
    current_task_status["pref_code"] = pref_code
    current_task_status["pref_name"] = pref_info["name"]
    current_task_status["city_name"] = city_name
    current_task_status["progress"] = 0
    current_task_status["error"] = None
    current_task_status["cancel_requested"] = False

    try:
        runner = PipelineRunner(
            pref_code,
            OUTPUT_BASE_DIR,
            city_name=city_name,
            auto_cleanup=True,
            log_callback=log_event_sync,
            cancel_check=is_cancel_requested
        )
        res = runner.run()
        current_task_status["status"] = "completed"
        current_task_status["result"] = res
        current_task_status["progress"] = 100
        log_event_sync("✓ 全工程が正常に完了いたしました！", 100)
    except TaskCanceledException:
        current_task_status["status"] = "canceled"
        current_task_status["error"] = "ユーザーによって処理が中止されました"
        log_event_sync("⛔ 処理がユーザーによって中止されました", current_task_status["progress"])
    except Exception as e:
        current_task_status["status"] = "error"
        current_task_status["error"] = str(e)
        log_event_sync(f"エラーが発生しました: {e}", current_task_status["progress"])

@app.post("/api/process/{pref_code}")
async def start_process(pref_code: str, background_tasks: BackgroundTasks, city_name: Optional[str] = Query(None)):
    global current_task_status
    if current_task_status["status"] == "running":
        raise HTTPException(status_code=400, detail="現在別のパイプラインタスクが実行中です。")

    current_task_status["cancel_requested"] = False
    background_tasks.add_task(run_pipeline_task, pref_code, city_name)
    return JSONResponse(content={"message": "タスクを開始しました", "pref_code": pref_code, "city_name": city_name})

@app.post("/api/cancel")
async def cancel_process():
    global current_task_status
    if current_task_status["status"] == "running":
        current_task_status["cancel_requested"] = True
        log_event_sync("⚠️ 処理の中止が要求されました。安全に停止しています...", current_task_status["progress"])
        return JSONResponse(content={"message": "中止要求を受け付けました"})
    return JSONResponse(content={"message": "実行中のタスクはありません"})

@app.get("/api/download/{pref_code}")
async def download_zip(pref_code: str, city_name: Optional[str] = Query(None)):
    pref_info = get_pref_info(pref_code)
    if not pref_info:
        raise HTTPException(status_code=404, detail="都道府県が見つかりません")

    if current_task_status.get("result") and current_task_status["result"].get("zip_path"):
        zip_p = current_task_status["result"]["zip_path"]
        if os.path.exists(zip_p):
            return FileResponse(zip_p, media_type="application/zip", filename=os.path.basename(zip_p))

    pref_name = pref_info["name"]
    target_dirs = []
    
    if city_name and city_name != "ALL":
        target_dirs.append(os.path.join(OUTPUT_BASE_DIR, f"output_{pref_code}_{pref_name}_{city_name}"))
    target_dirs.append(os.path.join(OUTPUT_BASE_DIR, f"output_{pref_code}_{pref_name}"))

    found_target_dir = None
    for d in target_dirs:
        if os.path.exists(d):
            found_target_dir = d
            break

    if not found_target_dir:
        raise HTTPException(status_code=404, detail="成果物ディレクトリが見つかりません。処理を実行してください。")

    spatial_dir = os.path.join(found_target_dir, "spatial_layers_by_zukaku")
    if not os.path.exists(spatial_dir):
        spatial_dir = os.path.join(found_target_dir, "geojson_by_zukaku")
    if not os.path.exists(spatial_dir):
        spatial_dir = os.path.join(found_target_dir, "gpkg_by_zukaku")

    if not os.path.exists(spatial_dir):
        raise HTTPException(status_code=404, detail="成果物ファイルが存在しません。処理を実行してください。")

    # ZIP ファイルの検索または生成
    zip_filepath = None
    for f in os.listdir(found_target_dir):
        if f.endswith(".zip"):
            zip_filepath = os.path.join(found_target_dir, f)
            break

    if not zip_filepath or not os.path.exists(zip_filepath):
        zip_filename = os.path.basename(found_target_dir).replace("output_", "") + "_spatial_pack.zip"
        zip_filepath = os.path.join(found_target_dir, zip_filename)
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(spatial_dir):
                for fn in files:
                    fp = os.path.join(root, fn)
                    rel_p = os.path.relpath(fp, spatial_dir)
                    zf.write(fp, arcname=os.path.join("spatial_layers_by_zukaku", rel_p))

    return FileResponse(zip_filepath, media_type="application/zip", filename=os.path.basename(zip_filepath))

@app.get("/api/boundary-polygon/{pref_code}")
async def get_boundary_polygon(pref_code: str, city_name: Optional[str] = Query(None)):
    """
    指定自治体・都道府県の境界 GeoJSON (EPSG:4326) を取得 (選択時ズームイン用)
    """
    from app.core.boundary import fetch_boundary_geojson
    try:
        c_name = city_name if (city_name and city_name != "ALL") else None
        gdf = fetch_boundary_geojson(pref_code, c_name)
        if gdf is not None and len(gdf) > 0:
            features = []
            for idx, row in gdf.iterrows():
                features.append({
                    "type": "Feature",
                    "geometry": row.geometry.__geo_interface__,
                    "properties": {"name": c_name or pref_code}
                })
            return JSONResponse(content={"type": "FeatureCollection", "features": features})
        raise HTTPException(status_code=404, detail="境界 GeoJSON を取得できませんでした")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/live-zukaku/{pref_code}")
async def get_live_zukaku(pref_code: str, city_name: Optional[str] = Query(None)):
    """
    処理中・処理済みの 1/2,500 図郭メッシュ GeoJSON をリアルタイム取得
    """
    pref_info = get_pref_info(pref_code)
    if not pref_info:
        raise HTTPException(status_code=404, detail="都道府県が見つかりません")

    pref_name = pref_info["name"]
    target_label_id = f"{pref_code}_{pref_name}_{city_name}" if (city_name and city_name != "ALL") else f"{pref_code}_{pref_name}"
    target_dir = os.path.join(OUTPUT_BASE_DIR, f"output_{target_label_id}")

    zukaku_json_path = os.path.join(target_dir, f"{target_label_id}_zukaku_2500.geojson")
    if os.path.exists(zukaku_json_path):
        with open(zukaku_json_path, "r", encoding="utf-8") as f:
            raw = f.read()
        return Response(content=raw, media_type="application/json")

    raise HTTPException(status_code=404, detail="ライブ図郭メッシュがまだ生成されていません")

@app.get("/api/preview/{pref_code}")
async def preview_boundary(pref_code: str, city_name: Optional[str] = Query(None)):
    pref_info = get_pref_info(pref_code)
    if not pref_info:
        raise HTTPException(status_code=404, detail="都道府県が見つかりません")

    pref_name = pref_info["name"]
    target_label_id = f"{pref_code}_{pref_name}_{city_name}" if (city_name and city_name != "ALL") else f"{pref_code}_{pref_name}"
    
    target_dirs = [
        os.path.join(OUTPUT_BASE_DIR, f"output_{target_label_id}"),
        os.path.join(OUTPUT_BASE_DIR, f"output_{pref_code}_{pref_name}")
    ]

    master_path = None
    for d in target_dirs:
        for folder_name in ["spatial_layers_by_zukaku", "geojson_by_zukaku", "gpkg_by_zukaku"]:
            s_d = os.path.join(d, folder_name)
            if os.path.exists(s_d):
                for fn in os.listdir(s_d):
                    if fn.startswith("zukaku_2500_master_") or fn.endswith("boundary_all.geojson") or fn.endswith("boundary_master.geojson") or fn.endswith("boundary_all.gpkg"):
                        master_path = os.path.join(s_d, fn)
                        break
            if master_path:
                break
        if master_path:
            break

    if not master_path or not os.path.exists(master_path):
        raise HTTPException(status_code=404, detail="プレビュー用データが存在しません")

    try:
        if master_path.endswith(".geojson"):
            with open(master_path, "r", encoding="utf-8") as f:
                raw_json_str = f.read()
            return Response(content=raw_json_str, media_type="application/json")
        else:
            gdf = gpd.read_file(master_path, engine="pyogrio").to_crs(epsg=4326)
            features = []
            for idx, row in gdf.iterrows():
                props = {}
                for col in row.index:
                    if col != "geometry":
                        val = row[col]
                        if isinstance(val, (float, np.floating)) and np.isnan(val):
                            props[col] = None
                        else:
                            props[col] = val
                features.append({
                    "type": "Feature",
                    "geometry": row.geometry.__geo_interface__,
                    "properties": props
                })
            geojson_data = {"type": "FeatureCollection", "features": features}
            return JSONResponse(content=geojson_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
