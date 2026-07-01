"""规则加载与合并层。

v0.2 新增：让用户能在 GUI 里编辑 3 类规则（number_mappings / keyword_rules / voltage_extractors），
这些规则合并到 builtin_rules.json 之上，按以下策略：

- number_mappings: **整体覆盖**（按子命名空间）
  - 用户对 `soc_mode` 子 dict 整体替换 builtin；可删可增
  - `rst_type` / `rst_reason` 同理
- keyword_rules: **追加 + pattern 冲突胜出**
  - builtin + user 拼接，user 项排在后
  - 编译时**先到先得**——user 可覆盖 builtin 同 pattern
- voltage_extractors: **追加 + name 冲突胜出**
  - 同 keyword_rules，冲突判定按 `name` 字段

用户规则存于 `%APPDATA%\\MCU_TRACE\\user_rules.json`（独立于 config.json）。
"""
from __future__ import annotations

import copy
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional, Union

log = logging.getLogger(__name__)


# 数字映射的合法子命名空间（用于校验）
NUMBER_MAPPING_SUBNAMESPACES = ("soc_mode", "rst_type", "rst_reason")

# 关键字规则的严重度白名单
KEYWORD_SEVERITY_WHITELIST = ("info", "low", "medium", "high", "critical")

# 电压提取器的单位白名单
VOLTAGE_UNIT_WHITELIST = ("mV", "V")


def get_builtin_rules_path() -> Path:
    """内置规则 JSON 路径。"""
    return Path(__file__).parent.parent / "assets" / "config" / "builtin_rules.json"


def get_user_rules_path() -> Path:
    """用户规则 JSON 路径：%APPDATA%\\MCU_TRACE\\user_rules.json。"""
    from .config import get_config_dir
    return get_config_dir() / "user_rules.json"


