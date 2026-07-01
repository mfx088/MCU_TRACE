"""HTML 报告生成（小白友好版）。

输出自包含单文件 HTML：
- 头部 TL;DR 卡片（一句话总结）
- 概览统计
- matplotlib 渲染的 PNG 图表（base64 嵌入）
  - FSM 时序（水平色块图 + 中文状态名 + 配色）
  - 电压曲线（正常范围带 + 异常高亮）
  - 关键字分类
- 状态机时序表（中文）
- 复位事件表（中文）
- 关键字命中表（中文 category）
"""
from __future__ import annotations

import base64
import io
import logging
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager as _fm
from matplotlib.patches import Patch

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import FsmTransition, LogSession, RstEvent, Severity, VoltagePoint

log = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent.parent / "assets" / "templates"


def _setup_cjk_font() -> Optional[str]:
    """注册系统中可用的 CJK 字体，避免 matplotlib 报 "Glyph missing"。

    优先级：优先静态字体（避免 Variable Font 在 bold 上出问题），
    然后才是 NotoSansSC-VF / SourceHanSans。
    返回最终生效的字体名（用于 rcParams）。
    """
    cjk_candidates = [
        # 静态 TTF/TTC 优先（兼容 bold / italic）
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyh.ttf",
        r"C:\Windows\Fonts\simkai.ttf",
        # 静态 OTF（如果存在）
        r"C:\Windows\Fonts\SourceHanSansSC-Regular.otf",
        r"C:\Windows\Fonts\SourceHanSansCN-Regular.otf",
        # Variable Font 兜底（matplotlib 可能识别 bold 失败）
        r"C:\Windows\Fonts\NotoSansSC-VF.ttf",
        # macOS / Linux
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]
    chosen_name: Optional[str] = None
    for fp in cjk_candidates:
        if Path(fp).exists():
            try:
                _fm.fontManager.addfont(fp)
                # 从文件名推断名字
                stem = Path(fp).stem.lower()
                if "simhei" in stem:
                    chosen_name = "SimHei"
                elif "simsun" in stem:
                    chosen_name = "SimSun"
                elif "msyh" in stem or "yahei" in stem:
                    chosen_name = "Microsoft YaHei"
                elif "simkai" in stem or "kaiti" in stem:
                    chosen_name = "KaiTi"
                elif "notosanssc" in stem or "noto" in stem:
                    chosen_name = "Noto Sans SC"
                elif "sourcehan" in stem:
                    chosen_name = "Source Han Sans SC"
                elif "pingfang" in stem:
                    chosen_name = "PingFang SC"
                else:
                    chosen_name = Path(fp).stem
                break
            except Exception:
                continue
    return chosen_name


_CJK_FONT_NAME = _setup_cjk_font()
if _CJK_FONT_NAME:
    plt.rcParams["font.sans-serif"] = [_CJK_FONT_NAME, "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    log.info("matplotlib CJK 字体: %s", _CJK_FONT_NAME)
else:
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    log.warning("未找到 CJK 字体，中文可能显示为方块")


# ============================================================
# v0.2.1: 现代 matplotlib 主题
# ============================================================
def _apply_modern_style():
    """应用现代化主题：白底、淡网格、无顶/右轴、统一字号。"""
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#e5e7eb",
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "grid.color": "#f3f4f6",
        "grid.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.labelsize": 11,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.titlepad": 14,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "xtick.color": "#6b7280",
        "ytick.color": "#6b7280",
        "legend.frameon": False,
        "legend.fontsize": 10,
        "figure.dpi": 110,
    })


_apply_modern_style()


# ============================================================
# 状态名 → 中文 + 颜色 映射（小白友好）
# ============================================================

