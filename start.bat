@echo off
setlocal
:: Windows コンソールを UTF-8 に設定
chcp 65001 > NUL

:: Python の入出力エンコーディングを UTF-8 に強制指定
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

title 全国公共測量図郭 & 森林資源メッシュ構築パイプライン GUI

echo ================================================================
echo   全国公共測量図郭 & 森林資源メッシュ構築 Web GUI
echo ================================================================
echo.
echo [1/2] サーバーを起動中... (http://localhost:8000)
echo.

uv run python run_app.py

if errorlevel 1 (
    echo.
    echo [エラー] サーバーの起動に失敗しました。
    echo 以下の理由が考えられます:
    echo  1. uv マネージャーがインストールされていない
    echo  2. ポート 8000 番が既に他のアプリで使用されている
    echo.
)

pause
