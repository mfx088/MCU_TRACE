# MCU TRACE 工具 v0.1.0 (便携版)

> 绿色版 — 解压即用，不写注册表，不创建额外快捷方式，卸载=删除文件夹。

## 使用方法

1. 把 `MCU_TRACE_v0.1.0_portable.zip` 解压到任意目录（如 `D:\Tools\MCU_TRACE\`）
2. 双击文件夹里的 **`MCU_TRACE.exe`** 启动

## 系统要求

- Windows 10 1803+ / Windows 11
- WebView2 Runtime（Win10 1803+ 一般自带）
- 公司的 `hsaedecrypt.exe`（首次导入 .enc 需用）

## 首次使用

1. 双击 MCU_TRACE.exe 启动
2. 切到「⚙️ 设置」标签
3. 确认 `hsaedecrypt.exe` 路径（默认 `E:\Data\桌面工具\decrypt-update\decrypt-update\hsaedecrypt.exe`）
4. 切到「📊 分析」→ 「浏览」选 .enc 目录 → 「📥 导入并分析」
5. 「📄 导出 HTML 报告」存成自包含 .html

## 用户配置

配置文件：`%APPDATA%\MCU_TRACE\config.json`
（首次运行自动创建默认配置，无需手动管理）

## 卸载

- 直接删除解压的文件夹即可
- 如需彻底清除：`删除 %APPDATA%\MCU_TRACE\ 文件夹`

## 管理员权限？

不需要。普通用户权限即可。
