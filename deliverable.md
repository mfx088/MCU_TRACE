# MCU_TRACE v0.1.0 bug 修复 + 重打包 开发完成报告

> 由 owner (Mavis) 手动补写。Worker 因 15min timeout 未完成，但实际所有修复均已落地（最近几轮对话中完成），验证全部通过。

---

## 修复的 bug

### 1. 按钮点不动（pywebview api 时机）
- **根因**：HTML 脚本顶层 `const api = window.pywebview.api` 在 pywebview 注入 `js_api` 之前执行，`api` 是 undefined，所有 `await api.xxx()` 静默失败。
- **修复**：
  - 删除 `<script>` 顶部的 `const api = window.pywebview.api`
  - 加 `getApi()` 懒查找函数
  - 加 `pywebviewready` 事件，pywebview 注入完成才调 `init()`
  - 所有 `onclick` 加 `getApi() == null` 检查 + toast 提示
  - 加全局错误捕获（`window.onerror` + `unhandledrejection`）→ 错误显示在 toast
- **位置**：`src/mcu_trace/web/index.html`

### 2. FileNotFoundError: builtin_rules.json（PyInstaller 资源路径错）
- **根因**：spec 把 datas 放到 `_internal/assets/...`，但代码里 `CONFIG_DIR = __file__.parent.parent / "assets/config"` 计算出来是 `_internal/mcu_trace/assets/config/...`（多一层 `mcu_trace/`）。
- **修复**：
  - `installer/mcu_trace.spec` 的 datas 路径加 `mcu_trace/` 中间层
  - `src/mcu_trace/app.py` 的 `_get_web_dir()` 改成 `sys._MEIPASS / "mcu_trace" / "web"`
- **位置**：`installer/mcu_trace.spec` + `src/mcu_trace/app.py`

### 3. ECharts 状态机图空（custom series data 格式错）
- **根因**：ECharts custom series 的 `data` 必须是**对象数组** `[{}, {}, ...]`，我之前写成了**嵌套数组** `[[{...}], [{...}], ...]`——ECharts 找不到 `value` 字段，色块一个都没渲染。
- **修复**：两处 `data.push([{` → `data.push({`，对应的 `}]);` → `});`。
- **位置**：`src/mcu_trace/web/index.html` line 568, 622

---

## 验证结果

### Step 1: 单元测试
```
============================= 26 passed in 0.08s ==============================
```
**26/26 通过** ✅

### Step 2: E2E 报告
- `E:\Git_PJ\MCU_TRACE\work\report.html` 283KB
- events=620, fsm_transitions=14, rst_events=1
**E2E 跑通** ✅

### Step 3: 重新打包
- `dist\MCU_TRACE\MCU_TRACE.exe` 17.3MB
**打包成功** ✅

### Step 4: 打包后结构
```
dist\MCU_TRACE\_internal\mcu_trace\
  ├── assets\config\{builtin_rules.json, psm_fsm.json, soc_fsm.json}
  ├── assets\templates\report.html
  ├── web\{index.html}
  └── web\vendor\echarts.min.js (1MB)
```
**资源完整** ✅

### Step 5: 打包后 exe 启动
PID 存活 8 秒不退出
**GUI 可启动** ✅

### Step 6: 发包 zip
- `dist\MCU_TRACE_v0.1.0_20260630.zip` 62.3MB
**发包完成** ✅

---

## 最终产物

| 项 | 路径 | 大小 |
| --- | --- | --- |
| GUI exe | `E:\Git_PJ\MCU_TRACE\dist\MCU_TRACE\MCU_TRACE.exe` | 17.3MB |
| 发包 zip | `E:\Git_PJ\MCU_TRACE\dist\MCU_TRACE_v0.1.0_20260630.zip` | 62.3MB |
| 安装源 | `E:\Git_PJ\MCU_TRACE\installer\MCU_TRACE\` | 124MB（解包后） |
| E2E 报告 | `E:\Git_PJ\MCU_TRACE\work\report.html` | 283KB |

---

## 遗留/风险

1. **GUI 端图表实际渲染**：CLI E2E 验证了后端（matplotlib 图表），但 ECharts 图表（PSM/SoC/电压）需要用户在 GUI 端点击「📥 导入并分析」按钮后由 ECharts 渲染——headless 没法验证。修复了 `data.push` 格式 bug 后，理论上应该正常，但仍需用户在实机点击验证。

2. **状态机 Y 轴类别方向**：当前 Y 轴按"预待机 → 待机 → 运行 → ... → 关机"自下而上排列，可能用户期望"自上而下"或"按时间"。GUI 端可调。

3. **WebView2 依赖**：打包后 exe 启动需要 WebView2，Win10 1803+ 自带，缺了工具启动时会弹窗给下载链接。

---

## 修复时间

- 修复 3 个 bug：~30 分钟
- 重新打包 + 验证：~3 分钟（PyInstaller 1-2min + 启动测试 8s）

**结论：开发完成。等待独立 E2E 验证任务。**
