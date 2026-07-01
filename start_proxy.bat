@echo off
REM ============================================================
REM  MCU_TRACE 一键推送（公司网绕封 GitHub 方案，v0.2.3）
REM
REM  原理：
REM    - 启本地 TCP tunnel (127.0.0.1:8443 → 20.205.243.x:443) 让 SSH 走通
REM    - 启本地 HTTP CONNECT 代理 (127.0.0.1:8444) 让浏览器/curl 走通
REM    - SSH config 已把 github.com 路由到 127.0.0.1:8443
REM    - 用 ed25519 key (用户 GitHub 账号: mfx088)
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo  MCU_TRACE 推送准备 (v0.2.3)
echo ============================================================
echo.

REM 关闭旧 tunnel/proxy
taskkill /F /IM python.exe 2>nul >nul
timeout /t 1 /nobreak >nul

REM 启 tunnel
echo [1/3] 启动 TCP tunnel (127.0.0.1:8443 → 20.205.243.x:443)...
start "github_tunnel" /min python tools\github_tunnel.py
timeout /t 2 /nobreak >nul

REM 启 HTTP CONNECT 代理
echo [2/3] 启动 HTTP CONNECT 代理 (127.0.0.1:8444)...
start "http_proxy" /min python tools\http_proxy.py
timeout /t 2 /nobreak >nul

REM 测 SSH
echo [3/3] 测试 GitHub SSH 认证 (应看到 "Hi mfx088! ...")...
ssh -T -o ConnectTimeout=10 git@github.com
echo.

echo ============================================================
echo  ✓ 准备完成
echo.
echo  [Git Push 方式 - 走 tunnel]
echo    跑 .\push.bat 一键推代码
echo.
echo  [浏览器创建仓库 - 走 HTTP CONNECT 代理]
echo    配置浏览器 HTTP/HTTPS 代理 = 127.0.0.1:8444
echo    然后访问 https://github.com/new
echo    ⚠️ 创建后保持这个代理开着 (后台)
echo.
echo  [curl 走代理调 API]
echo    set HTTP_PROXY=http://127.0.0.1:8444
echo    curl -x http://127.0.0.1:8444 https://api.github.com/...
echo.
echo  [关闭后台]
echo    taskkill /F /IM python.exe
echo ============================================================
pause
