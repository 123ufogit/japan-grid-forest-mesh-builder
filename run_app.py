# -*- coding: utf-8 -*-
"""
全国 1/2,500 公共測量図郭 & 国土地理院 DEM (5m/10m) / 傾斜分布図全自動構築 GUI Web App
ワンクリック起動スクリプト (安全設計版)
"""

import os
import sys
import socket
import uvicorn

# 標準出力を UTF-8 に再設定 (Windows コンソールでの UnicodeEncodeError 対策)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0

if __name__ == "__main__":
    port = 8000
    host = "127.0.0.1"

    if is_port_in_use(port, host):
        print(f"[WARNING] ポート {port} は既に使用されています。別ポート (8001) で試行します...")
        port = 8001
        if is_port_in_use(port, host):
            print(f"[ERROR] ポート 8000 および 8001 が既に他のプロセスで使用されています。")
            sys.exit(1)

    print("================================================================")
    print("  Japan GIS Grid & DEM / Slope Map Builder Web GUI")
    print(f"  URL: http://127.0.0.1:{port} (または http://localhost:{port})")
    print("================================================================")
    
    try:
        uvicorn.run("app.main:app", host=host, port=port, reload=False, log_level="info")
    except Exception as e:
        print(f"[ERROR] サーバーの起動中にエラーが発生しました: {e}")
        sys.exit(1)