# PSM 状态
PSM_STATE_DISPLAY: dict[str, tuple[str, str, int]] = {
    # state_name -> (中文名, 颜色, Y 坐标)
    "OFF":                 ("关机",          "#4b5563", 0),
    "PreStandby":          ("预待机",         "#fde68a", 1),
    "Standby":             ("待机",          "#3b82f6", 2),
    "Normal":              ("正常运行",       "#10b981", 3),
    "PrepareSleep_Step1":  ("准备休眠",       "#fbbf24", 4),
    "PreSleep_1":          ("预休眠-1",       "#a78bfa", 5),
    "PreSleep_2":          ("预休眠-2",       "#a78bfa", 6),
    "WatiEvnShutDown":      ("等待关闭",       "#f87171", 7),
    "WakeUp":              ("唤醒中",         "#06b6d4", 8),
    "StartUp_1":           ("启动中-1",       "#fbbf24", 9),
    "StartUp_2":           ("启动中-2",       "#fbbf24", 10),
}

# SoC 状态
SOC_STATE_DISPLAY: dict[str, tuple[str, str, int]] = {
    "OFF":         ("SoC 关机",       "#4b5563", 0),
    "STANDBY":     ("SoC 待机",       "#3b82f6", 1),
    "TEMPO_ON":    ("SoC 暂态开机",   "#06b6d4", 2),
    "NORMAL":      ("SoC 正常运行",   "#10b981", 3),
    "TEMPO_OFF":   ("SoC 暂态关机",   "#f97316", 4),
    "STR":         ("SoC 深度休眠",   "#8b5cf6", 5),
    "MAX":         ("SoC 上限",       "#6b7280", 6),
}

# 关键字 category → 中文 + emoji
CATEGORY_DISPLAY: dict[str, tuple[str, str]] = {
    # category -> (中文名, emoji)
    "fault":      ("故障",      "🚨"),
    "reset":      ("复位",      "🔄"),
    "watchdog":   ("看门狗",    "⏰"),
    "voltage":    ("电压",      "⚡"),
    "comm":       ("通信",      "📡"),
    "hsm":        ("安全引擎",  "🔐"),
    "retry":      ("重试",      "🔁"),
    "unknown":    ("其他",      "❓"),
}

# 严重度 → 中文 + emoji + 颜色
SEVERITY_DISPLAY: dict[int, tuple[str, str, str]] = {
    # Severity -> (中文, emoji, 颜色)
    0:  ("信息",   "ℹ️",  "#6b7280"),
    1:  ("低",     "🟢",  "#10b981"),
    2:  ("中",     "🟡",  "#eab308"),
    3:  ("高",     "🟠",  "#f97316"),
    4:  ("严重",   "🔴",  "#ef4444"),
}


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ============================================================
# 电压曲线（友好版 v0.2.1：渐变填充 + 标值 + 改进 1 点情况）
# ============================================================

