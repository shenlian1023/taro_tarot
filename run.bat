@echo off
chcp 65001 > nul

echo ===============================
echo 啟動 Tarot 系統
echo ===============================

REM 用 start 讓 python 在背景跑
start "" python main.py

REM 等 2 秒讓 server 起來
timeout /t 2 /nobreak > nul

REM 開瀏覽器
start http://localhost:8080