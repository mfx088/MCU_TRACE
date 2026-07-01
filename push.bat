@echo off
REM ============================================================
REM  MCU_TRACE 一键推送到 GitHub
REM
REM  ⚠️ 公司网封了 github.com，必须先切到手机热点！
REM  参考: E:\Git_PJ\CAN_LOG\HANDOVER.md §12
REM
REM  使用前提：
REM    1. 手机开热点，电脑连上
REM    2. GitHub 已加 SSH key (https://github.com/settings/keys)
REM    3. GitHub 已创建空仓库 mafuxuan/MCU_TRACE (Private, 不要勾 README/.gitignore/license)
REM ============================================================

echo.
echo ============================================================
echo  MCU_TRACE 一键推送到 GitHub
echo ============================================================
echo.

echo [1/4] 检查 git 状态...
git status --short
git log --oneline >nul 2>&1
if errorlevel 1 (
    echo   [错误] 没有 commit
    pause
    exit /b 1
)
echo.

echo [2/4] 测试 GitHub SSH 连接...
ssh -T -o ConnectTimeout=5 -o BatchMode=yes git@github.com 2>&1
echo.

echo [3/4] 检查 remote...
git remote -v
echo.

echo [4/4] 推送到 origin/main...
git push -u origin main
if errorlevel 1 (
    echo.
    echo   [错误] 推送失败！可能原因：
    echo     1. 还在公司网 (切到手机热点重试)
    echo     2. GitHub 仓库未创建 (https://github.com/new)
    echo     3. SSH key 未添加 (https://github.com/settings/keys)
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
