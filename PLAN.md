# MCU_TRACE 规划文档 (v0.2)

> 目标：基于 pywebview 打造一个 MCU 日志自动解析 + 可视化分析工具，重点支持电源管理生命周期曲线的绘制。
> 真实样本（2026-06-29 抓包 151MB）已验证。

## 1. 背景与目标

车载 MCU 项目（LK2A/LK1A/PK2C/N626 等）日常需要分析跑车上抓回来的 trace 日志。痛点：
- 手工 grep + 肉眼扫，效率低
- 电源相关的 PSM / PwrSuplyM / VoltDet 状态跳转散落在几十万行日志里，肉眼难辨时序
- 缺少可视化，问题复盘要靠经验

**目标**：本地桌面工具（pywebview 壳子），导入日志后自动解密+解析，给出：
1. 关键字 / 错误码检索 + 高亮
2. **状态机时序识别**（PSM 9+ 状态 + SoC 模式变化）
3. **电源管理生命周期曲线**（核心诉求：时间 vs 电压 / 状态）
4. 一键导出含原始节选 + 图表的自包含 HTML 报告

---

## 2. 真实样本分析

### 2.1 数据流

```
log_20260629_140253.zip  (151MB)
└── da/
    ├── avasese/   avasese_log1.log ~ log10.log (纯文本)
    ├── bsplog/    io_service.core.gz 等
    ├── crashdump/ *.zip.enc
    ├── iflytek/   work.log 等
    ├── logd/  ←  MCU trace 在这里
    │   ├── 001_001_20260629122126.zip.enc
    │   ├── 001_002_20260629122833.zip.enc
    │   ├── ...
    │   ├── 002_009_20260629134555.zip.enc
    │   └── 002_010_20260629135435.zip.enc  (10 个 .enc)
    └── meterlog/  dlt 等
```

### 2.2 解密 + 解压流程（必须内建）

原始 .enc → 复制到 `E:\Data\桌面工具\decrypt-update\decrypt-update\logd\` → `hsaedecrypt.exe logd`（AES 解密 + 内部展开为 logcat/logcat.001~020）→ 读取流式解析

**关键约束**：
- hsaedecrypt.exe 路径固定（README "DO NOT CHANGE THIS FOLDER NAME AND ITS PATH LOCATION"）
- `dev2zip.bat` 末尾 `pause` 会卡，用 Python 改名绕过
- 工具必须封装，GUI 一键完成

### 2.3 时间排序规则

**直接用文件名时间戳字典序排序**（不是 logcat 序号）：

```
001_001_20260629122126 → 2026-06-29 12:21:26
001_002_20260629122833 → 2026-06-29 12:28:33
002_010_20260629135435 → 2026-06-29 13:54:35
```

`XXX_YYYY_<YYYYMMDDHHMMSS>.zip.enc` 字典序天然 = 时间正序。

每个 .enc 内部是滚动 logcat（`logcat`、`logcat.001`、`logcat.020`...），序号越大越旧。整合时：先按 .enc 文件名时间，再在单个 .enc 内按 logcat 序号降序（最大→0）。

### 2.4 MCU trace 行格式（实测）

外层是 Android logcat 头，内层 mcu_trace 自定义级别和字段分隔：

```
MM-DD HH:MM:SS.ffffff  PID  TID  ANDROID_LEVEL  TAG:  MCU_LEVEL|MODULE COMPACT_TS| message
06-29 13:45:53.017942   335   339  I             mcu_trace:  I|PSM 0629134538| PreStandby->Standby, EVENT[14].
```

正则：

```python
LOG_LINE_RE = re.compile(
    r'^(?P<logcat_ts>\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)\s+'
    r'(?P<pid>\d+)\s+(?P<tid>\d+)\s+'
    r'(?P<logcat_level>[VDIWE])\s+'
    r'mcu_trace:\s+'
    r'(?P<mcu_level>[IWDENF])\|(?P<module>\w+)\s+'
    r'(?P<compact_ts>\d{10})\|'
    r'\s*(?P<message>.*)$'
)
```

### 2.5 发现的 MCU 模块（TAG 分布）

| TAG | 命中 | 性质 |
| --- | --- | --- |
| MIPC | 439 | MCU↔SoC IPC 通信（最热） |
| SYS_STATIST | 101 | 系统统计（CPU/负载） |
| **PSM** | 15 | **电源状态机**（核心） |
| DIPC | 14 | SoC→MCU IPC |
| BLM | 12 | 蓝牙/Bus Link Mgr? |
| MSAVE | 9 | 存储保存 |
| RadioDev | 6 | 收音机 |
| DEA / DeaDiag | 4+4 | 诊断 |
| **PwrSuplyM** | 2 | **电源供应管理** |
| HSE | 2 | 安全引擎（HSE/HSM） |
| VCFG | 2 | 车辆配置 |
| SWDL | 2 | 软件下载 |
| MCU | 2 | 复位信息 |
| HardF | 1 | Hard Fault（最严重） |

### 2.6 PSM 状态机（实测 9 状态）

```
PreStandby ──14──> Standby
   │ 5               │ 14
   ↓                 ↓
 Normal         PrepareSleep_Step1
                   │ 16
                   ↓
                PreSleep_1 (?)
                   │ 16?
                   ↓
                PreSleep_2 ──12──> WatiEvnShutDown
                                    │ 11
                                    ↓
                                 WakeUp ──11──> StartUp_1 ──15──> StartUp_2
                                                                  │ 12
                                                                  ↓
                                                              PreStandby
