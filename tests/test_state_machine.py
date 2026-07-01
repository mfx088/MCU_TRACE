"""state_machine 单元测试。"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcu_trace.core.state_machine import (
    FsmConfig,
    StateMachine,
    track_psm,
    track_soc_mode,
    detect_soc_mode_illegal,
    LEGAL_SOC_TRANSITIONS,
)
from mcu_trace.core.models import LogEvent, Severity
from mcu_trace.core.parser import _parse_line


CONFIG_DIR = Path(__file__).parent.parent / "src" / "mcu_trace" / "assets" / "config"


def _make_event(line: str, offset: int = 0) -> LogEvent:
    return _parse_line(line, "logcat", offset)


def test_psm_legal_transitions():
    """PSM 合法转换：PreStandby -> Standby -> PrepareSleep_Step1 -> ... -> Normal"""
    config = FsmConfig.from_json(CONFIG_DIR / "psm_fsm.json")
    events = [
        _make_event("06-29 13:45:53.017942   335   339 I mcu_trace: I|PSM 0629134538| PreStandby->Standby, EVENT[14]."),
        _make_event("06-29 13:45:53.409477   335   339 I mcu_trace: I|PSM 0629134538| Standby->PrepareSleep_Step1, EVENT[14]."),
        _make_event("06-29 13:45:54.504975   335   339 I mcu_trace: I|PSM 0629134538| PreSleep_1->PreSleep_2."),
        _make_event("06-29 13:45:55.000263   335   339 I mcu_trace: I|PSM 0629134538| PreSleep_2->WatiEvnShutDown, EVENT[12]."),
    ]
    transitions = track_psm(events, config)
    assert len(transitions) == 4
    for t in transitions:
        assert not t.is_illegal, f"Should be legal: {t.from_state}->{t.to_state}"


def test_psm_illegal_transition():
    """PSM 非法转换：Standby -> Normal（不在合法表里）"""
    config = FsmConfig.from_json(CONFIG_DIR / "psm_fsm.json")
    events = [
        _make_event("06-29 13:45:53.017942   335   339 I mcu_trace: I|PSM 0629134538| PreStandby->Standby, EVENT[14]."),
        # 非法：直接从 Standby -> Normal（应通过 PrepareSleep）
        _make_event("06-29 13:46:00.000000   335   339 I mcu_trace: I|PSM 0629134600| Standby->Normal, EVENT[5]."),
    ]
    transitions = track_psm(events, config)
    assert len(transitions) == 2
    assert transitions[1].is_illegal
    assert "Standby->Normal" in transitions[1].reason


def test_soc_mode_legal():
    """SoC 模式：OFF->STR 在 LEGAL_SOC_TRANSITIONS 里"""
    soc_map = {"0": "OFF", "1": "STANDBY", "3": "NORMAL", "5": "STR"}
    config = FsmConfig.from_json(CONFIG_DIR / "soc_fsm.json")
    events = [
        _make_event("06-29 13:46:00.000000   335   339 I mcu_trace: I|PSM 0629134600| soc mode changed,cur[5] last[0]."),
    ]
    transitions = track_soc_mode(events, config, soc_map)
    assert len(transitions) == 1
    assert transitions[0].from_state == "OFF"
    assert transitions[0].to_state == "STR"
    assert not transitions[0].is_illegal  # (OFF, STR) 在 LEGAL_SOC_TRANSITIONS


def test_soc_mode_illegal():
    """SoC 模式：OFF -> MAX 非法（不在合法表里）"""
    soc_map = {"0": "OFF", "6": "MAX"}
    config = FsmConfig.from_json(CONFIG_DIR / "soc_fsm.json")
    events = [
        _make_event("06-29 13:46:00.000000   335   339 I mcu_trace: I|PSM 0629134600| soc mode changed,cur[6] last[0]."),
    ]
    transitions = track_soc_mode(events, config, soc_map)
    detect_soc_mode_illegal(transitions, LEGAL_SOC_TRANSITIONS)
    assert len(transitions) == 1
    assert transitions[0].is_illegal


def test_legal_soc_transitions_includes_known_pairs():
    """验证 LEGAL_SOC_TRANSITIONS 包含一些已知合法对。"""
    assert ("OFF", "STR") in LEGAL_SOC_TRANSITIONS
    assert ("STANDBY", "STR") in LEGAL_SOC_TRANSITIONS
    assert ("STR", "STANDBY") in LEGAL_SOC_TRANSITIONS
    assert ("STANDBY", "TEMPO_ON") in LEGAL_SOC_TRANSITIONS  # STANDBY->NORMAL 应经 TEMPO_ON，跳过是非法


if __name__ == "__main__":
    test_psm_legal_transitions()
    test_psm_illegal_transition()
    test_soc_mode_legal()
    test_soc_mode_illegal()
    test_legal_soc_transitions_includes_known_pairs()
    print("ALL state_machine tests passed")
