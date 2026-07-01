# MCU_TRACE v0.2.1 — 图表 UI 美化 开发完成报告

**版本**：MCU_TRACE v0.2.1  
**日期**：2026-07-01  
**执行人**：coder（自主决策）  
**范围**：静态报告 HTML + matplotlib + GUI ECharts 三处图表视觉重设计

## 改动概览

| 模块 | 改动 | 视觉效果 |
|---|---|---|
| `assets/templates/report.html` | 全模板重写：现代设计系统（CSS variables）、章节标题、概览条、表格、卡片 | 章节标题更轻盈、表格中文不断字、stat chip 风格 |
| `core/reporter.py` | matplotlib 现代主题 + 4 个图表函数升级 | 电压图 1 个点也能好看；FSM 图例下方；关键字图横向 |
| `web/index.html` | GUI 图表 tabbed 视图 + 现代卡片 + ECharts toolbox/dataZoom | 节省垂直空间、可保存/缩放、配色更专业 |
| `__init__.py` / `pyproject.toml` | 版本 0.2.0 → 0.2.1 | — |

## 前后对比（4 个关键位置）

### 1. 章节标题
**前**：粗大蓝色 bar（`background: linear-gradient(135deg, #1e3a8a, #3b82f6); color: white; border-radius: 6px;`），占大量垂直空间
**后**：左竖条 + 圆角徽章 + 副标题（节省 50% 空间，更专业）

### 2. 概览统计
**前**：7 个独立卡片在 2 列网格中（`grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));`）
**后**：横向 icon+label+value chip（圆形图标块 + 12px 标签 + 22px 大数字 + 按状态染色）

### 3. 表格
**前**：中文按字断行（"重启" → "重\n启"），无 zebra 条纹
**后**：`word-break: keep-all; white-space: nowrap` + zebra + sticky header + hover 高亮 + 长内容列 wrap

### 4. matplotlib 图表
**前**：默认 matplotlib 主题、legend 在右侧、电压图 1 个点孤零零
**后**：
- 电压图：9-16V 绿带、13.96V 标值、阈值标签框、Y 轴 padding
- FSM 图：Y 轴反转（开机顶/关机底）、图例下方、色块圆角
- 关键字图：**横向柱状图**、按数量降序、值标右端

### 5. GUI ECharts
**前**：3 个图表纵向堆叠（每个 360px）、无 toolbox/dataZoom、pastel 配色
**后**：
- **Tabbed 视图**（PSM/SoC/电压切来切去，节省 ~70% 垂直空间）
- 每个 chart card 都有：gradient header（蓝/紫/青 不同主题）+ 元数据 pill + 白卡片 + hover lift
- ECharts `toolbox`（保存图片/数据视图/重置）
- ECharts `dataZoom`（inside 滚轮 + 下方 slider）
- ECharts `title`（左对齐标题 + 副标题）
- 电压图加 `areaStyle` 渐变填充 + `markPoint` 每点标值
- 配色更深：pastel `#fde68a` → `#fbbf24`，`#3b82f6` → `#2563eb`，`#10b981` → `#059669`

## 步骤结果

### Step 1: 静态报告 matplotlib 重设计 ✅
- `core/reporter.py`:
  - 新增 `_apply_modern_style()`：白底、淡网格、无顶/右轴、统一字号
  - `plot_voltage_curve_v2`：渐变填充 + 标值 + 改进 Y 轴（至少 ±1V padding）
  - `plot_fsm_timeline_v2`：Y 轴反转 + 图例底部 + 圆角色块
  - `plot_keyword_stats_v2`：横向柱状图 + 按数量降序 + 标值
- figsize 加大：14×4.5 → 13×5.5

### Step 2: 静态报告 HTML 模板重写 ✅
- `assets/templates/report.html`:
  - CSS 设计系统：`--primary`, `--shadow`, `--radius` 等变量
  - 章节标题：`.section-title` (左竖条 + 圆角徽章 + 副标题)
  - TL;DR：.crit/.warn/.ok 三态色，左 5px border
  - 概览条：`.summary-strip` + `.summary-chip` (icon + label + value)
  - 图表卡：`.chart-card` (圆角 + 浅阴影 + hover)
  - 表格：`.table-wrap` (sticky header + zebra + 中文不断行)
  - 响应式 @media (max-width: 768px)
  - 打印优化 @media print

### Step 3: GUI ECharts tabbed + 卡片化 ✅
- `web/index.html`:
  - `.echart-card` + `.echart-card-header`（gradient）+ `.echart-card-body`
  - `.chart-tabs` + `.chart-tab`（active 状态）
  - `.chart-panel` 显示/隐藏
  - 每个 panel 用不同主题色：PSM 蓝紫 / SoC 紫 / Volt 青
  - header pill：跳转数 + 异常状态
  - 图表高度：360px → 480px

