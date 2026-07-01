# 🚗 MCU TRACE 工具 v0.1.0

> 车载 MCU 日志自动解析 + 可视化分析工具，专注电源管理生命周期曲线。

## ✨ 功能

- 📥 **一键导入加密 .enc 日志**（自动调用公司 `hsaedecrypt` 工具解密）
- 🔍 **关键字 / 错误码检索** + 分类高亮（故障/复位/看门狗/电压/通信/安全）
- 📊 **PSM 电源状态机时序**（10 状态 + 异常跳转自动标红）
- 📊 **SoC 系统模式时序**（OFF/STANDBY/TEMPO_ON/NORMAL/TEMPO_OFF/STR）
- ⚡ **电压时间曲线**（正常范围灰色带 + 异常高亮 + 支持自定义关键字正则）
- 🔄 **MCU 复位事件**（按 NXP S32K3 硬件枚举自动映射）
- 📄 **一键导出 HTML 报告**（自包含单文件，图表内嵌，可邮件直发）

## 🎯 适用场景

- 车上 debug：跑一段路后抓 .enc，用工具分析电源/状态/复位
- 偶发问题复盘：把异常时刻前后的 mcu_trace 截出来，工具自动出报告
- 新人培训：拿到 MCU 日志不知道看什么？工具给一句话总结

## 📋 系统要求

| 项 | 要求 |
|---|---|
| OS | Windows 10 1803+ / Windows 11 |
| WebView2 | Win10 1803+ 一般自带，缺了启动时会提示下载 |
| 解密工具 | 公司 `hsaedecrypt.exe`（用于解密 .enc 日志） |
| 权限 | 普通用户即可（安装需管理员） |

## 🚀 安装

### 方式一：图形安装（推荐）

1. 解压 `MCU_TRACE_v0.1.0_20260630.zip` 到任意目录
2. **右键以管理员身份运行** `install.ps1`
3. 按提示完成（约 1 分钟）
4. 双击桌面「MCU TRACE」图标启动

### 方式二：手动运行（开发模式）

```powershell
cd MCU_TRACE
pip install -e .
python -m mcu_trace
```

## 📖 使用

### 第一次使用

1. 启动后，菜单切换到「⚙️ 设置」
2. 确认 `hsaedecrypt.exe` 路径（默认 `E:\Data\桌面工具\decrypt-update\decrypt-update\hsaedecrypt.exe`）
3. 切回「📊 分析」

### 导入 .enc 分析

1. 点击「浏览」选 .enc 所在目录
2. 点「📥 导入并分析」（首次 1-3 分钟）
3. 主界面看：概览 / TL;DR 总结 / ECharts 状态机图 / 事件表
4. 点「📄 导出 HTML 报告」存成自包含 .html

### 仅分析已解密 logcat

直接在「📂 已解密目录」输入框填路径（包含 `logcat` 文件的子目录），点「分析」。

## 📊 报告示例

工具自动生成：
- **TL;DR 卡片**（一句话总结 + emoji 标记）
- **概览统计**（7 个数字卡片，异常项红色高亮）
- **PSM 状态机时序图**（水平色块 + 中文状态名 + 配色）
- **SoC 模式时序图**
- **整车电池电压曲线**（正常范围带 + 异常点红圈）
- **关键字分类柱状图**
- **状态转换明细表**（含中文翻译）
- **MCU 复位事件表**（含硬件枚举映射）
- **关键字命中明细表**

## 🔧 配置

配置文件位置：`%APPDATA%\MCU_TRACE\config.json`

```json
{
  "decrypt_tool_path": "E:\\Data\\桌面工具\\decrypt-update\\decrypt-update\\hsaedecrypt.exe",
  "default_logd_dir": "",
  "theme": "light",
  "custom_voltage_patterns": [],
  "custom_keyword_patterns": []
}
```

### 自定义电压关键字

如果项目里 `VoltDet` / `VBAT` 等关键字不标准，可以在 `custom_voltage_patterns` 加：

```json
[
  {"name": "我的电压", "pattern": "VoltDet.*VBAT=([\\d.]+)", "unit": "V", "scale": 1.0, "enabled": true}
]
```

## 🆘 常见问题

**Q: 启动报错 "WebView2 not found"**
A: 访问 https://developer.microsoft.com/zh-cn/microsoft-edge/webview2/ 下载安装

**Q: 导入 .enc 报错 "hsaedecrypt not found"**
A: 1) 检查 decrypt-update 工具是否安装；2) GUI 设置面板里改路径

**Q: 解析后没有 mcu_trace 事件**
A: 检查源 .enc 文件是否含 MCU 日志；用 `Select-String` 验证原始文件含 `mcu_trace` 字样

**Q: 状态机异常跳转太多**
A: 检查 `assets/config/psm_fsm.json` 和 `state_machine.py:LEGAL_SOC_TRANSITIONS`，可能要补充合法转换

**Q: 怎么升级到 v0.2？**
A: 重跑 install.ps1 即可，会自动覆盖安装（配置和缓存保留）

## 📞 反馈

- 飞书/企微: mafuxuan
- Issue: 公司内部 Git（待开通）

## 📝 版本

- **v0.1.0** (2026-06-30): MVP 首发

## 📄 许可

仅限公司内部使用。
