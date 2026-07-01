"""voltage 单元测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcu_trace.core.voltage import VoltageScanner, extract_voltage_points
from mcu_trace.core.parser import _parse_line
from mcu_trace.core.models import VoltagePoint


CONFIG = Path(__file__).parent.parent / "src" / "mcu_trace" / "assets" / "config" / "builtin_rules.json"


def test_voltage_extraction_psm():
    """PSM 上报的电压（mV）→ V 换算。"""
    scanner = VoltageScanner.from_json(CONFIG)
    line = "06-29 13:45:54.603518   335   339 I mcu_trace: I|PSM 0629134538| cur Volt is 13960."
    ev = _parse_line(line, "logcat", 0)
    assert ev is not None
    points = scanner.scan(ev)
    assert len(points) == 1
    assert abs(points[0].value_v - 13.96) < 0.01
    assert points[0].source == "PSM Volt"


def test_voltage_extraction_no_match():
    """不匹配的日志不产生电压点。"""
    scanner = VoltageScanner.from_json(CONFIG)
    line = "06-29 13:46:00.000000   335   339 I mcu_trace: I|MIPC 0629134600| random message."
    ev = _parse_line(line, "logcat", 0)
    points = scanner.scan(ev)
    assert points == []


def test_voltage_extraction_custom():
    """自定义电压关键字：VoltDet VBAT=12.34V"""
    import json
    import tempfile

    cfg = {
        "voltage_extractors": [
            {"name": "VoltDet VBAT", "pattern": r"VoltDet.*VBAT=([\d.]+)", "unit": "V", "scale": 1.0, "enabled": True},
        ]
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(cfg, f)
        cfg_path = Path(f.name)
    try:
        scanner = VoltageScanner.from_json(cfg_path)
        line = "06-29 12:00:00.000000   337   341 I mcu_trace: I|PwrSuplyM 0612000000| VoltDet VBAT=12.34V"
        ev = _parse_line(line, "logcat", 0)
        points = scanner.scan(ev)
        assert len(points) == 1
        assert abs(points[0].value_v - 12.34) < 0.001
    finally:
        cfg_path.unlink()


def test_voltage_extraction_disabled():
    """禁用的 extractor 不产生点。"""
    import json
    import tempfile

    cfg = {
        "voltage_extractors": [
            {"name": "Disabled", "pattern": r"cur Volt is (\d+)", "unit": "mV", "scale": 0.001, "enabled": False},
        ]
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(cfg, f)
        cfg_path = Path(f.name)
    try:
        scanner = VoltageScanner.from_json(cfg_path)
        line = "06-29 13:45:54.603518   335   339 I mcu_trace: I|PSM 0629134538| cur Volt is 13960."
        ev = _parse_line(line, "logcat", 0)
        points = scanner.scan(ev)
        assert points == []
    finally:
        cfg_path.unlink()


if __name__ == "__main__":
    test_voltage_extraction_psm()
    test_voltage_extraction_no_match()
    test_voltage_extraction_custom()
    test_voltage_extraction_disabled()
    print("ALL voltage tests passed")
