"""parser 单元测试。"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcu_trace.core.parser import (
    _LOG_LINE_RE,
    _build_mcu_trace_event,
    _parse_line,
    _parse_logcat_ts,
    _parse_compact_ts,
    _mcu_level_to_severity,
)
from mcu_trace.core.models import Severity


def test_log_line_re_match():
    line = "06-29 12:27:57.395742   337   341 I mcu_trace: I|SYS_STATIST 0629122756| last 1min cpu max usage:   59"
    m = _LOG_LINE_RE.match(line)
    assert m is not None
    gd = m.groupdict()
    assert gd["logcat_ts"] == "06-29 12:27:57.395742"
    assert gd["pid"] == "337"
    assert gd["tid"] == "341"
    assert gd["logcat_level"] == "I"
    assert gd["mcu_level"] == "I"
    assert gd["module"] == "SYS_STATIST"
    assert gd["compact_ts"] == "0629122756"
    assert "last 1min cpu" in gd["message"]


def test_log_line_re_psm_transition():
    line = "06-29 13:45:53.017942   335   339 I mcu_trace: I|PSM 0629134538| PreStandby->Standby, EVENT[14]."
    m = _LOG_LINE_RE.match(line)
    assert m is not None
    assert m.group("module") == "PSM"
    assert "PreStandby->Standby" in m.group("message")


def test_log_line_re_rst_type():
    line = "06-29 13:46:02.690844   335   339 I mcu_trace: W|MCU 0629134601| RST TYPE[18],REASON[24]."
    m = _LOG_LINE_RE.match(line)
    assert m is not None
    assert m.group("mcu_level") == "W"
    assert m.group("module") == "MCU"
    assert "RST TYPE[18]" in m.group("message")


def test_log_line_re_soc_mode():
    line = "06-29 13:45:53.107730   335   339 I mcu_trace: I|PSM 0629134538| soc mode changed,cur[5] last[1]."
    m = _LOG_LINE_RE.match(line)
    assert m is not None
    assert "soc mode changed" in m.group("message")


def test_parse_line_mcu_trace():
    line = "06-29 12:27:57.395742   337   341 I mcu_trace: I|SYS_STATIST 0629122756| last 1min cpu max usage:   59"
    ev = _parse_line(line, "logcat", 0)
    assert ev is not None
    assert ev.is_mcu_trace
    assert ev.module == "SYS_STATIST"
    assert ev.timestamp == datetime(2026, 6, 29, 12, 27, 57, 395742)


def test_parse_line_non_mcu():
    line = "06-29 12:28:10.557354  6604  6836 D Spword_C: leave GetSubSentence"
    ev = _parse_line(line, "logcat", 0)
    assert ev is None


def test_parse_logcat_ts():
    base = datetime(2026, 6, 29, 0, 0)
    ts = _parse_logcat_ts("06-29 12:27:57.395742", base)
    assert ts == datetime(2026, 6, 29, 12, 27, 57, 395742)


def test_parse_compact_ts():
    base = datetime(2026, 6, 29, 0, 0)
    ts = _parse_compact_ts("0629122757", base)
    assert ts == datetime(2026, 6, 29, 12, 27, 57)


def test_mcu_level_to_severity():
    assert _mcu_level_to_severity("E") == Severity.CRITICAL
    assert _mcu_level_to_severity("F") == Severity.CRITICAL
    assert _mcu_level_to_severity("W") == Severity.HIGH
    assert _mcu_level_to_severity("I") == Severity.INFO
    assert _mcu_level_to_severity("D") == Severity.INFO


def test_parse_line_base_date_override():
    """base_date 用于跨年 / 跨月拼接。"""
    line = "06-29 12:27:57.395742   337   341 I mcu_trace: I|TEST 0629122756| hi"
    ev = _parse_line(line, "logcat", 0, base_date=datetime(2025, 6, 29))
    assert ev.timestamp.year == 2025


if __name__ == "__main__":
    test_log_line_re_match()
    test_log_line_re_psm_transition()
    test_log_line_re_rst_type()
    test_log_line_re_soc_mode()
    test_parse_line_mcu_trace()
    test_parse_line_non_mcu()
    test_parse_logcat_ts()
    test_parse_compact_ts()
    test_mcu_level_to_severity()
    test_parse_line_base_date_override()
    print("ALL parser tests passed")
