@echo off
REM =====================================================================
REM 实验室局域网 — Windows 一键启动（开发机/实验室电脑本机部署）
REM 适用：参与者在同一网段，浏览器打开 http://<本机内网IP>:5173 即可使用。
REM
REM ⚠️ 与前端的"开发调试"共用端口 8000 / 5173。若本机已在跑
REM    "uvicorn 127.0.0.1:8000" 或 "vite 127.0.0.1:5173"，请先结束它们
REM    （否则本脚本会因端口被占用而启动失败）。
REM
REM 启动后会开两个独立窗口：后端(8000) + 前端(5173)。关闭窗口即停止。
REM =====================================================================

setlocal
REM —— 项目根目录（按实际位置修改，下面两行一般不用动）——
set "PROJECT_DIR=D:\27475\WorkBuddy-搭建网站\travel-experiment-platform"
set "NODE_EXE=C:\Users\27475\.workbuddy\binaries\node\versions\22.12.0\npm.cmd"

REM —— 步骤 0：确认 CORS 已放行局域网访问的前端地址 ——
REM 参与者通过 http://<本机IP>:5173 访问，后端 CORS 必须包含该地址，否则请求被拦。
REM 先查本机内网 IP：
for /f "tokens=4" %%a in ('route print ^| findstr 0.0.0.0 ^| findstr 0.0.0.0') do (
  set "LAN_IP=%%a" & goto :gotip
)
:gotip
echo 本机内网 IP 疑似：%LAN_IP%
echo 请将 backend\.env 的 CORS_ORIGINS 加上： http://%LAN_IP%:5173
echo （例如 CORS_ORIGINS=http://%LAN_IP%:5173,http://localhost:5173）
pause

REM —— 启动后端（绑 0.0.0.0 允许局域网访问，单 worker 避免重复发信）——
start "后端 uvicorn 8000" cmd /k "cd /d %PROJECT_DIR%\backend && venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level info"

REM —— 启动前端开发服务器（绑 0.0.0.0 允许局域网访问）——
start "前端 vite 5173" cmd /k "cd /d %PROJECT_DIR%\frontend && set NODE_OPTIONS= && %NODE_EXE% run dev -- --host 0.0.0.0 --port 5173"

echo.
echo 已启动两个窗口。参与者访问地址： http://%LAN_IP%:5173
echo 关闭这两个窗口即可停止服务。
endlocal