def load_builtin() -> dict:
    """加载内置规则（必存在）。"""
    path = get_builtin_rules_path()
    if not path.is_file():
        raise FileNotFoundError(f"内置规则文件不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_user(path: Optional[Path] = None) -> dict:
    """加载用户规则。文件不存在或损坏时返回空 dict（不抛错）。"""
    p = path or get_user_rules_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            log.warning("user_rules.json 格式错误（非 dict），已忽略: %s", p)
            return {}
        return data
    except (json.JSONDecodeError, OSError) as e:
        log.warning("user_rules.json 加载失败，已忽略: %s (%s)", p, e)
        return {}


def save_user(rules: dict, path: Optional[Path] = None) -> Path:
    """保存用户规则到磁盘。先校验全部规则，校验失败则抛 ValueError。"""
    p = path or get_user_rules_path()
    validate_user_rules(rules)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(rules, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("用户规则已保存: %s", p)
    return p


def merge(builtin: dict, user: dict) -> dict:
    """合并 builtin + user → 新的合并规则 dict（不修改入参）。"""
    merged = copy.deepcopy(builtin)

    # 1. number_mappings：按键级覆盖（保留 builtin 中 user 未列出的 key）
    # 即 user 给出 {"soc_mode": {"0": "我的OFF"}} 时，仅覆盖 "0" 这一个 key；
    # builtin 中 "1"/"2"/"3" 等 key 保持不变。这样用户改 1 个值不会丢其他。
    user_nm = user.get("number_mappings", {})
    if isinstance(user_nm, dict):
        merged_nm = merged.setdefault("number_mappings", {})
        for sub in NUMBER_MAPPING_SUBNAMESPACES:
            user_sub = user_nm.get(sub)
            if isinstance(user_sub, dict) and sub in merged_nm and isinstance(merged_nm[sub], dict):
                # 在 builtin 的 dict 基础上浅覆盖 user 给出的 key
                merged_nm[sub] = {**merged_nm[sub], **user_sub}

    # 2. keyword_rules：追加（user 在后，编译时 user 胜出）
    user_kw = user.get("keyword_rules", [])
    if isinstance(user_kw, list):
        merged_kw = list(merged.get("keyword_rules", []))
        for r in user_kw:
            if isinstance(r, dict):
                merged_kw.append(r)
        merged["keyword_rules"] = merged_kw

    # 3. voltage_extractors：追加（user 在后，编译时 user 胜出）
    user_v = user.get("voltage_extractors", [])
    if isinstance(user_v, list):
        merged_v = list(merged.get("voltage_extractors", []))
        for r in user_v:
            if isinstance(r, dict):
                merged_v.append(r)
        merged["voltage_extractors"] = merged_v

    return merged


def load_merged_rules() -> dict:
    """加载 builtin + user，合并后返回。等价于 merge(load_builtin(), load_user())。"""
    return merge(load_builtin(), load_user())


# ============================================================
# 校验
# ============================================================

class RuleValidationError(ValueError):
    """规则校验失败。message 含失败位置和原因。"""
    pass


def validate_user_rules(rules: dict) -> None:
    """校验 user_rules 整体结构。失败抛 RuleValidationError。"""
    if not isinstance(rules, dict):
        raise RuleValidationError("规则必须为 dict")

    # number_mappings
    nm = rules.get("number_mappings", {})
    if not isinstance(nm, dict):
        raise RuleValidationError("number_mappings 必须为 dict")
    for sub, mapping in nm.items():
        if sub not in NUMBER_MAPPING_SUBNAMESPACES:
            raise RuleValidationError(
                f"number_mappings.{sub} 不在白名单 {NUMBER_MAPPING_SUBNAMESPACES}"
            )
        if not isinstance(mapping, dict):
            raise RuleValidationError(f"number_mappings.{sub} 必须为 dict")
        for k, v in mapping.items():
            if not isinstance(k, str) or not k.isdigit():
                raise RuleValidationError(
                    f"number_mappings.{sub} 键必须为数字字符串，实际: {k!r}"
                )
            if not isinstance(v, str) or not v.strip():
                raise RuleValidationError(
                    f"number_mappings.{sub}.{k} 必须为非空字符串"
                )

    # keyword_rules
    kw_list = rules.get("keyword_rules", [])
    if not isinstance(kw_list, list):
        raise RuleValidationError("keyword_rules 必须为 list")
    for i, r in enumerate(kw_list):
        validate_keyword_rule(r, f"keyword_rules[{i}]")

    # voltage_extractors
    v_list = rules.get("voltage_extractors", [])
    if not isinstance(v_list, list):
        raise RuleValidationError("voltage_extractors 必须为 list")
    for i, r in enumerate(v_list):
        validate_voltage_extractor(r, f"voltage_extractors[{i}]")


def validate_keyword_rule(rule: dict, prefix: str = "rule") -> None:
    """校验单条关键字规则。"""
    if not isinstance(rule, dict):
        raise RuleValidationError(f"{prefix} 必须为 dict")
    pattern = rule.get("pattern")
    if not pattern or not isinstance(pattern, str):
        raise RuleValidationError(f"{prefix}.pattern 必须为非空字符串")
    try:
        re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise RuleValidationError(f"{prefix}.pattern 正则无效: {e}") from e
    cat = rule.get("category", "unknown")
    if not isinstance(cat, str) or not cat.strip():
        raise RuleValidationError(f"{prefix}.category 必须为非空字符串")
    sev = rule.get("severity", "info")
    if sev not in KEYWORD_SEVERITY_WHITELIST:
        raise RuleValidationError(
            f"{prefix}.severity 必须在 {KEYWORD_SEVERITY_WHITELIST}，实际: {sev!r}"
        )


def validate_voltage_extractor(rule: dict, prefix: str = "extractor") -> None:
    """校验单条电压提取器。"""
    if not isinstance(rule, dict):
        raise RuleValidationError(f"{prefix} 必须为 dict")
    name = rule.get("name")
    if not name or not isinstance(name, str) or not name.strip():
        raise RuleValidationError(f"{prefix}.name 必须为非空字符串")
    pattern = rule.get("pattern")
    if not pattern or not isinstance(pattern, str):
        raise RuleValidationError(f"{prefix}.pattern 必须为非空字符串")
    try:
        re.compile(pattern)
    except re.error as e:
        raise RuleValidationError(f"{prefix}.pattern 正则无效: {e}") from e
    unit = rule.get("unit", "V")
    if unit not in VOLTAGE_UNIT_WHITELIST:
        raise RuleValidationError(
            f"{prefix}.unit 必须在 {VOLTAGE_UNIT_WHITELIST}，实际: {unit!r}"
        )
    scale = rule.get("scale", 1.0)
    if not isinstance(scale, (int, float)) or scale <= 0:
        raise RuleValidationError(
            f"{prefix}.scale 必须为正数，实际: {scale!r}"
        )
    enabled = rule.get("enabled", True)
    if not isinstance(enabled, bool):
        raise RuleValidationError(f"{prefix}.enabled 必须为 bool")


def validate_pattern(category: str, pattern: str) -> dict:
    """快速校验单个正则（供 GUI 实时校验用）。返回 {"ok": bool, "error": str|None}。"""
    try:
        if category == "keyword":
            re.compile(pattern, re.IGNORECASE)
        else:
            re.compile(pattern)
        return {"ok": True, "error": None}
    except re.error as e:
        return {"ok": False, "error": str(e)}
