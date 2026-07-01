"""关键字 / 错误码检索。

基于 builtin_rules.json 里的 keyword_rules 配置。
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from .models import KeywordHit, LogEvent, Severity

log = logging.getLogger(__name__)

SEVERITY_MAP = {
    "info": Severity.INFO,
    "low": Severity.LOW,
    "medium": Severity.MEDIUM,
    "high": Severity.HIGH,
    "critical": Severity.CRITICAL,
}


class KeywordScanner:
    """关键字扫描器：编译所有 pattern，对每个 event 扫一遍。"""

    def __init__(self, rules: list[dict]):
        # 编译每条规则
        self.compiled: list[tuple[re.Pattern, dict]] = []
        for r in rules:
            try:
                pat = re.compile(r["pattern"], re.IGNORECASE)
                self.compiled.append((pat, r))
            except re.error as e:
                log.warning("关键字正则编译失败: %s → %s", r["pattern"], e)

    @classmethod
    def from_json(cls, path: Path) -> "KeywordScanner":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return cls(data.get("keyword_rules", []))

    @classmethod
    def from_rules(cls, rules: dict) -> "KeywordScanner":
        """v0.2+: 从已合并的 rules dict（不是 Path）构造。"""
        return cls(rules.get("keyword_rules", []))

    def scan(self, event: LogEvent) -> list[KeywordHit]:
        if not event.is_mcu_trace:
            return []
        hits: list[KeywordHit] = []
        msg = event.message
        for pat, rule in self.compiled:
            m = pat.search(msg)
            if m:
                hits.append(KeywordHit(
                    event=event,
                    pattern=rule["pattern"],
                    category=rule.get("category", "unknown"),
                    severity=SEVERITY_MAP.get(rule.get("severity", "info"), Severity.INFO),
                    matched_text=m.group(0),
                ))
        return hits


def scan_events(events: list[LogEvent], scanner: KeywordScanner) -> list[KeywordHit]:
    """对所有 event 跑扫描，返回所有命中。"""
    hits: list[KeywordHit] = []
    for ev in events:
        hits.extend(scanner.scan(ev))
    return hits


def filter_by_severity(hits: list[KeywordHit], min_severity: Severity) -> list[KeywordHit]:
    """按严重度过滤（>=）。"""
    return [h for h in hits if h.severity >= min_severity]


def filter_by_category(hits: list[KeywordHit], categories: list[str]) -> list[KeywordHit]:
    """按类别过滤。"""
    return [h for h in hits if h.category in categories]

