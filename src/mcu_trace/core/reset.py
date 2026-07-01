"""MCU 复位事件提取。

匹配 mcu_trace 里 RST TYPE[X],REASON[Y] 模式，按 builtin_rules.json 映射。
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from .models import LogEvent, RstEvent, Severity

log = logging.getLogger(__name__)

_RST_PATTERN = re.compile(r"RST TYPE\[(\d+)\],REASON\[(\d+)\]")

SEVERITY_MAP = {
    "info": Severity.INFO,
    "low": Severity.LOW,
    "medium": Severity.MEDIUM,
    "high": Severity.HIGH,
    "critical": Severity.CRITICAL,
}


class ResetScanner:
    def __init__(self, rst_type_map: dict, reason_map: dict, severity_map: dict):
        self.rst_type_map = rst_type_map
        self.reason_map = reason_map
        self.severity_map = severity_map

    @classmethod
    def from_json(cls, path: Path) -> "ResetScanner":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return cls.from_rules(data)

    @classmethod
    def from_rules(cls, rules: dict) -> "ResetScanner":
        """v0.2+: 从已合并的 rules dict 构造。"""
        mappings = rules.get("number_mappings", {})
        severity = rules.get("reason_severity", {})
        return cls(
            rst_type_map=mappings.get("rst_type", {}),
            reason_map=mappings.get("rst_reason", {}),
            severity_map=severity,
        )

    def scan(self, event: LogEvent) -> Optional[RstEvent]:
        if not event.is_mcu_trace:
            return None
        m = _RST_PATTERN.search(event.message)
        if not m:
            return None
        rst_raw, reason_raw = m.groups()
        rst_int = int(rst_raw)
        reason_int = int(reason_raw)
        return RstEvent(
            timestamp=event.timestamp,
            rst_type_raw=rst_int,
            rst_type_name=self.rst_type_map.get(rst_raw, f"TYPE_{rst_raw}"),
            reason_raw=reason_int,
            reason_name=self.reason_map.get(reason_raw, f"REASON_{reason_raw}"),
            severity=SEVERITY_MAP.get(self.severity_map.get(reason_raw, "info"), Severity.INFO),
            raw=event.message,
            source_file=event.source_file,
            source_offset=event.source_offset,
        )


def extract_rst_events(events: list[LogEvent], scanner: ResetScanner) -> list[RstEvent]:
    out: list[RstEvent] = []
    for ev in events:
        r = scanner.scan(ev)
        if r:
            out.append(r)
    return out