def plot_voltage_curve_v2(points: list[VoltagePoint]) -> Optional[str]:
    """电压曲线：标"正常范围"灰色带 + 异常点高亮 + 渐变填充。"""
    if not points:
        return None
    fig, ax = plt.subplots(figsize=(13, 5.5))

    # 计算 Y 轴范围（数据稀少时也能好看）
    all_vs = [p.value_v for p in points]
    v_min, v_max = min(all_vs), max(all_vs)
    # 至少 ±1V padding，并覆盖 0-18V 范围
    y_low = max(0, min(v_min - 1, 8))
    y_high = max(v_max + 1, 18)
    ax.set_ylim(y_low, y_high)

    # 正常电压范围：车载电池典型 9V-16V（标绿色带）
    ax.axhspan(9, 16, color="#10b981", alpha=0.10, label="正常范围 (9-16V)", zorder=0)
    # 异常阈值线
    ax.axhline(9, color="#f97316", linestyle="--", linewidth=1.0, alpha=0.7, zorder=1)
    ax.axhline(16, color="#f97316", linestyle="--", linewidth=1.0, alpha=0.7, zorder=1)
    # 阈值标签（放右侧更安全）
    ax.text(0.998, 0.04, "  低压告警 9V  ", transform=ax.get_yaxis_transform(),
            color="#f97316", fontsize=9, va="bottom", ha="right",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="#f97316", linewidth=0.8, alpha=0.9))
    ax.text(0.998, 0.93, "  过压告警 16V  ", transform=ax.get_yaxis_transform(),
            color="#f97316", fontsize=9, va="top", ha="right",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="#f97316", linewidth=0.8, alpha=0.9))

    # 按 source 分组画
    source_groups: dict[str, list[tuple[datetime, float]]] = {}
    for p in points:
        source_groups.setdefault(p.source, []).append((p.timestamp, p.value_v))

    color_cycle = ["#3b82f6", "#10b981", "#8b5cf6", "#f97316", "#06b6d4"]
    for i, (source, items) in enumerate(source_groups.items()):
        ts, vs = zip(*items)
        color = color_cycle[i % len(color_cycle)]
        # 渐变填充（仅在多点时）
        if len(items) >= 2:
            ax.fill_between(ts, vs, y_low, color=color, alpha=0.10, zorder=2)
        ax.plot(ts, vs, marker="o", markersize=6, linewidth=2.0,
                color=color, label=f"{source}（{len(items)} 点）",
                markeredgecolor="white", markeredgewidth=1.2, zorder=4)

        # 异常点（< 9V 或 > 16V）红色高亮
        for t, v in items:
            if v < 9 or v > 16:
                ax.scatter([t], [v], color="#ef4444", s=120, zorder=6,
                           edgecolor="white", linewidth=1.8, marker="D")

    # 标值（点数 ≤ 30 时全部标）
    for p in points:
        if len(points) <= 30:
            ax.annotate(f"{p.value_v:.2f}V", (p.timestamp, p.value_v),
                       xytext=(0, 10), textcoords="offset points",
                       ha="center", fontsize=9, color="#1f2937",
                       bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                                 edgecolor="#d1d5db", alpha=0.9))

    ax.set_xlabel("时间", fontsize=11, color="#374151")
    ax.set_ylabel("电压 (V)", fontsize=11, color="#374151")
    ax.set_title("整车电池电压变化", fontsize=14, fontweight="bold",
                 color="#1f2937", loc="left", pad=12)
    ax.legend(loc="upper left", fontsize=9, ncol=2, framealpha=0.95,
              edgecolor="#e5e7eb")
    ax.grid(True, alpha=0.4, linestyle="-", linewidth=0.6)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax.tick_params(axis="both", which="major", length=4, color="#9ca3af")
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()
    return _fig_to_base64(fig)


# ============================================================
# FSM 时序图（小白友好版：水平色块图）
# ============================================================