```

转换触发用 `EVENT[XX]` 编号标识。**PreSleep_1 本次样本未出现**，状态机配置留 10 个槽位。

### 2.7 SoC 模式独立维度

`mcu_trace: I|PSM ...| soc mode changed,cur[X] last[Y].` 多次出现：
- `cur[5] last[1]`、`cur[0] last[5]`、`cur[1] last[5]`、`cur[3] last[1]`、`cur[5] last[0]`

这是 **SoC（鸿蒙/QNX）系统状态**——与 PSM 平行。数字含义需用户配置（v0.1 留配置位）。

### 2.8 电压/复位数据点

| 类型 | 样本 | 备注 |
| --- | --- | --- |
| 电压 | `cur Volt is 13960` (mV) | PSM 上报，**采样点极稀** |
| MCU 复位 | `RST TYPE[18],REASON[24]` | 数字含义需用户配置 |
| Hard Fault | `Trace_BackupMcuRegContext_VaildationCheck failed` | 上下文校验失败 |
| SoC 复位 | `SECURE_BOOT_OK[ON]` | 安全启动状态 |

> **电压数据稀的影响**：电源曲线不能只靠 PSM 上报，要支持**可配置多个电压关键字**（如 `VoltDet`、`VBAT`、`volt=`），用户根据自己项目添加。

### 2.9 错误样例

- `mcu_trace: E|MSAVE` — 存储重试（`[ODO_INFO:retry:1 odo_display:41251]`）
- `mcu_trace: E|MIPC ...| REQ-S ID[177]CNT[9]` — IPC 错误
- `mcu_trace: W|MCU ...| RST TYPE[18],REASON[24]` — 复位警告
- `mcu_trace: W|HardF` — Hard Fault 警告
- `mcu_trace: E|DIPC ...| SOC-GET-VEHICLE_CFG:0x2.` — SoC 配置通信错

---

## 3. 推荐方案

### 3.1 技术选型

| 层 | 选型 | 理由 |
| --- | --- | --- |
| GUI 壳 | pywebview 4.x | 用户硬性要求 |
| 前端 | 原生 HTML + ECharts 5 | 时序图体验好；不引入构建链 |
| 后端 | Python 3.12 | 标准库优先 |
| 图表导出 | matplotlib（PNG base64 嵌入） | 离线 HTML 报告 |
| 报告模板 | Jinja2 → 单文件 HTML | 灵活 |
| 加密/解密 | subprocess 调 hsaedecrypt.exe | 不能改原工具位置 |

### 3.2 整体架构

```
+---------------------------------------------------+
|  pywebview Window                                 |
|  +---------------------+   +-------------------+  |
|  |  HTML/JS Frontend   |<->|  Python Backend   |  |
|  |  (ECharts 渲染)     |   |  (js_api)         |  |
|  +---------------------+   +---------+---------+  |
|                                     |             |
|                              +------v------+      |
|                              |  Importer   |      |
|                              |  - .enc →   |      |
|                              |    解密+解压 |      |
|                              +------+------+      |
|                              +------v------+      |
|                              |  Parser     |      |
|                              |  (正则解析) |      |
|                              +------+------+      |
|                              +------v------+      |
|                              |  Analyzer   |      |
|                              |  - keyword  |      |
|                              |  - fsm(PSM) |      |
|                              |  - fsm(SOC) |      |
|                              |  - voltage  |      |
|                              +------+------+      |
|                              +------v------+      |
|                              |  Reporter   |      |
|                              |  (HTML)     |      |
|                              +-------------+      |
+---------------------------------------------------+
```

### 3.3 目录结构（v0.1）

```
MCU_TRACE/
├── pyproject.toml
├── README.md
├── PLAN.md
├── src/mcu_trace/
│   ├── __main__.py          # python -m mcu_trace
│   ├── app.py               # pywebview + js_api
│   ├── core/
│   │   ├── importer.py      # .enc 解密 + 解压编排
│   │   ├── parser.py        # 解析器（2.4 正则）
│   │   ├── models.py        # LogEvent / LogSession
│   │   ├── keyword.py       # 关键字 / 错误码检索
│   │   ├── state_machine.py # FSM 引擎（PSM + SoC mode）
│   │   ├── voltage.py       # 电压数值提取（多关键字）
│   │   └── reporter.py      # HTML 报告
│   ├── web/
│   │   ├── index.html
│   │   ├── app.js
│   │   ├── style.css
│   │   └── vendor/echarts.min.js
│   └── assets/
│       ├── templates/report.html
│       └── config/
│           ├── builtin_rules.json
│           └── psm_fsm.json
└── tests/
    ├── test_importer.py
    ├── test_parser.py
    ├── test_keyword.py
    ├── test_state_machine.py
    ├── test_voltage.py
    └── fixtures/
```

---

## 4. 关键设计决策

### 4.1 导入层：解密流程封装

```python
# core/importer.py 伪代码
def import_logd(src_dir: Path, work_root: Path) -> list[Path]:
    """把 src_dir 下的 .enc 复制到 decrypt-update\logd\
    调用 hsaedecrypt.exe → 原地展开为 logcat 文件 → 拷贝到 work_root → 返回文件列表
    """
    decrypt_dir = Path(r"E:\Data\桌面工具\decrypt-update\decrypt-update\logd")
    # 1. 清理旧 .enc（保留 .bak 备份）
    # 2. Copy-Item .enc → decrypt_dir
    # 3. subprocess.run(["hsaedecrypt.exe", "logd"], cwd=decrypt_dir.parent)
    # 4. Rename-Item *.dec → *.zip（绕过 .bat 的 pause）
    # 5. zipfile 解压
    # 6. 返回 logcat 文件路径列表（按文件名时间戳排序）
```

GUI 提供两种入口：
- "导入 .enc 目录" → 走完整解密流程
- "导入已解密 logcat 文件" → 跳过解密，直接解析

### 4.2 解析器

`core/parser.py` 用 2.4 节正则流式处理大文件（生成器 + 进度条）。

时间戳处理：
- 优先级 1：logcat 头部 `MM-DD HH:MM:SS.ffffff`（精度高）
- 优先级 2：mcu_trace 紧凑 `MMDDHHMMSS`（精度秒）
- 跨日处理：从 .enc 文件名拿日期前缀拼接

### 4.3 状态机引擎

`core/state_machine.py` 实现**通用 FSM 跟踪器**：

```python
@dataclass
class StateMachine:
    name: str
    states: list[str]                  # 全部合法状态
    initial: str
    transitions: list[Transition]      # {from, to, pattern}

    def feed(self, event: LogEvent) -> Transition | None:
        for t in self.transitions:
            if re.search(t.pattern, event.message):
                return t
