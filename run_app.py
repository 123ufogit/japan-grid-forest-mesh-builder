# -*- coding: utf-8 -*-
"""
全国 1/2,500 公共測量図郭 & 20m 森林資源メッシュ全自動構築 GUI Web App
ワンクリック起動スクリプト (安全設計版)
"""

import os
import sys
import uvicorn

# 標準出力を UTF-8 に再設定 (Windows コンソールでの UnicodeEncodeError 対策)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

if __name__ == "__main__":
    print("================================================================")
    print("  Japan GIS Grid & Forest Mesh Builder Web GUI")
    print("  URL: http://localhost:8000 (http://127.0.0.1:8000)")
    print("================================================================")
    
    # 127.0.0.1 および 0.0.0.0 の両対応でバインド
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
