"""电压数值提取。

支持多个 extractor，每个独立配置正则和单位换算。
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import LogEvent, VoltagePoint

log = logging.getLogger(__name__)


@dataclass
class VoltageExtractor:
    name: str
    pattern: re.Pattern
    unit: str          # "mV" / "V"
    scale: float       # 转换为 V 的系数
    enabled: bool = True


class VoltageScanner:
    """多 extractor 扫描器。"""

    def __init__(self, extractors: list[VoltageExtractor]):
        self.extractors = [e for e in extractors if e.enabled]

    @classmethod
    def from_json(cls, path: Path) -> "VoltageScanner":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return cls.from_rules(data)

    @classmethod
    def from_rules(cls, rules: dict) -> "VoltageScanner":
        """v0.2+: 从已合并的 rules dict 构造。"""
        exts: list[VoltageExtractor] = []
        for e in rules.get("voltage_extractors", []):
            try:
                pat = re.compile(e["pattern"])
                exts.append(VoltageExtractor(
                    name=e["name"],
                    pattern=pat,
                    unit=e.get("unit", "V"),
                    scale=float(e.get("scale", 1.0)),
                    enabled=e.get("enabled", True),
                ))
            except re.error as err:
                log.warning("电压正则编译失败: %s → %s", e["pattern"], err)
        return cls(exts)

    def scan(self, event: LogEvent) -> list[VoltagePoint]:
        if not event.is_mcu_trace or event.timestamp is None:
            return []
        points: list[VoltagePoint] = []
        for ext in self.extractors:
            m = ext.pattern.search(event.message)
            if m:
                try:
                    raw = float(m.group(1))
                    value_v = raw * ext.scale
                    points.append(VoltagePoint(
                        timestamp=event.timestamp,
                        value_v=value_v,
                        source=ext.name,
                        raw=event.message,
                    ))
                except (ValueError, IndexError):
                    continue
        return points


def extract_voltage_points(events: list[LogEvent], scanner: VoltageScanner) -> list[VoltagePoint]:
    points: list[VoltagePoint] = []
    for ev in events:
        points.extend(scanner.scan(ev))
    # 按时间排序
    points.sort(key=lambda p: p.timestamp)
    return points