def plot_fsm_timeline_v2(
    transitions: list[FsmTransition],
    state_display: dict[str, tuple[str, str, int]],
    title: str,
) -> Optional[str]:
    """FSM 时序图：每个状态是水平色块，一眼看出时间段。

    state_display: {state_name: (中文名, 颜色, Y坐标)}
    """
    if not transitions:
        return None

    sorted_trans = sorted([t for t in transitions if t.timestamp], key=lambda t: t.timestamp)
    if not sorted_trans:
        return None

    # 构建时间段：[(start_num, duration_sec, y, color, label), ...]
    segments = []
    for i, t in enumerate(sorted_trans):
        start = t.timestamp
        if i + 1 < len(sorted_trans):
            end = sorted_trans[i + 1].timestamp
        else:
            end = start + timedelta(seconds=2)
        duration = (end - start).total_seconds()
        if duration <= 0:
            duration = 0.5  # 至少 0.5s，色块可见
        if t.to_state in state_display:
            cn, color, y = state_display[t.to_state]
            segments.append((mdates.date2num(start), duration, y, color, cn, t.is_illegal, t))

    if not segments:
        return None

    # v0.2.1: 根据状态数动态调整高度（多状态 → 更高）
    n_states = len(set(y for _, _, y, _, _, _, _ in segments))
    fig_height = max(5.5, min(8.5, 4.5 + n_states * 0.35))
    fig, ax = plt.subplots(figsize=(13, fig_height))

    # 画色块
    illegal_segments = []
    for start_num, dur, y, color, cn, is_illegal, t in segments:
        ax.broken_barh([(start_num, dur)], (y - 0.38, 0.76),
                       facecolors=color, edgecolor="white", linewidth=0.8)
        if is_illegal:
            illegal_segments.append((start_num, dur, y, t))

    # 非法跳转：红色粗箭头 + 文字（仅 1-3 个时显示，避免拥挤）
    for start_num, dur, y, t in illegal_segments[:5]:
        mid_x = start_num + dur / 2
        ax.annotate(
            "",
            xy=(start_num, y + 0.5),
            xytext=(start_num, y - 1.5),
            arrowprops=dict(arrowstyle="->", color="#dc2626", lw=2.5),
        )
        ax.text(mid_x, y + 0.7, "⚠ 异常",
                color="#dc2626", fontsize=10, ha="center", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#fef2f2",
                          edgecolor="#dc2626", linewidth=1))

    # Y 轴：状态名（中文）
    y_ticks = []
    y_labels = []
    seen_y = set()
    for cn, color, y in state_display.values():
        if y not in seen_y:
            seen_y.add(y)
            y_ticks.append(y)
            label = next((cn for scn, _, sy in state_display.values() if sy == y), "")
            y_labels.append(label)

    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels, fontsize=10, color="#374151")
    ax.set_ylim(-1.5, max(y_ticks) + 1.5)
    ax.invert_yaxis()  # 让"开机"在顶部、"关机"在底部（自然阅读顺序）

    # X 轴
    ax.set_xlabel("时间", fontsize=11, color="#374151")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    fig.autofmt_xdate(rotation=0, ha="center")

    # 标题
    ax.set_title(title, fontsize=14, fontweight="bold", color="#1f2937",
                 loc="left", pad=14)
    ax.grid(True, alpha=0.3, axis="x", linestyle="-", linewidth=0.6)
    ax.set_axisbelow(True)

    # 图例（颜色 → 状态）放在底部
    legend_items = []
    seen = set()
    for state_name, (cn, color, y) in state_display.items():
        if state_name not in seen:
            seen.add(state_name)
            legend_items.append(Patch(facecolor=color, label=f"{cn}", alpha=0.9))
    if illegal_segments:
        from matplotlib.lines import Line2D
        legend_items.append(Line2D([0], [0], color="#dc2626", marker="^",
                                    linestyle="None", markersize=10, label="非法跳转"))
    ncol = min(len(legend_items), 6)
    ax.legend(handles=legend_items, loc="upper center", bbox_to_anchor=(0.5, -0.12),
              fontsize=9, ncol=ncol, framealpha=0.95, edgecolor="#e5e7eb",
              title="图例", title_fontsize=10)

    fig.tight_layout()
    return _fig_to_base64(fig)


# ============================================================
# 关键字分类柱状图
# ============================================================

