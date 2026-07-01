# X 轴修复 + 重打包完成报告

**版本**：MCU_TRACE v0.1.0  
**日期**：2026-06-30  
**执行人**：coder

## Summary

完成了 ECharts 状态机图 X 轴时间显示的第三次修复（`type:"time"` + 显式 `min:baseMs`/`max:maxMs` + HH:MM:SS formatter），并发现原修复版有 3 处关键 bug（PSM/SOC `xAxis.max` 引用了未定义的 `sortedPoints`、Volt data 用相对秒而非绝对 ms），全部修正后跑通 26/26 单测 + E2E、PyInstaller 重新打包、exe 启动 5 秒存活、打 zip 完成。

## Step-by-Step Results

### Step 1: 静态检查 ✅
- `xAxis: { type: "time", min: baseMs, max: maxMs, axisLabel: { formatter: (v) => ...HH:MM:SS... }` × 3 处（PSM line 589、SOC line 654、Volt line 692）
- `xAxis: { type: "value"` × 0 处
- 3 处 `axisLabel.formatter` 都用 `getHours()`/`getMinutes()`/`getSeconds()` 输出 `HH:MM:SS`

**关键修复（修在打包前）**：

| # | 文件:行 | Bug | 修复 |
|---|---------|-----|------|
| 1 | `src/mcu_trace/web/index.html:588` | PSM `xAxis.max` 表达式引用未定义的 `sortedPoints`（运行时 ReferenceError） | 提前计算 `const maxMs = sortedTrans.length > 0 ? new Date(sortedTrans[sortedTrans.length-1].timestamp).getTime() : baseMs;`，xAxis 改为 `max: maxMs` |
| 2 | `src/mcu_trace/web/index.html:652` | SOC 同 bug | 同上修法 |
| 3 | `src/mcu_trace/web/index.html:679` | Volt `data` 用 `[(new Date(p.timestamp).getTime() - baseMs) / 1000, p.value_v]`（相对秒），但 `xAxis.type:"time"` + `min:baseMs` 期望绝对 ms — 数值会被画在 1970+ 偏移处 | 改为 `[new Date(p.timestamp).getTime(), p.value_v]`（绝对 ms）；tooltip 改为格式化 `d.getHours()`/etc 输出 `HH:MM:SS`，去掉"相对"标注 |

### Step 2: 测试 + E2E ✅
- `python -m pytest tests/` → **26 passed in 0.09s**
- `python -m mcu_trace e2e work/test_enc4 -o work/report.html` → 输出"✿ E2E 完成 ✿"
- `work/report.html`：**283,338 bytes**（≈ 277 KB > 100 KB 阈值）

### Step 3: PyInstaller 打包 ✅
```
65917 INFO: Building PYZ (ZlibArchive) ... completed successfully.
66026 INFO: Building PKG (CArchive) MCU_TRACE.pkg completed successfully.
68275 INFO: Building EXE from EXE-00.toc completed successfully.
70824 INFO: Building COLLECT COLLECT-00.toc completed successfully.
```
- `dist\MCU_TRACE\MCU_TRACE.exe`：17,268,874 bytes（≈ 17.3 MB）

### Step 4: 打包后 HTML 校验 ✅
`dist\MCU_TRACE\_internal\mcu_trace\web\index.html`：
- `xAxis: { type: "time", min: baseMs, max: maxMs` × 3 处（line 589 / 654 / 692）

### Step 5: exe 存活测试 ✅
`Start-Process MCU_TRACE.exe -WindowStyle Hidden` → 5 秒后检查 → **ALIVE**（强制 Stop-Process 终止）

### Step 6: zip 打包 ✅
- `dist\MCU_TRACE_v0.1.0_20260630.zip`：**62,336,114 bytes（≈ 59.4 MB）**
- installer\MCU_TRACE 已同步

## Changed Files

| 路径 | 改动 |
|------|------|
| `src/mcu_trace/web/index.html` | 3 处 X 轴 bug 修复（PSM line 588、SOC line 652、Volt line 679/685/688） |
| `dist/MCU_TRACE/` | 完整重新打包（PyInstaller COLLECT） |
| `dist/MCU_TRACE_v0.1.0_20260630.zip` | 新建（59.4 MB） |
| `installer/MCU_TRACE/` | 同步新 dist |
| `work/report.html` | E2E 产物（277 KB） |

## Notes for Verifier

1. **X 轴原修复版本不可用**：原版 3 处关键 bug 会在用户加载图表时立即触发（PSM/SOC ReferenceError、Volt 数据单位不一致），网页 console 会报错。本轮已修。
2. **Volt tooltip 文案变更**：从原来的"X 分 Y 秒 (相对)"改为 `HH:MM:SS`（与 X 轴刻度统一），不再有"相对"字样，因为现在数据就是绝对时间。
3. **HH:MM:SS formatter 在每个 xAxis 的 `axisLabel.formatter` 中**（不是 tooltip），确保 tick 文字直接显示 HH:MM:SS，不再被 ECharts 自动算成年份范围。
4. **数据语义保持**：PSM/SOC 色块的 `value: [y, startMs, dur, dur]`、Volt 折线 `[tsMs, V]` 全部统一为"绝对毫秒"。
5. **zip 路径**：`E:\Git_PJ\MCU_TRACE\dist\MCU_TRACE_v0.1.0_20260630.zip`
6. **exe 路径**：`E:\Git_PJ\MCU_TRACE\dist\MCU_TRACE\MCU_TRACE.exe`