```

**PSM FSM 配置**（`assets/config/psm_fsm.json`）：

```json
{
  "name": "PSM",
  "states": ["PreStandby", "Standby", "Normal", "PrepareSleep_Step1",
             "PreSleep_1", "PreSleep_2", "WatiEvnShutDown", "WakeUp",
             "StartUp_1", "StartUp_2"],
  "initial": "PreStandby",
  "transitions": [
    {"from": "PreStandby", "to": "Standby",            "pattern": "PreStandby->Standby"},
    {"from": "Standby",    "to": "PrepareSleep_Step1", "pattern": "Standby->PrepareSleep_Step1"},
    {"from": "PrepareSleep_Step1", "to": "PreSleep_1", "pattern": "PrepareSleep_Step1->PreSleep_1"},
    {"from": "PreSleep_1", "to": "PreSleep_2",         "pattern": "PreSleep_1->PreSleep_2"},
    {"from": "PreSleep_2", "to": "WatiEvnShutDown",    "pattern": "PreSleep_2->WatiEvnShutDown"},
    {"from": "WatiEvnShutDown", "to": "WakeUp",        "pattern": "WatiEvnShutDown->WakeUp"},
    {"from": "WakeUp",     "to": "StartUp_1",          "pattern": "WakeUp->StartUp_1"},
    {"from": "StartUp_1",  "to": "StartUp_2",          "pattern": "StartUp_1->StartUp_2"},
    {"from": "StartUp_2",  "to": "PreStandby",         "pattern": "StartUp_2->PreStandby"},
    {"from": "PreStandby", "to": "Normal",             "pattern": "PreStandby->Normal"}
  ]
}
```

**SoC mode FSM**（用户配置）：

```json
{
  "name": "SoCMode",
  "states": ["0", "1", "3", "5"],
  "initial": "?",
  "transitions": [],
  "extract_pattern": "soc mode changed,cur\\[(\\d+)\\] last\\[(\\d+)\\]"
}
```

> PSM 和 SoC mode 是**两个独立 FSM**，UI 用双 track 渲染。

### 4.4 电压曲线 ⭐

**关键问题**：实测中电压数据点极稀（10 个 .enc 只有 1 条 `cur Volt is 13960`）。解决方案：

`assets/config/builtin_rules.json` 提供可配置电压关键字列表：

```json
"voltage_extractors": [
  {"name": "PSM Volt",      "pattern": "cur Volt is (\\d+)",  "unit": "mV", "scale": 0.001},
  {"name": "VoltDet VBAT",  "pattern": "VoltDet.*VBAT=([\\d.]+)", "unit": "V",  "scale": 1.0},
  {"name": "VoltDet 5V0",   "pattern": "VoltDet.*5V0=([\\d.]+)",  "unit": "V",  "scale": 1.0},
  {"name": "自定义",        "pattern": "",                       "unit": "mV", "scale": 0.001}
]
```

GUI 提供"添加自定义电压正则"按钮，**用户可以随时扩展**。默认启用 PSM Volt。

### 4.5 数字映射

`soc mode`、`RST TYPE`、`REASON` 这些数字含义需要**项目级配置**：

```json
"number_mappings": {
  "soc_mode": {"0": "OFF", "1": "Normal", "3": "Standby", "5": "PreStandby"},
  "rst_type":  {"18": "Watchdog Reset"},
  "rst_reason":{"24": "Power Glitch"}
}
```

GUI 提供编辑面板（v0.1 改 JSON 文件，v0.2 做可视化编辑器）。

### 4.6 HTML 报告

```
┌─────────────────────────────────────────┐
│  MCU TRACE Report                       │
│  文件: log_20260629_140253  |  时间跨度  │
├─────────────────────────────────────────┤
│  1. 概览：总事件数、错误数、状态转换数  │
│  2. 电源生命周期曲线                     │
│     - 电压时间曲线（PNG 嵌入）          │
│     - PSM 状态甘特图（PNG 嵌入）        │
│     - SoC 模式时间线（PNG 嵌入）        │
│  3. 状态机时序                           │
│     - PSM 跳转表 + 异常跳转列表         │
│     - SoC mode 变化表                   │
│  4. 关键字命中（按类别分组）             │
│  5. 原始日志节选（关键事件前后 ±20 行）  │
└─────────────────────────────────────────┘
```

---

## 5. 范围边界

### v0.1（MVP，本次实现）

- 完整解密流程（GUI 一键 .enc → logcat）
- MCU trace 解析（基于 2.4 节的正则）
- 多 .enc 跨文件时间排序（按文件名时间戳）
- 单 .enc 内 logcat 序号处理（logcat.020 → logcat.001 → logcat，倒序）
- 关键字 / 错误码检索 + 分类高亮
- PSM 状态机时序识别（含 10 状态 + 异常跳转）
- SoC mode 独立维度跟踪
- 电压时间曲线（matplotlib + ECharts）+ 可配置多关键字
- HTML 报告导出（自包含，PNG 内嵌）
- 数字映射 JSON 配置（v0.1 改文件，v0.2 GUI 编辑）

### v0.2（不实现，留 hook）

- 串口 / RTT 实时模式
- 多文件对比
- PyInstaller 打包
- PDF / Excel 报告
- 数字映射 GUI 可视化编辑
- 自定义规则 GUI 编辑器

### 不做

- 日志采集（导入即可）
- 在线协作 / 云端同步
- 自动写禅道日报

---

## 6. 验证方案

### 6.1 单元测试

- `test_importer.py`：mock hsaedecrypt + zip 处理
- `test_parser.py`：MCU trace 真实样本切片（≥100 行）
- `test_keyword.py`：规则匹配
- `test_state_machine.py`：合法 + 非法跳转
- `test_voltage.py`：多种关键字数值提取

### 6.2 E2E 流程

`python -m mcu_trace --e2e` 走完：
1. 读 1 个真实 .enc
2. 解密 + 解压
3. 解析 → 关键字 → FSM → 电压
4. 导出 mock_report.html
5. 断言：HTML 存在、PNG base64 嵌入、PSM 至少 5 个 transition、SoC mode 至少 1 次变化

### 6.3 用户验收

- 用 10 个 .enc 完整跑一次（2026-06-29 数据，约 1.5h 跨度）
- 看 HTML 报告是否符合预期
- 如果电压曲线太稀，根据 GUI 添加自定义电压关键字

---

## 7. 风险与对策

| 风险 | 影响 | 对策 |
| --- | --- | --- |
| hsaedecrypt.exe 路径变更 | 解密失败 | 配置文件可改路径，README 说明 |
| 实测电压数据点稀 | 曲线空 | 电压关键字可配置（v0.1 支持） |
| logcat 序号跨日处理错 | 时间乱序 | 用 .enc 文件名日期拼接 |
| E 级别样本少 | 错误面板空 | 内置常见关键字兜底（如 `WDG\|Fault\|Error`） |
| 大文件（>100MB）卡顿 | UX 差 | 解析用生成器 + 进度条 |
| 数字映射（soc mode）含义缺失 | 曲线无标注 | GUI 弹窗引导用户配置 |
| pywebview 在 Windows 缺 WebView2 | 起不来 | 启动时检测 + 友好报错 |

---

## 8. 实施步骤

| 步骤 | 内容 | 估时 |
| --- | --- | --- |
| 1 | 项目骨架 + pyproject + pywebview 启动 | 0.5h |
| 2 | `core/importer.py` 完整解密流程（含进度回调） | 1h |
| 3 | `core/parser.py` + models + 单测 | 1h |
| 4 | `core/state_machine.py` + PSM/SoC 配置 + 单测 | 1.5h |
| 5 | `core/keyword.py` + `core/voltage.py` + 单测 | 1h |
| 6 | `core/reporter.py` + Jinja2 模板 + matplotlib 曲线 | 1.5h |
| 7 | `web/index.html` + ECharts 集成 + pywebview.js_api | 2h |
| 8 | 单元测试 + E2E 流程 | 1h |
| 9 | 用真实 10 个 .enc 跑一次 + 迭代 | 0.5h |

**总计**：约 1.5 个工作日。

---

## 9. 下一步

1. **你**：
   - 状态机配置里 `soc mode` 的数字含义（0/1/3/5 分别对应什么状态）？这一步非必须，没配置也能跑。
   - 是否需要把 `HardF`（Hard Fault）单独高亮（红色 banner）？建议是，工具就做成默认开。
2. **我**：按 v0.1 范围开始实现，第一版交付：
   - 完整可跑工程（`python -m mcu_trace` 启动 GUI）
   - 单元测试通过
   - 用真实 10 个 .enc 数据跑出一份 HTML 报告
   - 报告里包含 PSM 状态甘特图 + 电压曲线 + SoC mode 时间线 + 原始节选

如果你想调整范围（v0.1 就只跑通 GUI 跳过 HTML 报告、或者第一版只要电源曲线不要状态机）随时说。

---

## 10. 数字映射补充（v0.2+）

### 10.1 PSM_ResetReason_t 枚举（用户提供）

```c
typedef enum {
    RESETREASON_BATT = 0,                // 电池掉电
    RESETREASON_GOTOSLEEP = 1,           // 正常休眠
    RESETREASON_DA_TIMEOUT = 2,          // DA 通信超时
    RESETREASON_METER_TIMEOUT = 3,       // Meter 通信超时
    RESETREASON_VOLT_ABNORMAL = 4,       // 电压异常
    RESETREASON_UPDATE = 5,              // OTA 更新
    RESETREASON_SWITCH_AB = 6,           // AB 切换
    RESETREASON_DIAG_CMD = 7,            // 诊断命令
    RESETREASON_DIPC_RESTORE_FACTORY = 8,// DIPC 恢复出厂
    RESETREASON_MIPC_RESTORE_FACTORY = 9,// MIPC 恢复出厂
    RESETREASON_SHELL = 10,              // Shell 触发
    RESETREASON_SOC_BOOT = 11,           // SoC 引导
    RESETREASON_RTC_ALARM = 12,          // RTC 闹钟
    RESETREASON_HAND_SHAKE_TIMEOUT = 13, // 握手超时
    RESETREASON_Button_Reboot = 14,      // 按钮重启
    RESETREASON_QNX_REQ_Reboot = 15,     // QNX 请求
    RESETREASON_UNKNOW = 16,             // 未知
    RESETREASON_36H_Reboot = 17,         // 36h 定时
    RESETREASON_MID_WAKEUP = 18          // 中唤醒
} PSM_ResetReason_t;
```

注意：枚举名是 `PSM_ResetReason_t`（reason），但用户样本里 `RST TYPE[18],REASON[24]` 中 18 命中 `RESETREASON_MID_WAKEUP`。**待确认**：RST TYPE 是否复用本枚举、还是另有独立定义。

### 10.2 写入 `assets/config/builtin_rules.json`

```json
"number_mappings": {
  "soc_mode": {
    "0": "OFF",
    "1": "Normal",
    "3": "Standby",
    "5": "PreStandby"
  },
  "reset_reason": {
    "0":  "RESETREASON_BATT",
    "1":  "RESETREASON_GOTOSLEEP",
    "2":  "RESETREASON_DA_TIMEOUT",
    "3":  "RESETREASON_METER_TIMEOUT",
    "4":  "RESETREASON_VOLT_ABNORMAL",
    "5":  "RESETREASON_UPDATE",
    "6":  "RESETREASON_SWITCH_AB",
    "7":  "RESETREASON_DIAG_CMD",
    "8":  "RESETREASON_DIPC_RESTORE_FACTORY",
    "9":  "RESETREASON_MIPC_RESTORE_FACTORY",
    "10": "RESETREASON_SHELL",
    "11": "RESETREASON_SOC_BOOT",
    "12": "RESETREASON_RTC_ALARM",
    "13": "RESETREASON_HAND_SHAKE_TIMEOUT",
    "14": "RESETREASON_Button_Reboot",
    "15": "RESETREASON_QNX_REQ_Reboot",
    "16": "RESETREASON_UNKNOW",
    "17": "RESETREASON_36H_Reboot",
    "18": "RESETREASON_MID_WAKEUP"
  }
}
```

GUI 提取逻辑（`core/voltage.py` 同款模式，复用 `re.search`）：

```python
# 匹配 mcu_trace 里的 RST TYPE / REASON
RST_PATTERN = re.compile(r"RST TYPE\[(\d+)\],REASON\[(\d+)\]")
def extract_rst(message: str) -> tuple[str, str] | None:
    m = RST_PATTERN.search(message)
    if m:
        rst_type, reason = m.groups()
        return (
            NUMBER_MAPPINGS["reset_reason"].get(rst_type, f"TYPE_{rst_type}"),
            NUMBER_MAPPINGS["reset_reason"].get(reason,  f"REASON_{reason}")
        )
    return None
