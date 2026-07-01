"""reset 单元测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcu_trace.core.reset import ResetScanner
from mcu_trace.core.parser import _parse_line
from mcu_trace.core.models import Severity


CONFIG = Path(__file__).parent.parent / "src" / "mcu_trace" / "assets" / "config" / "builtin_rules.json"


def test_rst_extraction_known():
    """RST TYPE[18] → RESETREASON_MID_WAKEUP, REASON[24] → MCU_WAKEUP_REASON"""
    scanner = ResetScanner.from_json(CONFIG)
    line = "06-29 13:46:02.690844   335   339 I mcu_trace: W|MCU 0629134601| RST TYPE[18],REASON[24]."
    ev = _parse_line(line, "logcat", 0)
    r = scanner.scan(ev)
    assert r is not None
    assert r.rst_type_raw == 18
    assert r.rst_type_name == "RESETREASON_MID_WAKEUP"
    assert r.reason_raw == 24
    assert r.reason_name == "MCU_WAKEUP_REASON"


def test_rst_extraction_unknown_number():
    """不在映射表里的数字用占位字符串。"""
    scanner = ResetScanner.from_json(CONFIG)
    line = "06-29 13:46:00.000000   335   339 I mcu_trace: W|MCU 0629134600| RST TYPE[99],REASON[88]."
    ev = _parse_line(line, "logcat", 0)
    r = scanner.scan(ev)
    assert r is not None
    assert r.rst_type_name == "TYPE_99"
    assert r.reason_name == "REASON_88"


def test_rst_extraction_no_match():
    """无 RST TYPE 的行不产生事件。"""
    scanner = ResetScanner.from_json(CONFIG)
    line = "06-29 13:45:54.603518   335   339 I mcu_trace: I|PSM 0629134538| cur Volt is 13960."
    ev = _parse_line(line, "logcat", 0)
    assert scanner.scan(ev) is None


def test_rst_severity_critical():
    """REASON 24 (WAKEUP_REASON) 是 info 严重度。REASON 5 (PLL_LOL) 应是 critical。"""
    scanner = ResetScanner.from_json(CONFIG)
    line = "06-29 13:46:00.000000   335   339 I mcu_trace: W|MCU 0629134600| RST TYPE[0],REASON[5]."
    ev = _parse_line(line, "logcat", 0)
    r = scanner.scan(ev)
    assert r is not None
    assert r.reason_name == "MCU_PLL_LOL_RESET"
    assert r.severity == Severity.CRITICAL


if __name__ == "__main__":
    test_rst_extraction_known()
    test_rst_extraction_unknown_number()
    test_rst_extraction_no_match()
    test_rst_severity_critical()
    print("ALL reset tests passed")
