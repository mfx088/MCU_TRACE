"""通用 FSM 状态机引擎。

支持两种跟踪模式：
1. PSM 模式：从消息里 match transition pattern，校验 from→to 合法性
2. SoCMode 模式：从消息里直接提取 cur/last 数字（无 transition 表，任意值都接受），但跨值越界（如 OFF→STR）标非法
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import FsmTransition, LogEvent, Severity

log = logging.getLogger(__name__)


@dataclass
class FsmConfig:
    """状态机配置。"""
    name: str
    states: list[str]
    initial: str
    transitions: list[dict]            # [{"from":..., "to":..., "pattern":..., "event_id":...}]
    transition_regex: Optional[str] = None     # PSM 模式：从 message match 出 (from, to, event_id)
    extract_pattern: Optional[str] = None     # SoCMode 模式：从 message match 出 (cur, last)

    @classmethod
    def from_json(cls, path: Path) -> "FsmConfig":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return cls(
            name=data["name"],
            states=data["states"],
            initial=data["initial"],
            transitions=data.get("transitions", []),
            transition_regex=data.get("transition_regex"),
            extract_pattern=data.get("extract_pattern"),
        )


class StateMachine:
    """状态机跟踪器。"""

    def __init__(self, config: FsmConfig, state_name_map: Optional[dict[str, str]] = None):
        self.config = config
        self.state_name_map = state_name_map or {}   # {"0": "OFF", "1": "STANDBY", ...}
        self.current: Optional[str] = config.initial
        # 把 transitions 编译成正则（按 from 预分组加速）
        self._transitions_by_from: dict[str, list[tuple[re.Pattern, dict]]] = {}
        for t in config.transitions:
            compiled = re.compile(t["pattern"])
            self._transitions_by_from.setdefault(t["from"], []).append((compiled, t))

        # SoCMode 模式专用：extract_pattern
        self._extract_re: Optional[re.Pattern] = None
        if config.extract_pattern:
            self._extract_re = re.compile(config.extract_pattern)

        # PSM 模式专用：transition_regex
        self._trans_regex: Optional[re.Pattern] = None
        if config.transition_regex:
            self._trans_regex = re.compile(config.transition_regex)

    def feed(self, event: LogEvent) -> Optional[FsmTransition]:
        """送入一个事件，返回触发的 transition（无则 None）。"""
        if not event.is_mcu_trace:
            return None

        if self._extract_re:
            return self._feed_extract(event)
        else:
            return self._feed_pattern(event)

    def _feed_pattern(self, event: LogEvent) -> Optional[FsmTransition]:
        """PSM 模式：module 匹配 + message match transition pattern。"""
        if event.module != self.config.name:
            return None

        # 在 transitions 表里找
        # 简化：先看 from==current 的，扫一遍；找不到再扫 all
        candidates = self._transitions_by_from.get(self.current or "", [])
        # 也加上 from==None/* 的兜底（如果 initial 不知道）
        all_candidates = []
        for from_state, lst in self._transitions_by_from.items():
            for c in lst:
                all_candidates.append((from_state, c))

        for c in candidates:
            t_regex, t = c
            if t_regex.search(event.message):
                return self._build_transition(event, self.current, t["to"], t, illegal=False)

        # 没找到合法转换 → 看是不是真的发生了状态变更（在消息里）
        if self._trans_regex:
            m = self._trans_regex.search(event.message)
            if m:
                groups = m.groups()
                from_s, to_s = groups[0], groups[1]
                event_id = groups[2] if len(groups) > 2 else None
                is_legal = any(
                    t["from"] == from_s and t["to"] == to_s
                    for t in self.config.transitions
                )
                trans = self._build_transition(
                    event, from_s, to_s,
                    {"event_id": f"EVENT[{event_id}]" if event_id else None},
                    illegal=not is_legal,
                    reason="" if is_legal else f"未定义的 transition: {from_s}->{to_s}",
                )
                self.current = to_s
                return trans
        return None

    def _feed_extract(self, event: LogEvent) -> Optional[FsmTransition]:
        """SoCMode 模式：从 message 抽 (cur, last) 数字。"""
        if not self._extract_re:
            return None
        m = self._extract_re.search(event.message)
        if not m:
            return None
        cur_raw, last_raw = m.groups()
        cur_name = self.state_name_map.get(cur_raw, f"MODE_{cur_raw}")
        last_name = self.state_name_map.get(last_raw, f"MODE_{last_raw}")
        # 合法性检查：任何 (last, cur) 都接受，但记录
        self.current = cur_name
        return self._build_transition(
            event, last_name, cur_name, {},
            illegal=False,
            reason=f"soc mode {last_raw}→{cur_raw}",
        )

    def _build_transition(
        self,
        event: LogEvent,
        from_state: str,
        to_state: str,
        t: dict,
        *,
        illegal: bool,
        reason: str = "",
    ) -> FsmTransition:
        return FsmTransition(
            fsm_name=self.config.name,
            timestamp=event.timestamp,
            from_state=from_state or "?",
            to_state=to_state,
            event_id=t.get("event_id"),
            raw=event.message,
            source_file=event.source_file,
            source_offset=event.source_offset,
            is_illegal=illegal,
            reason=reason,
        )


def track_psm(events: list[LogEvent], config: FsmConfig) -> list[FsmTransition]:
    """用 PSM 状态机跟踪 events 列表，返回所有 transition。"""
    sm = StateMachine(config)
    transitions: list[FsmTransition] = []
    for ev in events:
        t = sm.feed(ev)
        if t:
            transitions.append(t)
    return transitions


def track_soc_mode(
    events: list[LogEvent],
    config: FsmConfig,
    state_name_map: dict[str, str],
) -> list[FsmTransition]:
    """用 SoCMode 状态机跟踪 events 列表。"""
    sm = StateMachine(config, state_name_map=state_name_map)
    transitions: list[FsmTransition] = []
    for ev in events:
        t = sm.feed(ev)
        if t:
            transitions.append(t)
    return transitions


def detect_soc_mode_illegal(
    transitions: list[FsmTransition],
    legal_transitions: set[tuple[str, str]],
) -> list[FsmTransition]:
    """SoCMode 模式：把 (last, cur) 不在合法转换表里的标非法。

    合法转换示例：STANDBY↔STR↔OFF，TEMPO_ON→NORMAL→TEMPO_OFF
    """
    for t in transitions:
        key = (t.from_state, t.to_state)
        if key not in legal_transitions and t.from_state != "?" and t.to_state != "?":
            t.is_illegal = True
            t.reason = f"非法的 SoC 模式跳转: {t.from_state} → {t.to_state}"
    return transitions


# SoCMode 合法转换集（基于 PowerMode_Soc_t 语义推断）
LEGAL_SOC_TRANSITIONS: set[tuple[str, str]] = {
    # OFF ↔ STANDBY
    ("OFF", "STANDBY"), ("STANDBY", "OFF"),
    # STANDBY ↔ STR
    ("STANDBY", "STR"), ("STR", "STANDBY"),
    # STANDBY → TEMPO_ON → NORMAL
    ("STANDBY", "TEMPO_ON"), ("TEMPO_ON", "NORMAL"),
    # NORMAL → TEMPO_OFF → STANDBY
    ("NORMAL", "TEMPO_OFF"), ("TEMPO_OFF", "STANDBY"),
    # STANDBY ↔ NORMAL 快速路径（不经过 TEMPO_ON，样本里多次出现）
    ("STANDBY", "NORMAL"), ("NORMAL", "STANDBY"),
    # OFF ↔ STR（深度断电）
    ("STR", "OFF"),
    ("OFF", "STR"),
    # 自循环
    ("NORMAL", "NORMAL"), ("STANDBY", "STANDBY"), ("STR", "STR"), ("OFF", "OFF"),
    ("TEMPO_ON", "TEMPO_ON"), ("TEMPO_OFF", "TEMPO_OFF"),
}