```

### 10.3 待你确认

- [ ] RST TYPE 是否复用 `PSM_ResetReason_t` 这套枚举？如果不是，请提供 RST TYPE 自己的枚举
- [ ] `soc mode` 数字 0/1/3/5 含义（鸿蒙/QNX 状态名）？我先留 `?` 占位，跑通后你再填
- [ ] `RST TYPE[18],REASON[24]` 这种一行里同时出现两段数字的，工具默认按"两段都是 REASON"处理；如果 RST TYPE 有自己独立枚举请告知

不影响开干——默认值我先用 `?` 和 `TYPE_xx/REASON_xx` 占位，你后续在 `builtin_rules.json` 里改一下就生效。

---

## 11. 用户提供的两个枚举（v0.2+）

### 11.1 `PowerMode_Soc_t`（SoC 模式，完整 7 状态）

```c
typedef enum {
    PM_MODE_SOC_OFF        = 0,  // OFF
    PM_MODE_SOC_STANDBY    = 1,  // STANDBY
    PM_MODE_SOC_TEMPO_ON   = 2,  // TEMPO_ON（暂态开机）
    PM_MODE_SOC_NORMAL     = 3,  // NORMAL
    PM_MODE_SOC_TEMPO_OFF  = 4,  // TEMPO_OFF（暂态关机）
    PM_MODE_SOC_STR        = 5,  // STR（Suspend To RAM）
    PM_MODE_SOC_MAX        = 6   // MAX（哨兵/上限）
} PowerMode_Soc_t;
```

样本中观察到的实际跳转（已确认合法 vs 异常）：

| cur | last | 语义 | 评估 |
| --- | --- | --- | --- |
| 5 (STR)  | 1 (STANDBY) | STANDBY → STR | 合法（休眠进入） |
| 0 (OFF)  | 5 (STR)    | STR → OFF      | 合法（深度断电） |
| 1 (STBY) | 5 (STR)    | STR → STANDBY  | 合法（唤醒） |
| 3 (NRM)  | 1 (STBY)   | STANDBY → NORMAL | 合法（开机） |
| 5 (STR)  | 0 (OFF)    | OFF → STR      | **异常**（跳过 STANDBY） |
| 3 (NRM)  | 1 (STBY)   | STANDBY → NORMAL | 合法（重复 cycle） |

→ 状态机引擎会自动标红"OFF → STR" 这种非法跳转。

### 11.2 `Power_Ip_ResetType`（REASON，硬件级 MC_RGM）

```c
typedef enum {
    /* Destructive Event Status Register (MC_RGM_DES) */
    MCU_POWER_ON_RESET       = ... /* F_DR0  Power on */
    MCU_FCCU_FTR_RESET       = ... /* F_DR1  FCCU failure to react */
    MCU_STCU_URF_RESET       = ... /* F_DR3  STCU unrecoverable fault */
    MCU_MC_RGM_FRE_RESET     = ... /* F_DR4  Functional reset escalation */
    MCU_FXOSC_FAIL_RESET     = ... /* F_DR6  FXOSC failure */
    MCU_PLL_LOL_RESET        = ... /* F_DR8  CORE_PLL DFS loss of lock */
    MCU_CORE_CLK_FAIL_RESET  = ... /* F_DR9  PERIPH_PLL DFS loss of lock */
    MCU_AIPS_PLAT_CLK_FAIL_RESET = ... /* F_DR10 DDR_PLL loss of lock */
    MCU_HSE_CLK_FAIL_RESET   = ... /* F_DR11 ACCEL_PLL loss of lock */
    MCU_SYS_DIV_FAIL_RESET   = ... /* F_DR12 XBAR_DIV3_CLK failure */
    MCU_HSE_TMPR_RST_RESET   = ... /* F_DR13 Life-cycle error */
    MCU_HSE_SNVS_RST_RESET   = ... /* F_DR16 HSE SNVS tamper detected */
    MCU_SW_DEST_RESET        = ... /* F_DR17 HSE SWT timeout */
    MCU_DEBUG_DEST_RESET     = ... /* F_DR18 Software destructive reset */

    /* Functional Event Status Register (MC_RGM_FES) */
    MCU_F_EXR_RESET          = ... /* FCCU Reset Reaction */
    MCU_FCCU_RST_RESET       = ... /* Self-Test Done */
    MCU_ST_DONE_RESET        = ... /* SWT0 Timeout */
    MCU_SWT0_RST_RESET       = ... /* SWT1 Timeout */
    MCU_SWT1_RST_RESET       = ... /* HSE Memory ECC Error */
    MCU_JTAG_RST_RESET       = ... /* HSE Boot Failure Error */
    MCU_HSE_SWT_RST_RESET    = ... /* HSE M7 Core Lock */
    MCU_HSE_BOOT_RST_RESET   = ... /* Software functional reset */
    MCU_SW_FUNC_RESET        = ... /* Debug functional reset */
    MCU_DEBUG_FUNC_RESET     = ...

    MCU_WAKEUP_REASON        = ... /* Wake-up event detected */
    MCU_NO_RESET_REASON      = ... /* No reset reason found */
    MCU_MULTIPLE_RESET_REASON= ... /* More than one reset events */
    MCU_RESET_UNDEFINED      = ... /* Undefined reset source */
} Power_Ip_ResetType;
```

**枚举值映射**（值是 McuConf 配置文件分配的，常见 NXP S32K3 工具链下是顺序编号 0-27）：

| 值 | 名称 | 类别 | 严重度 |
| --- | --- | --- | --- |
| 0  | MCU_POWER_ON_RESET        | destructive | info |
| 1  | MCU_FCCU_FTR_RESET        | destructive | **critical** |
| 2  | MCU_STCU_URF_RESET        | destructive | **critical** |
| 3  | MCU_MC_RGM_FRE_RESET      | destructive | high |
| 4  | MCU_FXOSC_FAIL_RESET      | destructive | **critical** |
| 5  | MCU_PLL_LOL_RESET         | destructive | **critical** |
| 6  | MCU_CORE_CLK_FAIL_RESET   | destructive | **critical** |
| 7  | MCU_AIPS_PLAT_CLK_FAIL_RESET | destructive | **critical** |
| 8  | MCU_HSE_CLK_FAIL_RESET    | destructive | **critical** |
| 9  | MCU_SYS_DIV_FAIL_RESET    | destructive | **critical** |
| 10 | MCU_HSE_TMPR_RST_RESET    | destructive | **critical** |
| 11 | MCU_HSE_SNVS_RST_RESET    | destructive | **critical** |
| 12 | MCU_SW_DEST_RESET         | destructive | high |
| 13 | MCU_DEBUG_DEST_RESET      | destructive | high |
| 14 | MCU_F_EXR_RESET           | functional  | high |
| 15 | MCU_FCCU_RST_RESET        | functional  | high |
| 16 | MCU_ST_DONE_RESET         | functional  | info |
| 17 | MCU_SWT0_RST_RESET        | functional  | high |
| 18 | MCU_SWT1_RST_RESET        | functional  | high |
| 19 | MCU_JTAG_RST_RESET        | functional  | info |
| 20 | MCU_HSE_SWT_RST_RESET     | functional  | **critical** |
| 21 | MCU_HSE_BOOT_RST_RESET    | functional  | **critical** |
| 22 | MCU_SW_FUNC_RESET         | functional  | high |
| 23 | MCU_DEBUG_FUNC_RESET      | functional  | info |
| 24 | MCU_WAKEUP_REASON         | wakeup      | info |
| 25 | MCU_NO_RESET_REASON       | none        | info |
| 26 | MCU_MULTIPLE_RESET_REASON | multi       | high |
| 27 | MCU_RESET_UNDEFINED       | unknown     | high |

> ⚠️ **以上数值映射是按"工具链顺序编号"假设**。你样本 `REASON[24] = MCU_WAKEUP_REASON` 与本表对得上（24）。但 `McuConf_McuResetReasonConf_*` 的实际值由 EB tresos / S32 Configuration Tool 配置文件决定，可能会有出入。**工具运行时若发现实际值与映射不符，会回退到 `REASON_<value>` 占位字符串**——你可以在 GUI 配置面板里修正。

### 11.3 写入 `assets/config/builtin_rules.json`（完整版）

```json
{
  "number_mappings": {
    "soc_mode": {
      "0": "OFF",
      "1": "STANDBY",
      "2": "TEMPO_ON",
      "3": "NORMAL",
      "4": "TEMPO_OFF",
      "5": "STR",
      "6": "MAX"
    },
    "rst_type": {
      "0":  "RESETREASON_BATT",
      "1":  "RESETREASON_GOTOSLEEP",
      "2":  "RESETREASON_DA_TIMEOUT",
      "3":  "RESETREASON_METER_TIMEOUT",
      "4":  "RESETREASON_VOLT_ABNORMAL",
      "5":  "RESETREASON_UPDATE",
      "6":  "RESETREASON_SWITCH_AB",
      "7":  "RESETREASON_DIAG_CMD",
      "8":  "RESETREASON_DIPC_RESTORE_FACTORY",
      "9":  "RESETREASON_MIPC_RESTORE_FACTORY",
      "10": "RESETREASON_SHELL",
      "11": "RESETREASON_SOC_BOOT",
      "12": "RESETREASON_RTC_ALARM",
      "13": "RESETREASON_HAND_SHAKE_TIMEOUT",
      "14": "RESETREASON_Button_Reboot",
      "15": "RESETREASON_QNX_REQ_Reboot",
      "16": "RESETREASON_UNKNOW",
      "17": "RESETREASON_36H_Reboot",
      "18": "RESETREASON_MID_WAKEUP"
    },
    "rst_reason": {
      "0":  "MCU_POWER_ON_RESET",
      "1":  "MCU_FCCU_FTR_RESET",
      "2":  "MCU_STCU_URF_RESET",
      "3":  "MCU_MC_RGM_FRE_RESET",
      "4":  "MCU_FXOSC_FAIL_RESET",
      "5":  "MCU_PLL_LOL_RESET",
      "6":  "MCU_CORE_CLK_FAIL_RESET",
      "7":  "MCU_AIPS_PLAT_CLK_FAIL_RESET",
      "8":  "MCU_HSE_CLK_FAIL_RESET",
      "9":  "MCU_SYS_DIV_FAIL_RESET",
      "10": "MCU_HSE_TMPR_RST_RESET",
      "11": "MCU_HSE_SNVS_RST_RESET",
      "12": "MCU_SW_DEST_RESET",
      "13": "MCU_DEBUG_DEST_RESET",
      "14": "MCU_F_EXR_RESET",
      "15": "MCU_FCCU_RST_RESET",
      "16": "MCU_ST_DONE_RESET",
      "17": "MCU_SWT0_RST_RESET",
      "18": "MCU_SWT1_RST_RESET",
      "19": "MCU_JTAG_RST_RESET",
      "20": "MCU_HSE_SWT_RST_RESET",
      "21": "MCU_HSE_BOOT_RST_RESET",
      "22": "MCU_SW_FUNC_RESET",
      "23": "MCU_DEBUG_FUNC_RESET",
      "24": "MCU_WAKEUP_REASON",
      "25": "MCU_NO_RESET_REASON",
      "26": "MCU_MULTIPLE_RESET_REASON",
      "27": "MCU_RESET_UNDEFINED"
    }
  }
}
```

### 11.4 提取与显示

```python
# core/reset.py
import re
RST_PATTERN = re.compile(r"RST TYPE\[(\d+)\],REASON\[(\d+)\]")