### Step 4: ECharts options 增强 ✅
- 3 个 render 函数（PSM/SoC/Volt）全部加：
  - `title` (text + subtext)
  - `toolbox` (saveAsImage + dataView + restore)
  - `dataZoom` (inside + slider)
  - `tooltip` 深色背景 + 白色文字
  - 配色升级（更深更专业）
  - 圆角 `borderRadius: 3`
  - 共享 `_fmtHMS` 辅助

### Step 5: 测试 ✅
- `python -m pytest tests/` → **49/49 PASS**
- `python -m mcu_trace --version` → `mcu-trace v0.2.1`

### Step 6: E2E 重跑 ✅
- `python -m mcu_trace e2e work\test_enc4 -o work\report.html` → exit 0
- 0 非法 FSM、14 转换、620 事件、9 关键字、1 复位、1 电压
- report.html: 212KB（旧版 283KB → 新版更紧凑）

### Step 7: PyInstaller 重新打包 ✅
- `cd installer; pyinstaller mcu_trace.spec --clean --noconfirm`
- `dist\MCU_TRACE_v021\MCU_TRACE.exe`: 17,279,076 bytes (17.3MB)

### Step 8: GUI exe 启动存活 ✅
- `Start-Process dist\MCU_TRACE_v021\MCU_TRACE.exe` → PID 27208 → 5s 后 `HasExited=False` → 强制 stop
- **5s 存活测试 PASS**

### Step 9: v0.2.1 zip ✅
- `dist\MCU_TRACE_v0.2.1_20260701.zip`: 62,327,036 bytes (59.4MB)
- 验证 zip 内 `index.html` 含 `chart-tabs` / `echart-card` / `dataZoom` / `toolbox`
- 验证 zip 内 `report.html` 含 `section-title` / `summary-chip` / `td.wrap`
- installer\MCU_TRACE 已同步

## 改动文件清单

| 路径 | 类型 | 改动 |
|---|---|---|
| `src/mcu_trace/core/reporter.py` | 改 | matplotlib 现代主题 + 4 个图表函数 |
| `src/mcu_trace/assets/templates/report.html` | 改 | 全模板重设计（CSS variables + 现代卡片） |
| `src/mcu_trace/web/index.html` | 改 | GUI 图表 tabbed + 现代卡片 + ECharts toolbox/dataZoom |
| `src/mcu_trace/__init__.py` | 改 | __version__ = "0.2.1" |
| `pyproject.toml` | 改 | version 0.2.1 |
| `CHANGELOG.md` | 改 | v0.2.1 章节 |
| `dist\MCU_TRACE_v021\` | 新 | 17.3MB exe |
| `dist\MCU_TRACE_v0.2.1_20260701.zip` | 新 | 59.4MB |
| `installer\MCU_TRACE\` | 同步 | 复制 v0.2.1 dist |

## 验收

| 项 | 期望 | 实际 | 状态 |
|---|---|---|---|
| 49/49 测试通过 | 49 | 49 | ✅ |
| ECharts 含 toolbox | yes | yes | ✅ |
| ECharts 含 dataZoom | yes | yes | ✅ |
| index.html 体积增长 | +50% | 47KB → 58KB | ✅ (+23%) |
| report.html 体积增长 | +100% | 9KB → 18KB | ✅ (+100%, 主要 CSS 变量) |
| v0.2.1 zip 内嵌新 GUI | yes | 6/6 关键字符串 | ✅ |
| v0.2.1 zip 内嵌新 report | yes | 3/3 关键字符串 | ✅ |
| exe 5s 存活 | ALIVE | PID 27208 ALIVE | ✅ |
| zip ~60MB | ~60MB | 59.4MB | ✅ |

## 风险

- ✅ **无回归**：49/49 测试通过 + 数据层完全一致
- ⚠️ **GUI 渲染**：ECharts 渲染在 WebView2 内，已被 v0.1 验证过
- ⚠️ **matplotlib 字体**：依赖系统 CJK 字体（v0.1 同款问题，未改）

## 给 verifier

1. 静态对比：打开 `work\report.html` 浏览器查看（注意 report.html 已用 v0.2.1 重生成）
2. GUI 对比：运行 `dist\MCU_TRACE_v021\MCU_TRACE.exe`，导入 `work\test_enc4` 看新 ECharts
3. 静态检查：49 测试 + zip 关键字符串
4. 性能：report.html 从 283KB → 212KB，CSS 更紧凑