def plot_keyword_stats_v2(keyword_hits: list) -> Optional[str]:
    """v0.2.1: 横向柱状图，按数量降序，颜色按最高严重度。"""
    if not keyword_hits:
        return None
    cat_counter = Counter(h.category for h in keyword_hits)
    # 按数量降序
    items = sorted(cat_counter.items(), key=lambda kv: -kv[1])
    cats = [k for k, _ in items]
    counts = [v for _, v in items]

    labels_zh = []
    colors = []
    for c in cats:
        zh, _emoji = CATEGORY_DISPLAY.get(c, (c, ""))
        labels_zh.append(zh)
        max_sev = max((h.severity for h in keyword_hits if h.category == c),
                      default=Severity.INFO)
        colors.append(SEVERITY_DISPLAY.get(int(max_sev), ("", "", "#6b7280"))[2])

    # 高度按类别数动态调整
    n = len(cats)
    fig_height = max(3.5, min(7, 2.0 + n * 0.5))
    fig, ax = plt.subplots(figsize=(11, fig_height))

    y_pos = list(range(n))[::-1]  # 最多的在顶部
    bars = ax.barh(y_pos, counts, color=colors, edgecolor="white", linewidth=1.2, height=0.65)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels_zh, fontsize=11, color="#374151")
    ax.set_xlabel("命中次数", fontsize=11, color="#374151")
    ax.set_title("异常事件分类（颜色越红越严重，按数量降序）", fontsize=14,
                 fontweight="bold", color="#1f2937", loc="left", pad=12)
    ax.grid(True, alpha=0.4, axis="x", linestyle="-", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.invert_yaxis()  # 让最大值在顶部

    # 在柱子右端标值
    max_count = max(counts) if counts else 1
    ax.set_xlim(0, max_count * 1.18)
    for bar, count in zip(bars, counts):
        ax.text(bar.get_width() + max_count * 0.02, bar.get_y() + bar.get_height() / 2,
                str(count), ha="left", va="center", fontsize=11,
                fontweight="bold", color="#1f2937")

    fig.tight_layout()
    return _fig_to_base64(fig)


# ============================================================
# TL;DR 一句话总结
# ============================================================

def generate_tldr(session: LogSession) -> dict:
    """生成报告头部 TL;DR 卡片。"""
    illegal = [t for t in session.fsm_transitions if t.is_illegal]
    critical_hits = [h for h in session.keyword_hits if h.severity == Severity.CRITICAL]
    high_hits = [h for h in session.keyword_hits if h.severity >= Severity.HIGH]
    rst_critical = [r for r in session.rst_events if r.severity >= Severity.HIGH]

    issues = []
    if illegal:
        # 找最严重的非法跳转
        sample = illegal[0]
        if sample.fsm_name == "PSM":
            from_zh = PSM_STATE_DISPLAY.get(sample.from_state, (sample.from_state, "#6b7280", 0))[0]
            to_zh = PSM_STATE_DISPLAY.get(sample.to_state, (sample.to_state, "#6b7280", 0))[0]
        else:
            from_zh = SOC_STATE_DISPLAY.get(sample.from_state, (sample.from_state, "#6b7280", 0))[0]
            to_zh = SOC_STATE_DISPLAY.get(sample.to_state, (sample.to_state, "#6b7280", 0))[0]
        issues.append({
            "emoji": "⚠️",
            "text": f"发现 {len(illegal)} 次状态机异常跳转（如 {from_zh}→{to_zh} 跳过中间状态）",
            "severity": "high",
        })
    if rst_critical:
        issues.append({
            "emoji": "🔄",
            "text": f"MCU 复位 {len(rst_critical)} 次（最高严重度）",
            "severity": "high",
        })
    elif session.rst_events:
        issues.append({
            "emoji": "🔄",
            "text": f"MCU 复位 {len(session.rst_events)} 次",
            "severity": "medium",
        })
    if critical_hits:
        issues.append({
            "emoji": "🚨",
            "text": f"严重故障 {len(critical_hits)} 个",
            "severity": "critical",
        })
    if high_hits:
        issues.append({
            "emoji": "🟠",
            "text": f"高级告警 {len(high_hits)} 个",
            "severity": "medium",
        })

    # 统计
    duration_min = 0
    if session.time_range[0] and session.time_range[1]:
        duration_min = (session.time_range[1] - session.time_range[0]).total_seconds() / 60

    return {
        "issues": issues,
        "duration_min": round(duration_min, 1),
        "event_count": session.stats()["mcu_trace_events"],
        "has_issues": len(issues) > 0,
    }


# ============================================================
# 主入口
# ============================================================

def export_html_report(session: LogSession, output_path: Path) -> Path:
    """导出 HTML 报告。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    log.info("生成图表...")
    voltage_png = plot_voltage_curve_v2(session.voltage_points)

    psm_trans = [t for t in session.fsm_transitions if t.fsm_name == "PSM"]
    psm_png = plot_fsm_timeline_v2(
        psm_trans, PSM_STATE_DISPLAY,
        "MCU 电源状态机时序（彩色块 = 状态持续时间）",
    )

    soc_trans = [t for t in session.fsm_transitions if t.fsm_name == "SoCMode"]
    soc_png = plot_fsm_timeline_v2(
        soc_trans, SOC_STATE_DISPLAY,
        "SoC 系统模式时序（彩色块 = 模式持续时间）",
    )

    kw_png = plot_keyword_stats_v2(session.keyword_hits)

    # 状态转换表（中文）
    transition_table = []
    for t in session.fsm_transitions:
        from_state = t.from_state
        to_state = t.to_state
        if t.fsm_name == "PSM":
            from_cn = PSM_STATE_DISPLAY.get(from_state, (from_state, "#6b7280", 0))[0]
            to_cn = PSM_STATE_DISPLAY.get(to_state, (to_state, "#6b7280", 0))[0]
        else:
            from_cn = SOC_STATE_DISPLAY.get(from_state, (from_state, "#6b7280", 0))[0]
            to_cn = SOC_STATE_DISPLAY.get(to_state, (to_state, "#6b7280", 0))[0]
        transition_table.append({
            "fsm": "MCU 电源" if t.fsm_name == "PSM" else "SoC 系统",
            "timestamp": t.timestamp.strftime("%H:%M:%S.%f")[:-3] if t.timestamp else "-",
            "from": from_cn,
            "to": to_cn,
            "event": t.event_id or "-",
            "illegal": "⚠️" if t.is_illegal else "",
            "reason": t.reason,
        })

    # 关键字命中表（中文 category）
    keyword_table = []
    for h in session.keyword_hits:
        cat_zh, cat_emoji = CATEGORY_DISPLAY.get(h.category, (h.category, "❓"))
        sev_zh, sev_emoji, sev_color = SEVERITY_DISPLAY.get(int(h.severity), ("?", "?", "#6b7280"))
        keyword_table.append({
            "timestamp": h.event.timestamp.strftime("%H:%M:%S.%f")[:-3] if h.event.timestamp else "-",
            "category_emoji": cat_emoji,
            "category_zh": cat_zh,
            "severity_zh": sev_zh,
            "severity_color": sev_color,
            "severity_emoji": sev_emoji,
            "module": h.event.module,
            "matched": h.matched_text,
            "message": h.event.message[:120],
        })

    # 复位事件表（中文）
    rst_table = []
    for r in session.rst_events:
        sev_zh, sev_emoji, sev_color = SEVERITY_DISPLAY.get(int(r.severity), ("?", "?", "#6b7280"))
        rst_table.append({
            "timestamp": r.timestamp.strftime("%H:%M:%S.%f")[:-3] if r.timestamp else "-",
            "rst_type": r.rst_type_name,
            "reason": r.reason_name,
            "severity_zh": f"{sev_emoji} {sev_zh}",
            "severity_color": sev_color,
            "raw": r.raw[:100],
        })

    tldr = generate_tldr(session)
    stats = session.stats()

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("report.html")
    html = template.render(
        session_name=session.name,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        stats=stats,
        tldr=tldr,
        voltage_png=voltage_png,
        psm_png=psm_png,
        soc_png=soc_png,
        keyword_png=kw_png,
        keyword_table=keyword_table,
        rst_table=rst_table,
        transition_table=transition_table,
        illegal_count=sum(1 for t in session.fsm_transitions if t.is_illegal),
    )

    output_path.write_text(html, encoding="utf-8")
    log.info("HTML 报告已写入: %s", output_path)
    return output_path