def extract_rst(message: str, mappings: dict) -> dict | None:
    m = RST_PATTERN.search(message)
    if not m:
        return None
    rst_type, reason = m.groups()
    return {
        "rst_type_raw":   int(rst_type),
        "rst_type_name":  mappings.get("rst_type",   {}).get(rst_type,  f"TYPE_{rst_type}"),
        "reason_raw":     int(reason),
        "reason_name":    mappings.get("rst_reason", {}).get(reason,    f"REASON_{reason}"),
        "severity":       REASON_SEVERITY.get(int(reason), "info")
    }

REASON_SEVERITY = {
    1: "critical", 2: "critical", 4: "critical", 5: "critical",
    6: "critical", 7: "critical", 8: "critical", 9: "critical",
    10: "critical", 11: "critical", 20: "critical", 21: "critical",
    # ... 其余按上表
}
```

HTML 报告里：
- critical → 红色 banner（置顶）
- high → 橙色
- info → 灰色

---

## 12. 打包发包流程（v0.1 必做）

### 12.1 总体策略

- **打包工具**：PyInstaller `--onedir`（目录模式）
- **产物**：`MCU_TRACE_v0.1.0_20260630.zip`（约 45-50MB）
- **目标受众**：5+ 名内部同事（技术岗，懂装软件，不懂 Python）
- **安装方式**：解压 + 一键安装脚本
- **配置位置**：`%APPDATA%\MCU_TRACE\`（用户级，可改）
- **hsaedecrypt**：**不打包**，通过 GUI 配置面板指定路径（默认 `E:\Data\桌面工具\decrypt-update\decrypt-update\hsaedecrypt.exe`）

### 12.2 目录结构（打包前）

```
MCU_TRACE/                       ← 源码
├── pyproject.toml               ← 项目元数据 + 打包配置
├── installer/
│   ├── install.ps1              ← 一键安装脚本
│   ├── uninstall.ps1            ← 一键卸载脚本
│   ├── create_shortcut.ps1      ← 建桌面快捷方式
│   └── mcu_trace.spec           ← PyInstaller spec 文件
├── README.md                    ← 用户文档
├── INSTALL.md                   ← 详细安装说明
├── CHANGELOG.md                 ← 版本变更
├── src/mcu_trace/...
└── tests/...
```

### 12.3 PyInstaller spec 文件（核心）

```python
# installer/mcu_trace.spec
# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

