"""mcu_trace 日志行解析器。

行格式:
    MM-DD HH:MM:SS.ffffff  PID TID L  mcu_trace:  L|MODULE COMPACT_TS| message
    06-29 13:45:53.017942   335   339  I             mcu_trace:  I|PSM 0629134538| PreStandby->Standby, EVENT[14].

设计:
- 用生成器流式处理大文件
- 时间戳优先 logcat 头部（毫秒精度），缺则用 mcu_trace 紧凑时间
- 跨日处理：从文件名（enc 时间戳）拿日期前缀拼接
- 跨年：默认当前年（2026），跨年 log 用户需在 GUI 配置
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable, Iterator, Optional

from .models import LogEvent, Severity

log = logging.getLogger(__name__)


# mcu_trace 行正则
# 完整: <ts> <pid> <tid> <level> mcu_trace: <mcu_level>|<module> <compact_ts>| <msg>
_LOG_LINE_RE = re.compile(
    r"^(?P<logcat_ts>\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\s+"
    r"(?P<pid>\d+)\s+(?P<tid>\d+)\s+"
    r"(?P<logcat_level>[VDIWE])\s+"
    r"mcu_trace:\s+"
    r"(?P<mcu_level>[IWDENF])\|(?P<module>\w+)\s+"
    r"(?P<compact_ts>\d{10})\|"
    r"\s*(?P<message>.*)$"
)

# 普通 logcat 行（用作兜底解析，没命中 mcu_trace 也存一份）
_LOGCAT_LINE_RE = re.compile(
    r"^(?P<logcat_ts>\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\s+"
    r"(?P<pid>\d+)\s+(?P<tid>\d+)\s+"
    r"(?P<logcat_level>[VDIWE])\s+"
    r"(?P<tag>\S+):\s+"
    r"(?P<message>.*)$"
)

_COMPACT_TS_RE = re.compile(r"^(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})$")  # MMDDHHMMSS

ProgressCb = Callable[[int, int], None]   # (lines_done, lines_total_or_-1)


def parse_logcat_file(
    path: Path,
    *,
    base_date: Optional[datetime] = None,
    progress_cb: Optional[ProgressCb] = None,
) -> Iterator[LogEvent]:
    """解析单个 logcat 文件，返回 LogEvent 生成器。

    Args:
        path: logcat 文件路径
        base_date: 日期基准（用于跨日拼接），通常是 .enc 文件名时间戳的日期部分
        progress_cb: 进度回调 (lines_done, -1)
    """
    name = path.name
    log.debug("parse: %s", name)
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                ev = _parse_line(line.rstrip("\n"), name, i, base_date)
                if ev is not None:
                    yield ev
                if progress_cb and i % 5000 == 0:
                    progress_cb(i, -1)
    except OSError as e:
        log.error("打开文件失败 %s: %s", name, e)


def _parse_line(
    line: str,
    source_file: str,
    offset: int,
    base_date: Optional[datetime] = None,
) -> Optional[LogEvent]:
    """解析单行。命中 mcu_trace 格式才返回 LogEvent，否则返回 None（跳过非 mcu_trace 行）。"""
    if not line.strip():
        return None

    m = _LOG_LINE_RE.match(line)
    if m:
        return _build_mcu_trace_event(m, source_file, offset, base_date)

    # 非 mcu_trace 行：用户不关心（按设计只分析 mcu_trace）
    # 但保留 mcu_trace: 前缀的 fallback：如果上面没命中但行含 mcu_trace: 也跳过
    return None


def _build_mcu_trace_event(
    m: re.Match,
    source_file: str,
    offset: int,
    base_date: Optional[datetime],
) -> LogEvent:
    """构造 mcu_trace LogEvent。"""
    gd = m.groupdict()
    logcat_ts_str = gd["logcat_ts"]
    compact_ts = gd["compact_ts"]

    # 1. 优先 logcat 头部毫秒精度
    ts = _parse_logcat_ts(logcat_ts_str, base_date)
    # 2. 兜底：mcu_trace 紧凑时间（秒精度，缺毫秒）
    if ts is None and compact_ts:
        ts = _parse_compact_ts(compact_ts, base_date)

    # 严重度：mcu_trace 内层级别 → Severity
    severity = _mcu_level_to_severity(gd["mcu_level"])

    return LogEvent(
        source_file=source_file,
        source_offset=offset,
        timestamp=ts,
        compact_ts=compact_ts,
        pid=int(gd["pid"]),
        tid=int(gd["tid"]),
        logcat_level=gd["logcat_level"],
        mcu_level=gd["mcu_level"],
        module=gd["module"],
        message=gd["message"],
        is_mcu_trace=True,
        severity=severity,
    )


def _parse_logcat_ts(ts_str: str, base_date: Optional[datetime]) -> Optional[datetime]:
    """解析 logcat 时间戳 'MM-DD HH:MM:SS.ffffff'。"""
    # 跨年处理：默认用 base_date 的年，或者当前年
    try:
        # datetime.strptime 不支持 microsecond 6 位，用 fromisoformat 也不支持
        # 自己解析
        m = re.match(
            r"^(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})\.(\d{6})$", ts_str
        )
        if not m:
            return None
        mo, d, h, mi, s, us = m.groups()
        year = base_date.year if base_date else datetime.now().year
        return datetime(int(year), int(mo), int(d), int(h), int(mi), int(s), int(us))
    except (ValueError, AttributeError):
        return None


def _parse_compact_ts(compact: str, base_date: Optional[datetime]) -> Optional[datetime]:
    """解析 mcu_trace 紧凑时间 'MMDDHHMMSS'。"""
    m = _COMPACT_TS_RE.match(compact)
    if not m:
        return None
    mo, d, h, mi, s = m.groups()
    try:
        year = base_date.year if base_date else datetime.now().year
        return datetime(int(year), int(mo), int(d), int(h), int(mi), int(s))
    except ValueError:
        return None


def _mcu_level_to_severity(mcu_level: str) -> Severity:
    """mcu_trace 内层级别 → Severity。

    E/F → CRITICAL
    W     → HIGH
    N     → MEDIUM (Notification)
    I/D   → INFO
    """
    return {
        "E": Severity.CRITICAL,
        "F": Severity.CRITICAL,
        "W": Severity.HIGH,
        "N": Severity.MEDIUM,
        "I": Severity.INFO,
        "D": Severity.INFO,
    }.get(mcu_level, Severity.INFO)


def parse_session(
    logcat_files: Iterable[Path],
    *,
    enc_timestamps: Optional[dict[str, datetime]] = None,
    progress_cb: Optional[Callable[[str, int, int], None]] = None,
) -> list[LogEvent]:
    """解析一组 logcat 文件，返回全部 LogEvent 列表（按时间排序）。

    Args:
        logcat_files: logcat 文件路径列表（已按时间+序号排序）
        enc_timestamps: {enc_name(去后缀): datetime}  用于跨日日期拼接
        progress_cb: (file_name, done, total) 回调
    """
    files = list(logcat_files)
    events: list[LogEvent] = []
    enc_timestamps = enc_timestamps or {}

    for fi, fpath in enumerate(files):
        # 找到对应的 enc 时间戳
        # 子目录名 = enc 去后缀，如 001_001_20260629122126
        sub_name = fpath.parent.name
        base_date = enc_timestamps.get(sub_name)

        def _file_progress(done: int, total: int) -> None:
            if progress_cb:
                progress_cb(fpath.name, done, fi + 1)

        for ev in parse_logcat_file(fpath, base_date=base_date, progress_cb=_file_progress):
            events.append(ev)

    # 按时间排序（无时间的放最后）
    events.sort(
        key=lambda e: (e.timestamp or datetime.min, e.source_file, e.source_offset)
    )
    return events
