# -*- coding: utf-8 -*-
"""
全国対応 公共測量図郭 & 国土地理院 DEM (5m/10m) / 傾斜分布図 構築 GUI Web App
FastAPI バックエンドメインサーバー
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
from app.core.boundary import fetch_boundary_geojson
from app.core.dem import check_dem_availability
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(
    title="全国公共測量図郭 & 国土地理院DEM/傾斜分布図構築ツール",
    description="全47都道府県対応 1/2,500図郭および国土地理院DEM(5m/10m)・傾斜分布図一括構築パイプライン",
    version="3.0.0"
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
    template = templates.get_template("index.html")
    content = template.render({"request": request, "prefectures": PREFECTURE_MASTER})
    return HTMLResponse(content=content)



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

@app.get("/api/check-dem-availability/{pref_code}")
async def check_dem_availability_api(pref_code: str, city_name: Optional[str] = Query(None)):
    """
    指定自治体において国土地理院 5m/10m DEM が利用可能か高速判定
    """
    try:
        c_name = city_name if (city_name and city_name != "ALL") else None
        gdf = fetch_boundary_geojson(pref_code, c_name)
        if gdf is None or len(gdf) == 0:
            return JSONResponse(content={"5m": False, "10m": True})
        
        bounds = tuple(gdf.to_crs(epsg=4326).total_bounds)
        availability = check_dem_availability(bounds)
        return JSONResponse(content=availability)
    except Exception as e:
        return JSONResponse(content={"5m": False, "10m": True, "error": str(e)})

def run_pipeline_task(
    pref_code: str,
    city_name: Optional[str] = None,
    resolution: str = "5m",
    generate_slope: bool = True,
    analysis_options: dict = None
):
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
            resolution=resolution,
            generate_slope=generate_slope,
            analysis_options=analysis_options,
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
async def start_process(
    pref_code: str,
    background_tasks: BackgroundTasks,
    city_name: Optional[str] = Query(None),
    resolution: str = Query("5m"),
    generate_slope: bool = Query(True),
    aspect: bool = Query(False),
    hillshade: bool = Query(False),
    curvature: bool = Query(False),
    csmap: bool = Query(False),
    twi: bool = Query(False),
    viewshed: bool = Query(False)
):
    global current_task_status
    if current_task_status["status"] == "running":
        raise HTTPException(status_code=400, detail="現在別のパイプラインタスクが実行中です。")

    current_task_status["cancel_requested"] = False
    analysis_opts = {
        "slope": generate_slope,
        "aspect": aspect,
        "hillshade": hillshade,
        "curvature": curvature,
        "csmap": csmap,
        "twi": twi,
        "viewshed": viewshed
    }
    background_tasks.add_task(run_pipeline_task, pref_code, city_name, resolution, generate_slope, analysis_opts)
    return JSONResponse(content={
        "message": "タスクを開始しました",
        "pref_code": pref_code,
        "city_name": city_name,
        "resolution": resolution,
        "analysis_options": analysis_opts
    })


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
        raise HTTPException(status_code=404, detail="成果物ファイルが存在しません。処理を実行してください。")

    # 最新の spatial_layers_by_zukaku 内の全ファイルを ZIP へリアルタイム圧縮
    zip_filename = os.path.basename(found_target_dir).replace("output_", "") + "_dem_spatial_pack.zip"
    zip_filepath = os.path.join(found_target_dir, zip_filename)

    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(spatial_dir):
            for fn in files:
                fp = os.path.join(root, fn)
                rel_p = os.path.relpath(fp, spatial_dir)
                zf.write(fp, arcname=os.path.join("spatial_layers_by_zukaku", rel_p))

    return FileResponse(zip_filepath, media_type="application/zip", filename=os.path.basename(zip_filepath))

@app.get("/api/download-file/{pref_code}/{filename}")
async def download_single_file(pref_code: str, filename: str, city_name: Optional[str] = Query(None)):
    """成果物 GeoTIFF / GeoJSON を個別ダウンロード"""
    pref_info = get_pref_info(pref_code)
    if not pref_info:
        raise HTTPException(status_code=404, detail="都道府県が見つかりません")

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
        raise HTTPException(status_code=404, detail="成果物ディレクトリが見つかりません")

    target_file = os.path.join(found_target_dir, "spatial_layers_by_zukaku", filename)
    if not os.path.exists(target_file):
        raise HTTPException(status_code=404, detail=f"指定されたファイルが見つかりません: {filename}")

    media_type = "image/tiff" if filename.endswith(".tif") else "application/octet-stream"
    return FileResponse(target_file, media_type=media_type, filename=filename)


@app.get("/api/boundary-polygon/{pref_code}")
async def get_boundary_polygon(pref_code: str, city_name: Optional[str] = Query(None)):
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
        s_d = os.path.join(d, "spatial_layers_by_zukaku")
        if os.path.exists(s_d):
            for fn in os.listdir(s_d):
                if fn.startswith("zukaku_2500_master_") or fn.startswith("city_boundary_"):
                    master_path = os.path.join(s_d, fn)
                    break
        if master_path:
            break

    if not master_path or not os.path.exists(master_path):
        raise HTTPException(status_code=404, detail="プレビュー用データが存在しません")

    try:
        with open(master_path, "r", encoding="utf-8") as f:
            raw_json_str = f.read()
        return Response(content=raw_json_str, media_type="application/json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