a = Analysis(
    ['../src/mcu_trace/__main__.py'],
    pathex=['../src'],
    binaries=[
        # hsaedecrypt.exe 不打包，用户配置
    ],
    datas=[
        ('../src/mcu_trace/web', 'web'),               # HTML/JS 前端
        ('../src/mcu_trace/assets/templates', 'assets/templates'),
        ('../src/mcu_trace/assets/config',   'assets/config'),
        ('../src/mcu_trace/assets/samples',  'assets/samples'),
    ],
    hiddenimports=[
        'webview', 'webview.platforms.winforms',
        'matplotlib', 'jinja2',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,        # ← 关键：目录模式
    name='MCU_TRACE',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                    # UPX 加壳常被杀毒误报，关掉
    console=False,                # GUI 模式，不弹 console
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='../src/mcu_trace/assets/icon.ico',  # 自定义图标（可选）
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MCU_TRACE',
)
```

**关键开关**：
- `exclude_binaries=True` + 独立的 `COLLECT(...)` → 目录模式
- `console=False` → GUI 不弹黑窗
- `upx=False` → 避免杀毒误报
- `icon` → 自定义 exe 图标（可选，用默认也行）

### 12.4 打包命令

```powershell
# 在项目根目录
cd MCU_TRACE
pyinstaller installer/mcu_trace.spec --clean --noconfirm

# 产物在 dist/MCU_TRACE/
# 打 zip
Compress-Archive -Path dist/MCU_TRACE -DestinationPath dist/MCU_TRACE_v0.1.0_20260630.zip
```

### 12.5 一键安装脚本（`installer/install.ps1`）

```powershell
#Requires -RunAsAdministrator
# MCU_TRACE Installer v0.1.0
$ErrorActionPreference = "Stop"
$installPath = "C:\Tools\MCU_TRACE"
$startMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MCU_TRACE"
$configPath = "$env:APPDATA\MCU_TRACE"

# 1. 检测已安装版本
if (Test-Path "$installPath\version.txt") {
    $oldVer = Get-Content "$installPath\version.txt"
    Write-Host "检测到已安装版本: $oldVer，将覆盖安装" -ForegroundColor Yellow
}

# 2. 关闭正在运行的实例
Get-Process MCU_TRACE -ErrorAction SilentlyContinue | Stop-Process -Force

# 3. 解压 zip 到安装目录
Write-Host "正在安装到 $installPath ..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $installPath | Out-Null
Expand-Archive -Path "$PSScriptRoot\MCU_TRACE" -DestinationPath $installPath -Force

# 4. 写版本号
"v0.1.0" | Out-File "$installPath\version.txt" -Encoding UTF8

# 5. 创建用户配置目录 + 默认 config.json
New-Item -ItemType Directory -Force -Path $configPath | Out-Null
$defaultConfig = @{
    decrypt_tool_path = "E:\Data\桌面工具\decrypt-update\decrypt-update\hsaedecrypt.exe"
    default_logd_dir  = "E:\Data\MCU_Logs"
    theme = "light"
}
$defaultConfig | ConvertTo-Json | Out-File "$configPath\config.json" -Encoding UTF8

# 6. 检测 WebView2（Windows 10 1803+ 一般自带）
$webview2 = Get-ItemProperty -Path "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" -ErrorAction SilentlyContinue
if (-not $webview2) {
    Write-Host "⚠️ 检测到本机未安装 WebView2 运行时" -ForegroundColor Yellow
    Write-Host "  工具将无法启动 GUI。请从以下地址下载安装：" -ForegroundColor Yellow
    Write-Host "  https://developer.microsoft.com/zh-cn/microsoft-edge/webview2/" -ForegroundColor Cyan
    $choice = Read-Host "是否现在打开浏览器下载？(y/n)"
    if ($choice -eq "y") { Start-Process "https://developer.microsoft.com/zh-cn/microsoft-edge/webview2/" }
}

# 7. 创建桌面快捷方式
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut("$env:USERPROFILE\Desktop\MCU_TRACE.lnk")
$shortcut.TargetPath = "$installPath\MCU_TRACE.exe"
$shortcut.WorkingDirectory = $installPath
$shortcut.IconLocation = "$installPath\MCU_TRACE.exe,0"
$shortcut.Description = "MCU 日志解析分析工具 v0.1.0"
$shortcut.Save()

# 8. 创建开始菜单快捷方式
New-Item -ItemType Directory -Force -Path $startMenuPath | Out-Null
$startShortcut = $shell.CreateShortcut("$startMenuPath\MCU_TRACE.lnk")
$startShortcut.TargetPath = "$installPath\MCU_TRACE.exe"
$startShortcut.WorkingDirectory = $installPath
$startShortcut.Save()

Write-Host "`n✅ 安装完成！" -ForegroundColor Green
Write-Host "  安装目录: $installPath"
Write-Host "  配置文件: $configPath\config.json"
Write-Host "  快捷方式: 桌面 / 开始菜单" -ForegroundColor Green
Write-Host "`n⚠️ 首次使用请在 GUI '设置' 面板配置 decrypt-update 路径（默认已填好）。"
```

### 12.6 一键卸载脚本（`installer/uninstall.ps1`）

```powershell
#Requires -RunAsAdministrator
$installPath = "C:\Tools\MCU_TRACE"
$startMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\MCU_TRACE"
$configPath = "$env:APPDATA\MCU_TRACE"

# 关闭运行中的实例
Get-Process MCU_TRACE -ErrorAction SilentlyContinue | Stop-Process -Force

# 删除安装目录、快捷方式
Remove-Item $installPath -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $startMenuPath -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$env:USERPROFILE\Desktop\MCU_TRACE.lnk" -Force -ErrorAction SilentlyContinue

$keep = Read-Host "是否同时删除用户配置？默认保留（y=删除）"
if ($keep -eq "y") {
    Remove-Item $configPath -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "已删除配置" -ForegroundColor Yellow
} else {
    Write-Host "已保留配置: $configPath" -ForegroundColor Green
}

Write-Host "`n✅ 卸载完成" -ForegroundColor Green
```

### 12.7 README 草稿

```markdown
# MCU_TRACE 工具 v0.1.0

MCU 日志（mcu_trace）自动解析 + 可视化分析工具，专注电源管理生命周期曲线。

## 功能
- 一键导入加密 .enc 日志（自动调 decrypt-update 解密）
- 关键字 / 错误码检索 + 分类高亮
- PSM 电源状态机时序识别（10 状态 + 异常跳转检测）
- SoC 模式（OFF/STANDBY/TEMPO_ON/NORMAL/TEMPO_OFF/STR）时间线
- 电压时间曲线（支持自定义电压关键字正则）
- 一键导出含图表 + 原始节选的 HTML 报告

## 系统要求
- Windows 10 1803+ / Windows 11
- WebView2 Runtime（Win10 1803+ 一般自带，缺了启动时会提示）
- 公司 decrypt-update 工具（用于解密 .enc 日志）

## 安装

1. 解压 `MCU_TRACE_v0.1.0_20260630.zip` 到任意目录
2. **右键以管理员身份运行** `install.ps1`
3. 按提示完成安装（约 1 分钟）
4. 桌面双击 `MCU_TRACE` 快捷方式启动

## 首次配置

启动后 → 菜单 `设置` → `解密工具` 标签 → 确认 `hsaedecrypt.exe` 路径正确
（默认 `E:\Data\桌面工具\decrypt-update\decrypt-update\hsaedecrypt.exe`）

## 使用流程

1. 菜单 `文件` → `导入 .enc 目录`（选 .enc 所在文件夹）
2. 等待解密 + 解析完成（进度条会显示）
3. 主界面查看：事件表格 / 状态机时序 / 电压曲线
4. 菜单 `报告` → `导出 HTML 报告`

## 常见问题

**Q: 启动报错 "WebView2 not found"**
A: 访问 https://developer.microsoft.com/zh-cn/microsoft-edge/webview2/ 下载安装

**Q: 导入 .enc 报错 "hsaedecrypt not found"**
A: 检查 decrypt-update 工具是否安装；GUI 设置面板里确认路径正确

**Q: 解析后没有 mcu_trace 事件**
A: 检查源 .enc 文件是否包含 MCU 日志；用 `Select-String` 验证原始文件含 mcu_trace 字样

## 反馈
飞书/企微联系 mafuxuan
```

### 12.8 v0.1 打包发包实施步骤

| 步骤 | 内容 | 估时 |
| --- | --- | --- |
| 12.1 | 写 `mcu_trace.spec` + 测试本地打包成功 | 1h |
| 12.2 | 写 `install.ps1` / `uninstall.ps1` | 1h |
| 12.3 | 写 `README.md` / `INSTALL.md` / `CHANGELOG.md` | 1h |
| 12.4 | 在自己机器上跑一遍完整安装 + 卸载流程 | 0.5h |
| 12.5 | 找 1-2 个同事机器上做兼容性测试 | 0.5h |
| 12.6 | 修打包 / 安装脚本的 bug | 0.5h |
| 12.7 | 出最终 zip + 飞书群发包 | 0.5h |

**打包发包总计**：约 5h（0.6 个工作日），**v0.1 必做**。

### 12.9 升级机制（v0.2 留 hook，v0.1 不做）

- 工具启动时读 `%APPDATA%\MCU_TRACE\config.json`，含 `version` 字段
- 首次启动检查 `app_version` vs `config.version`，不一致弹窗"检测到升级，旧配置已合并"
- 配置 schema 变更时给迁移脚本：`migrate_0_1_to_0_2.py`
- 远程升级检查：v0.2 加一个"检查更新"菜单，调公司内部 Git/网盘 manifest.json

### 12.10 安全 / 合规

- **不收集用户数据**：工具纯本地运行，无网络请求
- **不读取敏感文件**：除用户明确选择的 .enc / logcat 目录外，不扫描磁盘
- **日志路径**：`%APPDATA%\MCU_TRACE\app.log`（仅记录工具自身错误，不记录解析内容）
- **代码签名**：v0.1 不做（要买证书），v0.2 评估 EV 证书
- **杀毒误报**：用 PyInstaller 目录模式 + 不开 UPX + 提交微软 MAPP 误报申诉（v0.2）

### 12.11 测试矩阵（v0.1 上线前必跑）

| 环境 | 备注 |
| --- | --- |
| Win 10 21H2 家庭版 | 主力测试机 |
| Win 11 23H2 专业版 | 新机器 |
| Win 10 LTSC 2019 | 兼容性测试（公司老机器） |
| WebView2 已装 | 正常路径 |
| WebView2 未装 | 启动时给下载链接（不能崩） |
| decrypt-update 已装 | 正常路径 |
| decrypt-update 未装 | 启动时给提示，禁用导入按钮（不能崩） |
| %APPDATA% 不可写 | 启动时报错给清晰提示 |

---

## 13. v0.1 总时间估算（更新）

| 模块 | 估时 |
| --- | --- |
| 1. 项目骨架 + pywebview 启动 | 0.5h |
| 2. core/importer.py 完整解密流程 | 1h |
| 3. core/parser.py + models + 单测 | 1h |
| 4. core/state_machine.py + PSM/SoC 配置 + 单测 | 1.5h |
| 5. core/keyword.py + core/voltage.py + core/reset.py + 单测 | 1h |
| 6. core/reporter.py + Jinja2 模板 + matplotlib 曲线 | 1.5h |
| 7. web/index.html + ECharts 集成 + pywebview.js_api | 2h |
| 8. 单元测试 + E2E 流程 | 1h |
| 9. 用真实 10 个 .enc 跑一次 + 迭代 | 0.5h |
| **10. 打包 + 安装脚本** | **5h** |
| 11. README + 文档 | 1h |
| 12. 兼容性测试 + 修 bug | 1h |

**总计**：约 18h（**2.3 个工作日**）。

---

## 14. v0.1 实施顺序（更新）

```
Day 1
  ├── 1-2  项目骨架 + pywebview + importer（先跑通解密流程）
  ├── 3    parser 解析（能解析 mcu_trace 行）
  └── 4-5  state_machine + keyword + voltage（核心分析能力）

Day 2
  ├── 6-7  reporter + matplotlib 曲线 + web 前端 + ECharts
  ├── 8    E2E 跑通：导入 → 解析 → 报告
  └── 9    真实 10 个 .enc 数据调优

Day 3
  ├── 10   打包 + 安装脚本
  ├── 11   写 README/CHANGELOG
  └── 12   同事机器兼容性测试 + 修 bug
```

---

## 15. 计划完成清单

| 章节 | 状态 |
| --- | --- |
| 1. 背景与目标 | ✅ |
| 2. 真实样本分析（151MB 抓包） | ✅ |
| 3. 推荐方案 | ✅ |
| 4. 关键设计决策 | ✅ |
| 5. 范围边界 | ✅ |
| 6. 验证方案 | ✅ |
| 7. 风险与对策 | ✅ |
| 8. 实施步骤 | ✅ (v0.1) |
| 9. 下一步 | ✅ |
| 10. 数字映射补充 | ✅ |
| 11. 用户提供的两个枚举 | ✅ |
| **12. 打包发包流程** | ✅ **(v0.1 必做)** |
| 13. 总时间估算 | ✅ (2.3 工作日) |
| 14. 实施顺序 | ✅ |
| 15. 计划完成清单 | ✅ |

<media src="E:\Git_PJ\MCU_TRACE\PLAN.md" caption="MCU_TRACE 规划文档 v0.3 完整版（42KB / 15 章）" />

---

## 12. v0.2-C 设计稿：自定义规则 GUI 编辑器

> 目标：消除 v0.1 唯一遗留痛点——"数字映射（soc_mode/rst_type/rst_reason）需要手动改 `builtin_rules.json` 重打包"。
> 范围：仅 3 类规则（**number_mappings / keyword_rules / voltage_extractors**）；FSM 配置（psm_fsm/soc_fsm）留 v0.3。

### 12.1 合并策略

| 规则类型 | 合并方式 | 说明 |
| --- | --- | --- |
| `number_mappings` | **按键级覆盖**（保留 builtin 中 user 未列出的 key） | user 给 `{"soc_mode": {"0": "我的OFF"}}` 时仅覆盖 `0`；builtin 中 `1/2/3/...` 保持不变。**v0.2.1 修订**：原"整体覆盖"会导致其他 key 丢失成 `MODE_xx` 占位，UX 反直觉 |
| `keyword_rules` | **追加 + pattern 冲突胜出** | builtin + user 拼接；user 项排在后；正则编译时**先到先得**，user 可覆盖 builtin 同 pattern |
| `voltage_extractors` | **追加 + name 冲突胜出** | 同 keyword_rules，但冲突判定按 `name` 字段 |

存储路径：`%APPDATA%\MCU_TRACE\user_rules.json`（独立于 `config.json`，避免污染通用配置）。
结构（与 `builtin_rules.json` 同 schema，但只填用户改动部分）：

```json
{
  "version": "0.2.0",
  "number_mappings": {
    "soc_mode": {"0": "OFF", "1": "STANDBY", "2": "我的状态", ...},
    "rst_type": {"18": "我的RST类型"}
  },
  "keyword_rules": [
    {"pattern": "MyProjectErr.*\\d+", "category": "custom", "severity": "high"}
  ],
  "voltage_extractors": [
    {"name": "我的 VBAT", "pattern": "VoltDet.*VBAT=([\\d.]+)", "unit": "V", "scale": 1.0, "enabled": true}
  ]
}
```

### 12.2 新增 / 修改文件

| 文件 | 改动 |
| --- | --- |
| `src/mcu_trace/core/rules_loader.py` (**新**) | `load_builtin()` / `load_user()` / `merge(builtin, user) -> dict`；提供 `validate_rule(category, rule) -> (ok, msg)` |
| `src/mcu_trace/core/config.py` | `UserConfig` 加 `user_rules: dict = field(default_factory=dict)`；新增 `get_user_rules_path()` 返回 `%APPDATA%\MCU_TRACE\user_rules.json` |
| `src/mcu_trace/core/analyzer.py` | 把 `_load_json_config("builtin_rules.json")` 换成 `load_merged_rules()` |
| `src/mcu_trace/core/keyword.py` | `KeywordScanner.from_json(data: dict)` 接受 dict（不只是 Path），便于注入合并结果 |
| `src/mcu_trace/core/voltage.py` | 同 keyword.py：接受 dict |
| `src/mcu_trace/core/reset.py` | 同上 |
| `src/mcu_trace/app.py` `McuTraceApi` | 新增 `get_user_rules()` / `save_user_rules(rules)` / `validate_pattern(category, pattern)` / `reset_user_rules()` 4 个 js_api |
| `src/mcu_trace/web/index.html` | 新增 "📐 规则" 标签页；3 个子卡片（数字映射 / 关键字 / 电压提取器）；增删改表格 + 校验 + 保存 + 恢复默认按钮 |
| `tests/test_rules_loader.py` (**新**) | 7 个测试：builtin 加载 / user 加载 / number_mappings 覆盖 / keyword_rules 追加 / voltage_extractors 追加 / 坏正则校验 / save+reload roundtrip |
| `src/mcu_trace/assets/config/builtin_rules.json` | 不变 |

### 12.3 GUI 标签页布局（"📐 规则"）

```
┌─────────────────────────────────────────────────────┐
│ 📐 自定义规则  (保存于 %APPDATA%\MCU_TRACE\user_rules.json) │
├─────────────────────────────────────────────────────┤
│ [数字映射]    [关键字]    [电压提取器]              │  ← 子标签
├─────────────────────────────────────────────────────┤
│  子命名空间: [soc_mode ▼] [rst_type] [rst_reason]   │  ← 数字映射分组
│ ┌────┬──────────────────────────┐                   │
│ │ 键 │ 名称                     │ [+行] [删除]      │
│ ├────┼──────────────────────────┤                   │
│ │ 0  │ OFF                      │                   │
│ │ 1  │ STANDBY                  │                   │
│ │ ...│                          │                   │
│ └────┴──────────────────────────┘                   │
├─────────────────────────────────────────────────────┤
│ [💾 保存规则]  [🔄 恢复内置默认]  [🧪 校验正则]      │
└─────────────────────────────────────────────────────┘
```

切换到 "📊 分析" 重跑 → 立即生效（不需重启 GUI）。

### 12.4 验收

1. ✅ 26/26 旧测试 + 7 个新测试 = **33 passed**
2. ✅ E2E 跑通：`work/test_enc4/` 出报告，电压/复位结果与 v0.1 byte-identical（未改 user_rules 时）
3. ✅ GUI smoke：在 user_rules.json 写一条 `{"soc_mode": {"0": "我的OFF"}}`、重启 GUI、分析 → 报告中 SoC mode 显示 "我的OFF"
4. ✅ 坏正则处理：写 `{"pattern": "[unclosed"}`，保存时弹 "正则无效: missing ]"；不写入磁盘
5. ✅ 重打包 + exe 存活 + 报告 SHA256 一致

### 12.5 不在 v0.2-C 范围

- ❌ psm_fsm.json / soc_fsm.json 编辑（FSM 配置改 GUI 化放 v0.3）
- ❌ dark theme（README 提了，但独立 feature）
- ❌ 规则导入/导出（JSON 复制粘贴手动）
- ❌ 规则批量删除 / 排序 / 搜索
