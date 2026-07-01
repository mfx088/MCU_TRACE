# MCU_TRACE Changelog

## v0.2.2 (2026-07-01) — 炫酷分析进度条

### 新增
- **全屏进度遮罩层（v0.2.2）**：
  - 圆形 SVG 进度环（`stroke-dasharray` 动画 + 渐变描边 + drop-shadow 发光）
  - 3 段 phase 配色：import 蓝→青 / analyze 紫→粉 / done 绿
  - 步骤列表（11 步）：已完成 ✓ / 进行中 ●（pulse 动画）/ 待办
  - 实时消息：「当前任务：解析 mcu_trace 事件」
  - ETA 计时器（mm:ss 格式）
  - 完成态：header 变绿、spinner 变 ✓、100% 数字
- **后端进度回调链路**：
  - `analyzer.py` 新增 `progress_cb` 参数，每个阶段都调用（解析/PSM/SoC/电压/复位/关键字）
  - `app.py` `import_and_analyze` 把 importer 和 analyzer 的 progress_cb 合并成 0~1 进度，通过 `window.evaluate_js()` 推到前端
  - 前端 `__mcuTraceUpdateProgress(payload)` 接收并更新 UI

### 改进
- 用户点击「导入并分析」后立刻看到全屏炫酷进度条（不再干等）
- 11 步可视化（扫描 → 复制 → 解密 → 解压 → 整理 → 解析 → PSM → SoC → 电压 → 复位 → 关键字）
- 实时 ETA（mm:ss）
- 错误时进度条立即消失并显示 toast

### 数据
- 验证数据：仍为 2026-06-29 N626 抓包
- 49/49 单元测试通过

### 技术栈
- 无新依赖；纯 CSS animations + SVG + JS state machine

## v0.2.1 (2026-07-01) — 图表 UI 美化

### 改进
- **静态报告 HTML（report.html 模板）**:
  - 章节标题从粗大蓝色 bar 改为轻盈的「左竖条 + 序号圆角徽章 + 副标题」设计
  - 概览统计从 7 张独立卡片改为**横向 icon+label+value chip**，色块按状态染色
  - 表格：中文按 `word-break: keep-all` 不再断字；长内容列（消息/原始日志）允许换行
  - 表格加 sticky header + zebra 条纹 + hover 高亮
  - 新增响应式 + 打印 CSS
- **matplotlib 样式（reporter.py）**:
  - 应用现代主题（白底、淡网格、无顶/右轴、统一字号 11-14px）
  - 电压曲线：1 个点也能"好看"——13.96V 标值 + 渐变填充 + 9-16V 绿带 + 阈值标签
  - FSM 时序：Y 轴反转（开机顶/关机底）、图例移到下方、色块圆角
  - 关键字图：横向柱状图、按数量降序、值标在右端
- **GUI ECharts（index.html）**:
  - 3 个图表从纵向堆叠改为 **Tabbed 视图**（节省垂直空间）
  - 图表容器：gradient header（标题 + 关键指标 pill）+ 白卡片 + 圆角 + 软阴影 + hover lift
  - ECharts 新增 `toolbox`（saveAsImage / dataView / restore）+ `dataZoom`（inside + slider）
  - ECharts 配色从 pastel 改为更深的色板（蓝/绿/紫更饱和）
  - 电压图新增 `markPoint`（每点都标值）、`areaStyle` 渐变填充

### 数据
- 验证数据：仍为 2026-06-29 N626 抓包（620 事件 / 14 FSM / 0 非法 / 1 复位 / 9 关键字）
- 49/49 单元测试通过

### 技术栈
- 无新依赖；纯 CSS/JS/matplotlib rcParams 调整

## v0.2.0 (2026-07-01) — 自定义规则 GUI 编辑器

