<#
.SYNOPSIS
    MCU TRACE 安装脚本
.DESCRIPTION
    解压 MCU_TRACE 工具到 C:\Tools\MCU_TRACE\，创建桌面快捷方式，
    初始化用户配置，检测 WebView2 依赖。
.NOTES
    以管理员身份运行。
#>

#Requires -RunAsAdministrator
$ErrorActionPreference = "Stop"

$installPath = "C:\Tools\MCU_TRACE"
$startMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MCU_TRACE"
$configPath = "$env:APPDATA\MCU_TRACE"
$scriptRoot = $PSScriptRoot

# 颜色函数
function Write-Info($msg)  { Write-Host "[INFO]  $msg" -ForegroundColor Cyan }
function Write-OK($msg)    { Write-Host "[ OK ]  $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "[FAIL]  $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "========================================" -ForegroundColor White
Write-Host "  MCU TRACE v0.1.0 安装程序" -ForegroundColor White
Write-Host "========================================" -ForegroundColor White
Write-Host ""

# 1. 检测已安装版本
if (Test-Path "$installPath\version.txt") {
    $oldVer = Get-Content "$installPath\version.txt" -ErrorAction SilentlyContinue
    Write-Warn "检测到已安装版本: $oldVer，将覆盖安装"
}

# 2. 关闭正在运行的实例
$proc = Get-Process MCU_TRACE -ErrorAction SilentlyContinue
if ($proc) {
    Write-Info "关闭正在运行的 MCU_TRACE（PID: $($proc.Id)）..."
    $proc | Stop-Process -Force
    Start-Sleep -Seconds 1
}

# 3. 解压到安装目录
Write-Info "解压到 $installPath ..."
New-Item -ItemType Directory -Force -Path $installPath | Out-Null
$sourceDir = Join-Path $scriptRoot "MCU_TRACE"
if (-not (Test-Path $sourceDir)) {
    Write-Err "找不到源目录: $sourceDir"
    Write-Err "请将 MCU_TRACE 目录放在 install.ps1 同级目录后再运行"
    exit 1
}
Copy-Item -Path "$sourceDir\*" -Destination $installPath -Recurse -Force

# 4. 写版本号
"v0.1.0" | Out-File "$installPath\version.txt" -Encoding UTF8 -NoNewline

# 5. 初始化用户配置
Write-Info "初始化用户配置..."
New-Item -ItemType Directory -Force -Path $configPath | Out-Null
$configFile = "$configPath\config.json"
if (-not (Test-Path $configFile)) {
    $defaultConfig = @{
        decrypt_tool_path = "E:\Data\桌面工具\decrypt-update\decrypt-update\hsaedecrypt.exe"
        default_logd_dir  = ""
        theme             = "light"
        work_dir          = ""
        custom_voltage_patterns = @()
        custom_keyword_patterns = @()
        version           = "0.1.0"
        last_updated      = ""
    } | ConvertTo-Json
    $defaultConfig | Out-File $configFile -Encoding UTF8
    Write-OK "已创建默认配置: $configFile"
} else {
    Write-Info "配置已存在，跳过"
}

# 6. 检测 WebView2
Write-Info "检测 WebView2 运行时..."
$webview2 = Get-ItemProperty -Path "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" -ErrorAction SilentlyContinue
if (-not $webview2) {
    $webview2 = Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" -ErrorAction SilentlyContinue
}
if ($webview2) {
    Write-OK "WebView2 已安装: v$($webview2.pv)"
} else {
    Write-Warn "本机未检测到 WebView2 运行时"
    Write-Warn "GUI 将无法启动。请访问以下地址下载安装："
    Write-Host "    https://developer.microsoft.com/zh-cn/microsoft-edge/webview2/" -ForegroundColor Cyan
    $choice = Read-Host "`n是否现在打开浏览器下载？(y/n)"
    if ($choice -eq "y") {
        Start-Process "https://developer.microsoft.com/zh-cn/microsoft-edge/webview2/"
    }
}

# 7. 创建桌面快捷方式
Write-Info "创建快捷方式..."
$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcut = $shell.CreateShortcut("$desktop\MCU TRACE.lnk")
$shortcut.TargetPath = "$installPath\MCU_TRACE.exe"
$shortcut.WorkingDirectory = $installPath
$shortcut.IconLocation = "$installPath\MCU_TRACE.exe,0"
$shortcut.Description = "MCU 日志解析分析工具 v0.1.0"
$shortcut.Save()
Write-OK "桌面快捷方式已创建"

# 8. 创建开始菜单快捷方式
New-Item -ItemType Directory -Force -Path $startMenuPath | Out-Null
$startShortcut = $shell.CreateShortcut("$startMenuPath\MCU TRACE.lnk")
$startShortcut.TargetPath = "$installPath\MCU_TRACE.exe"
$startShortcut.WorkingDirectory = $installPath
$startShortcut.Save()
Write-OK "开始菜单快捷方式已创建"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  安装完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  安装目录: $installPath"
Write-Host "  配置文件: $configFile"
Write-Host "  快捷方式: 桌面 / 开始菜单"
Write-Host ""
Write-Host "  ⚠ 首次使用请在 GUI 「设置」面板检查 hsaedecrypt.exe 路径" -ForegroundColor Yellow
Write-Host ""
Write-Host "  启动方式: 双击桌面「MCU TRACE」图标" -ForegroundColor Cyan
Write-Host ""
Read-Host "按 Enter 退出"
