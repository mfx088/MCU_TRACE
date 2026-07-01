"""分析编排：把 parser + state_machine + keyword + voltage + reset 串起来。

GUI / CLI / E2E 都通过这个统一入口生成 LogSession。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .importer import parse_enc_timestamp
from .keyword import KeywordScanner, scan_events
from .models import LogEvent, LogSession
from .parser import parse_session
from .reset import ResetScanner, extract_rst_events
from .rules_loader import load_merged_rules
from .state_machine import (
    LEGAL_SOC_TRANSITIONS,
    FsmConfig,
    detect_soc_mode_illegal,
    track_psm,
    track_soc_mode,
)
from .voltage import VoltageScanner, extract_voltage_points

log = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent / "assets" / "config"


def analyze_session(
    logcat_files: list[Path],
    *,
    name: str = "session",
    progress_cb=None,
) -> LogSession:
    """从 logcat 文件列表生成完整 LogSession。

    Args:
        logcat_files: 按时间+序号排序的 logcat 路径
        name: 会话名（用于报告标题）

    Returns:
        LogSession 含 events / voltage / rst / fsm / keyword
    """
    session = LogSession(name=name, source_files=[str(p) for p in logcat_files])

    def _step(p, msg):
        if progress_cb:
            try:
                progress_cb(p, msg)
            except Exception:
                pass

    # 1. 准备 enc 时间戳映射（用于跨日日期拼接）
    _step(0.01, "准备 enc 时间戳")
    enc_timestamps: dict[str, datetime] = {}
    for p in logcat_files:
        sub = p.parent.name
        if sub not in enc_timestamps:
            ts = parse_enc_timestamp(sub)
            if ts:
                enc_timestamps[sub] = ts
        # 同时把 enc_files 里的全名也记一下
    log.info("enc_timestamps: %s", {k: v.isoformat() for k, v in enc_timestamps.items()})

    # 2. 解析所有 mcu_trace 事件
    _step(0.05, f"解析 {len(logcat_files)} 个 logcat 文件")
    log.info("解析 %d 个 logcat 文件...", len(logcat_files))
    events = parse_session(logcat_files, enc_timestamps=enc_timestamps)
    session.events = events
    log.info("解析到 %d 条 mcu_trace 事件", len(events))
    _step(0.40, f"解析完成：{len(events)} 条 mcu_trace 事件")

    # 时间范围
    ts_list = [e.timestamp for e in events if e.timestamp]
    if ts_list:
        session.time_range = (min(ts_list), max(ts_list))

    # 3. 加载所有配置
    _step(0.42, "加载规则配置")
    # v0.2+: rules 已合并 builtin + user_rules.json
    rules = load_merged_rules()
    psm_config = FsmConfig.from_json(CONFIG_DIR / "psm_fsm.json")
    soc_config = FsmConfig.from_json(CONFIG_DIR / "soc_fsm.json")

    # 4. PSM 状态机跟踪
    _step(0.45, "PSM 状态机跟踪")
    log.info("PSM 状态机跟踪...")
    session.fsm_transitions.extend(track_psm(events, psm_config))
    _step(0.55, f"PSM 完成：{len(session.fsm_transitions)} 条转换")

    # 5. SoC 模式跟踪
    _step(0.58, "SoC 模式跟踪")
    log.info("SoC 模式跟踪...")
    soc_trans = track_soc_mode(events, soc_config, rules["number_mappings"]["soc_mode"])
    detect_soc_mode_illegal(soc_trans, LEGAL_SOC_TRANSITIONS)
    session.fsm_transitions.extend(soc_trans)
    _step(0.68, f"SoC 完成：{len(soc_trans)} 条模式变化")

    # 6. 电压提取
    _step(0.72, "电压提取")
    log.info("电压提取...")
    v_scanner = VoltageScanner.from_rules(rules)
    session.voltage_points = extract_voltage_points(events, v_scanner)
    _step(0.80, f"电压完成：{len(session.voltage_points)} 个采样点")

    # 7. 复位事件
    _step(0.83, "复位事件提取")
    log.info("复位事件提取...")
    r_scanner = ResetScanner.from_rules(rules)
    session.rst_events = extract_rst_events(events, r_scanner)
    _step(0.90, f"复位完成：{len(session.rst_events)} 个事件")

    # 8. 关键字扫描
    _step(0.93, "关键字扫描")
    log.info("关键字扫描...")
    k_scanner = KeywordScanner.from_rules(rules)
    session.keyword_hits = scan_events(events, k_scanner)
    _step(0.97, f"关键字完成：{len(session.keyword_hits)} 个命中")

    _step(1.0, "分析完成")
    return session


def session_to_dict(session: LogSession) -> dict:
    """LogSession → 字典（用于 JSON 序列化）。"""
    return {
        "name": session.name,
        "stats": session.stats(),
        "source_files": session.source_files,
        "events": [e.to_dict() for e in session.events],
        "voltage_points": [
            {
                "timestamp": p.timestamp.isoformat(),
                "value_v": p.value_v,
                "source": p.source,
                "raw": p.raw,
            }
            for p in session.voltage_points
        ],
        "rst_events": [r.to_dict() for r in session.rst_events],
        "fsm_transitions": [t.to_dict() for t in session.fsm_transitions],
        "keyword_hits": [h.to_dict() for h in session.keyword_hits],
    }

