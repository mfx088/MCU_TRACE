@echo off
REM ============================================================
REM  MCU_TRACE 一键推送 (v0.2.3 + keep-alive fix)
REM
REM  改进点：加了 GIT_SSH_COMMAND keep-alive 避免 tunnel 被限流
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo  MCU_TRACE 一键推送 (via GitHub tunnel)
echo ============================================================
echo.

REM 关旧 tunnel
taskkill /F /IM python.exe 2>nul >nul
timeout /t 2 /nobreak >nul

REM 启 tunnel
echo [1/4] 启动 GitHub tunnel...
start "github_tunnel" /min python tools\github_tunnel.py
timeout /t 3 /nobreak >nul

REM 设 keep-alive SSH
set GIT_SSH_COMMAND=ssh -o ServerAliveInterval=20 -o ServerAliveCountMax=5 -o TCPKeepAlive=yes

REM 测 SSH
echo [2/4] 测试 GitHub SSH 连接（应看到 "Hi mfx088! ..."）...
ssh -T -o ConnectTimeout=15 git@github.com
echo.

REM 推送
echo [3/4] 推送到 origin/main...
git push -u origin main
set PUSH_ERR=%errorlevel%

REM 关 tunnel
echo.
echo [4/4] 关闭 tunnel...
taskkill /F /IM python.exe 2>nul

if %PUSH_ERR% neq 0 (
    echo.
    echo   [错误] 推送失败！可能原因：
    echo     1. 还在公司网 (tunnel IP 可能被限流，重试几次)
    echo     2. GitHub 仓库未创建 (https://github.com/new)
    echo     3. SSH key 未添加到 GitHub (https://github.com/settings/keys)
    echo     4. tunnel 连接失败（IP 段可能变化）
    echo.
    echo   详细: GITHUB_SETUP.md
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  ✓ 推送成功！
echo  仓库地址: https://github.com/mfx088/MCU_TRACE
echo ============================================================
pause