### 新增
- **`core/rules_loader.py`（新）** — builtin + user 规则合并层
  - number_mappings 按键级合并（user 给出的 key 覆盖 builtin，未给出的保留 builtin）
  - keyword_rules / voltage_extractors 追加（user 在后，冲突时 user 胜出）
  - 全量校验（坏正则 / 非法子命名空间 / 坏 unit / 坏 severity 全部拒绝）
- **GUI 新增 "📐 规则" 标签页**：
  - 3 个子卡片：🔢 数字映射 / 🔍 关键字 / ⚡ 电压提取器
  - 增删改表格、实时校验、恢复默认、保存到 `%APPDATA%\MCU_TRACE\user_rules.json`
  - 未保存改动有视觉提示（橙色徽章）
- **js_api 新增 4 个方法**：`get_user_rules` / `get_builtin_rules_preview` / `save_user_rules` / `validate_pattern` / `reset_user_rules`
- **`UserConfig.user_rules` 字段**（v0.2+ 替代原 `custom_voltage_patterns` / `custom_keyword_patterns` 占位）

### 改进
- 数字映射编辑不再需要改 `builtin_rules.json` 源码 + 重打包——所有项目都可在 GUI 内适配
- v0.1 已知限制中"数字映射需手动配置" 标记为已解决

### 数据
- 验证数据：仍为 2026-06-29 N626 抓包（620 条 mcu_trace 事件、14 FSM 转换）
- 无 user_rules 时，E2E 报告与 v0.1 数据层 byte-identical（9 byte diffs 全部在生成时间戳）

### 技术栈
- 同 v0.1；无新依赖
- **49/49 单元测试通过**（26 旧 + 23 新 `test_rules_loader`）

### 已知限制
- FSM 配置（psm_fsm/soc_fsm）仍需手动改 `assets/config/*.json`（v0.3 计划）
- 用户改 `soc_mode` 某 key 的值后，原来以原名为 key 的 FSM 合法转换检测会失效（如 `STR→OFF` 改成 `STR→我的OFF` 后标 illegal）——这是 v0.1 引擎的固有限制，不影响核心功能

## v0.1.0 (2026-06-30) — MVP 首发

### 新增
- 核心解析器（基于 N626 真实样本适配的 mcu_trace 行格式）
- PSM 电源状态机时序（10 状态机 + 异常跳转检测）
- SoC 系统模式时序（7 状态 + 合法转换集）
- 关键字 / 错误码检索（fault / reset / watchdog / voltage / comm / hsm / retry 分类）
- 电压时间曲线（PSM Volt 关键字，可扩展自定义）
- MCU 复位事件提取（PSM_ResetReason_t + Power_Ip_ResetType 双枚举映射）
- HTML 报告导出（小白友好版：中文 + 配色 + TL;DR 卡片）
- 加密 .enc 导入流程（调 hsaedecrypt.exe + 自动解 .zip）
- GUI（pywebview）：三标签页（分析 / 设置 / 关于）+ ECharts 状态机图
- 用户配置管理（%APPDATA%\MCU_TRACE\config.json）
- PyInstaller 目录模式打包 spec
- install.ps1 / uninstall.ps1 一键安装卸载脚本

### 数据
- 验证数据：2026-06-29 N626 抓包 151MB（10 个 .enc，1.5h 时长，620 条 mcu_trace 事件）

### 技术栈
- Python 3.12 + pywebview 4.4 + matplotlib 3.11 + jinja2 3.1 + ECharts 5.5
- 26/26 单元测试通过

### 已知限制
- 时间戳异常：极少数 logcat 行的 MMDD 与文件名不一致（系统时钟混乱），v0.1 接受
- 仅支持本地 .enc 文件，不支持串口/RTT 实时（v0.3 计划）
- ~~数字映射（soc mode/RST TYPE/REASON）需要用户配置匹配实际枚举值~~ ✅ v0.2 已解决

## 计划
- v0.3: 串口实时模式、多文件对比、FSM 状态机 GUI 编辑、打包代码签名
