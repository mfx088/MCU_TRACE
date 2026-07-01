"""keyword 单元测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcu_trace.core.keyword import KeywordScanner, scan_events, filter_by_severity
from mcu_trace.core.parser import _parse_line
from mcu_trace.core.models import Severity


CONFIG = Path(__file__).parent.parent / "src" / "mcu_trace" / "assets" / "config" / "builtin_rules.json"


def test_keyword_hit_fault():
    """HardF 关键字命中 → critical 严重度。"""
    scanner = KeywordScanner.from_json(CONFIG)
    line = "06-29 13:46:02.876791   335   339 I mcu_trace: W|HardF 0629134601| Trace_BackupMcuRegContext_VaildationCheck failed."
    ev = _parse_line(line, "logcat", 0)
    hits = scanner.scan(ev)
    assert len(hits) >= 1
    fault_hit = next((h for h in hits if h.category == "fault"), None)
    assert fault_hit is not None
    assert fault_hit.severity == Severity.CRITICAL


def test_keyword_no_match():
    """不匹配的日志无命中。"""
    scanner = KeywordScanner.from_json(CONFIG)
    line = "06-29 13:45:54.603518   335   339 I mcu_trace: I|PSM 0629134538| cur Volt is 13960."
    ev = _parse_line(line, "logcat", 0)
    hits = scanner.scan(ev)
    assert hits == []


def test_filter_by_severity():
    """按严重度过滤：>=HIGH 保留 info/medium 的过滤掉。"""
    scanner = KeywordScanner.from_json(CONFIG)
    line1 = "06-29 13:46:02.876791   335   339 I mcu_trace: W|HardF 0629134601| Trace_BackupMcuRegContext_VaildationCheck failed."
    line2 = "06-29 13:45:54.603518   335   339 I mcu_trace: I|MSAVE 0629134538| retry:1"
    events = [_parse_line(line1, "logcat", 0), _parse_line(line2, "logcat", 1)]
    hits = scan_events(events, scanner)
    high = filter_by_severity(hits, Severity.HIGH)
    assert all(h.severity >= Severity.HIGH for h in high)


if __name__ == "__main__":
    test_keyword_hit_fault()
    test_keyword_no_match()
    test_filter_by_severity()
    print("ALL keyword tests passed")
