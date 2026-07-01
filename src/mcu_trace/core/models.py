"""数据模型：LogEvent、LogSession、VoltagePoint、RstEvent、FsmTransition、KeywordHit。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Optional


class Severity(IntEnum):
    """严重度（用于 HTML 报告着色）"""
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class LogEvent:
    """单条解析后的 mcu_trace 日志事件。

    行格式: MM-DD HH:MM:SS.ffffff  PID TID L  mcu_trace:  L|MODULE COMPACT_TS| message
    """
    # 来源
    source_file: str           # logcat 文件名（不含路径）
    source_offset: int         # 在文件中的行号（0-indexed）

    # 时间戳（优先 logcat 头部毫秒精度）
    timestamp: Optional[datetime] = None
    compact_ts: str = ""       # MMDDHHMMSS（来自 mcu_trace 内层）

    # logcat 头
    pid: int = 0
    tid: int = 0
    logcat_level: str = ""     # V/D/I/W/E

    # mcu_trace 内层
    mcu_level: str = ""        # I/W/D/E/N/F
    module: str = ""           # PSM / PwrSuplyM / ...
    message: str = ""

    # 派生
    is_mcu_trace: bool = False # 是否是 mcu_trace 行（区分普通 logcat）
    severity: Severity = Severity.INFO

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "source_offset": self.source_offset,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "compact_ts": self.compact_ts,
            "pid": self.pid,
            "tid": self.tid,
            "logcat_level": self.logcat_level,
            "mcu_level": self.mcu_level,
            "module": self.module,
            "message": self.message,
            "is_mcu_trace": self.is_mcu_trace,
            "severity": int(self.severity),
        }


@dataclass
class VoltagePoint:
    """电压采样点。"""
    timestamp: datetime
    value_v: float            # 单位 V
    source: str               # 哪个 extractor 提取的
    raw: str                  # 原始行片段


@dataclass
class RstEvent:
    """MCU 复位事件。"""
    timestamp: Optional[datetime]
    rst_type_raw: int
    rst_type_name: str
    reason_raw: int
    reason_name: str
    severity: Severity
    raw: str
    source_file: str
    source_offset: int

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "rst_type_raw": self.rst_type_raw,
            "rst_type_name": self.rst_type_name,
            "reason_raw": self.reason_raw,
            "reason_name": self.reason_name,
            "severity": int(self.severity),
            "raw": self.raw,
            "source_file": self.source_file,
            "source_offset": self.source_offset,
        }


@dataclass
class FsmTransition:
    """状态机的一次状态转换。"""
    fsm_name: str             # "PSM" / "SoCMode"
    timestamp: Optional[datetime]
    from_state: str
    to_state: str
    event_id: Optional[str] = None    # EVENT[14] 这种
    raw: str = ""
    source_file: str = ""
    source_offset: int = 0
    is_illegal: bool = False          # 非法跳转
    reason: str = ""                  # 非法原因描述

    def to_dict(self) -> dict:
        return {
            "fsm_name": self.fsm_name,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "event_id": self.event_id,
            "raw": self.raw,
            "source_file": self.source_file,
            "source_offset": self.source_offset,
            "is_illegal": self.is_illegal,
            "reason": self.reason,
        }


@dataclass
class KeywordHit:
    """关键字命中。"""
    event: LogEvent
    pattern: str              # 命中的正则 pattern
    category: str             # "fault" / "voltage" / "comm" / "hsm" ...
    severity: Severity
    matched_text: str         # 命中片段

    def to_dict(self) -> dict:
        return {
            **self.event.to_dict(),
            "pattern": self.pattern,
            "category": self.category,
            "matched_text": self.matched_text,
            "severity": int(self.severity),
        }


@dataclass
class LogSession:
    """一次会话的完整分析结果。"""
    name: str
    source_files: list[str] = field(default_factory=list)
    events: list[LogEvent] = field(default_factory=list)
    voltage_points: list[VoltagePoint] = field(default_factory=list)
    rst_events: list[RstEvent] = field(default_factory=list)
    fsm_transitions: list[FsmTransition] = field(default_factory=list)
    keyword_hits: list[KeywordHit] = field(default_factory=list)

    time_range: tuple[Optional[datetime], Optional[datetime]] = (None, None)

    def stats(self) -> dict:
        illegal = [t for t in self.fsm_transitions if t.is_illegal]
        return {
            "total_events": len(self.events),
            "mcu_trace_events": sum(1 for e in self.events if e.is_mcu_trace),
            "source_files": len(self.source_files),
            "voltage_points": len(self.voltage_points),
            "rst_events": len(self.rst_events),
            "fsm_transitions": len(self.fsm_transitions),
            "fsm_illegal": len(illegal),
            "keyword_hits": len(self.keyword_hits),
            "time_range": [
                self.time_range[0].isoformat() if self.time_range[0] else None,
                self.time_range[1].isoformat() if self.time_range[1] else None,
            ],
        }
