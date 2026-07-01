@echo off
REM ============================================================
REM  MCU_TRACE 一键推送（公司网绕封 GitHub 方案）
REM
REM  原理：
REM    - 启动本地 TCP tunnel (127.0.0.1:8443 -> GitHub IP:443)
REM    - SSH config 已把 github.com 路由到 127.0.0.1:8443
REM    - git push 走 SSH 协议经 tunnel 出去
REM    - 推完自动关 tunnel
REM
REM  使用前提（只需 1 次）：
REM    1. 在 GitHub 浏览器上 (https://github.com/settings/keys)
REM       添加 ~/.ssh/id_rsa.pub 完整内容
REM    2. 在 GitHub 浏览器上 (https://github.com/new)
REM       创建空仓库 mafuxuan/MCU_TRACE (Private)
REM       ⚠️ 不要勾选 Add README/.gitignore/license
REM
REM  之后每次推送只需运行本脚本即可。
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo  MCU_TRACE 一键推送 (via GitHub tunnel)
echo ============================================================
echo.

REM 启动 tunnel (后台)
echo [1/4] 启动 GitHub tunnel...
start "github_tunnel" /min python tools\github_tunnel.py
timeout /t 2 /nobreak >nul
echo    tunnel 已后台启动
echo.

REM 测试 SSH 连接
echo [2/4] 测试 GitHub SSH 连接（应看到 "Hi mafuxuan! ..."）...
ssh -T -o ConnectTimeout=10 git@github.com
echo.

REM 推送
echo [3/4] 推送到 origin/main...
git push -u origin main
set PUSH_ERR=%errorlevel%

REM 关闭 tunnel
echo.
echo [4/4] 关闭 tunnel...
taskkill /F /FI "WINDOWTITLE eq github_tunnel*" 2>nul

if %PUSH_ERR% neq 0 (
    echo.
    echo   [错误] 推送失败！可能原因：
    echo     1. GitHub 仓库未创建 (https://github.com/new)
    echo     2. SSH key 未添加到 GitHub (https://github.com/settings/keys)
    echo     3. tunnel 连接失败（IP 段可能变化）
    echo.
    echo   详细: GITHUB_SETUP.md
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  ✓ 推送成功！
echo  仓库地址: https://github.com/mafuxuan/MCU_TRACE
echo ============================================================
pause
