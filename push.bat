@echo off
REM ============================================================
REM  MCU_TRACE 一键推送到 GitHub
REM  使用前提：已完成 GITHUB_SETUP.md 里的步骤 1-3
REM ============================================================

echo.
echo [1/3] 检查 git 状态...
git status --short
echo.

echo [2/3] 测试 GitHub SSH 连接...
ssh -T -o ConnectTimeout=5 git@github.com
echo.

echo [3/3] 推送到 origin/main...
git push -u origin main
if errorlevel 1 (
    echo.
    echo [错误] 推送失败！可能原因：
    echo   1. 远程仓库未创建 → https://github.com/new
    echo   2. SSH key 未添加到 GitHub → https://github.com/settings/keys
    echo   3. 远程仓库名不对 → git remote -v
    echo.
    echo 详细说明见 GITHUB_SETUP.md
    pause
    exit /b 1
)

echo.
echo ✓ 推送成功！
echo 仓库地址: https://github.com/mafuxuan/MCU_TRACE
pause
