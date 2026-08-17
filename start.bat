@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

title Japan GIS Grid & DEM / Slope Map Builder Web GUI

echo ================================================================
echo   Japan GIS Grid and DEM / Slope Map Builder Web GUI
echo ================================================================

echo.

uv run python run_app.py

pause


