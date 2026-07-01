<#
.SYNOPSIS
    MCU TRACE 卸载脚本
.DESCRIPTION
    删除安装目录、快捷方式。可选删除用户配置。
#>

#Requires -RunAsAdministrator
$ErrorActionPreference = "Stop"

$installPath = "C:\Tools\MCU_TRACE"
$startMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MCU_TRACE"
$configPath = "$env:APPDATA\MCU_TRACE"
$desktop = [Environment]::GetFolderPath("Desktop")

function Write-Info($msg) { Write-Host "[INFO]  $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "[ OK ]  $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN]  $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "========================================" -ForegroundColor White
Write-Host "  MCU TRACE 卸载程序" -ForegroundColor White
Write-Host "========================================" -ForegroundColor White
Write-Host ""

# 关闭运行中的实例
$proc = Get-Process MCU_TRACE -ErrorAction SilentlyContinue
if ($proc) {
    Write-Info "关闭正在运行的 MCU_TRACE（PID: $($proc.Id)）..."
    $proc | Stop-Process -Force
    Start-Sleep -Seconds 1
}

# 删除安装目录
if (Test-Path $installPath) {
    Write-Info "删除安装目录: $installPath"
    Remove-Item $installPath -Recurse -Force
    Write-OK "安装目录已删除"
} else {
    Write-Info "安装目录不存在，跳过"
}

# 删除快捷方式
$shortcutDesktop = "$desktop\MCU TRACE.lnk"
if (Test-Path $shortcutDesktop) {
    Remove-Item $shortcutDesktop -Force
    Write-OK "桌面快捷方式已删除"
}

if (Test-Path $startMenuPath) {
    Remove-Item $startMenuPath -Recurse -Force
    Write-OK "开始菜单快捷方式已删除"
}

# 询问是否删除用户配置
Write-Host ""
$keep = Read-Host "是否同时删除用户配置（含历史报告）？默认保留（输入 y 删除）"
if ($keep -eq "y") {
    if (Test-Path $configPath) {
        Write-Info "删除配置: $configPath"
        Remove-Item $configPath -Recurse -Force
        Write-OK "配置已删除"
    }
} else {
    Write-Info "已保留配置: $configPath"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  卸载完成" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Read-Host "按 Enter 退出"
