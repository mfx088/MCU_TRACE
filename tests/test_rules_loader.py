"""v0.2-C: rules_loader 单元测试。"""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

import pytest

from mcu_trace.core import rules_loader as rl
from mcu_trace.core.rules_loader import (
    NUMBER_MAPPING_SUBNAMESPACES,
    RuleValidationError,
    load_builtin,
    load_user,
    merge,
    save_user,
    validate_keyword_rule,
    validate_pattern,
    validate_user_rules,
    validate_voltage_extractor,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def builtin():
    """Load actual builtin rules from the project."""
    return load_builtin()


@pytest.fixture
def tmp_user_path(tmp_path):
    return tmp_path / "user_rules.json"


# ============================================================
# Test 1: builtin 加载
# ============================================================

def test_load_builtin_has_expected_keys(builtin):
    assert "version" in builtin
    assert "keyword_rules" in builtin
    assert "voltage_extractors" in builtin
    assert "number_mappings" in builtin
    assert "soc_mode" in builtin["number_mappings"]
    assert "rst_type" in builtin["number_mappings"]
    assert "rst_reason" in builtin["number_mappings"]


# ============================================================
# Test 2: user 加载（缺失 / 损坏 / 正常）
# ============================================================

def test_load_user_missing_returns_empty(tmp_user_path):
    assert load_user(tmp_user_path) == {}


def test_load_user_corrupt_returns_empty(tmp_user_path):
    tmp_user_path.write_text("{bad json", encoding="utf-8")
    assert load_user(tmp_user_path) == {}


def test_load_user_non_dict_returns_empty(tmp_user_path):
    tmp_user_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert load_user(tmp_user_path) == {}


def test_load_user_valid(builtin, tmp_user_path):
    tmp_user_path.write_text(
        json.dumps({"version": "0.2.0", "number_mappings": {"soc_mode": {"0": "X"}}}),
        encoding="utf-8",
    )
    data = load_user(tmp_user_path)
    assert data["number_mappings"]["soc_mode"]["0"] == "X"


# ============================================================
# Test 3: number_mappings 整体覆盖
# ============================================================

def test_merge_number_mappings_override(builtin):
    """v0.2 改用 key-level override：user 给出的 key 覆盖 builtin，未给出的保留 builtin。"""
    user = {"number_mappings": {"soc_mode": {"0": "我的OFF", "99": "新增态"}}}
    merged = merge(builtin, user)
    # user 给出的 key 被覆盖
    assert merged["number_mappings"]["soc_mode"]["0"] == "我的OFF"
    assert merged["number_mappings"]["soc_mode"]["99"] == "新增态"
    # builtin 原有的 1, 2, 3 仍然在
    assert merged["number_mappings"]["soc_mode"]["1"] == builtin["number_mappings"]["soc_mode"]["1"]
    # 但 rst_type / rst_reason 完全不变
    assert merged["number_mappings"]["rst_type"] == builtin["number_mappings"]["rst_type"]
    assert merged["number_mappings"]["rst_reason"] == builtin["number_mappings"]["rst_reason"]


def test_merge_number_mappings_partial_subns(builtin):
    """只改 soc_mode，rst_type / rst_reason 不动。"""
    user = {"number_mappings": {"soc_mode": {"0": "OFF-OVERRIDE"}}}
    merged = merge(builtin, user)
    assert merged["number_mappings"]["soc_mode"]["0"] == "OFF-OVERRIDE"
    assert merged["number_mappings"]["rst_type"] == builtin["number_mappings"]["rst_type"]


def test_merge_does_not_mutate_builtin(builtin):
    original_soc0 = builtin["number_mappings"]["soc_mode"]["0"]
    user = {"number_mappings": {"soc_mode": {"0": "MUTATED"}}}
    merge(builtin, user)
    assert builtin["number_mappings"]["soc_mode"]["0"] == original_soc0


# ============================================================
# Test 4: keyword_rules 追加 + 冲突胜出
# ============================================================

def test_merge_keyword_rules_append(builtin):
    original_count = len(builtin["keyword_rules"])
    user = {"keyword_rules": [{"pattern": r"MyCustomErr\d+", "category": "custom", "severity": "high"}]}
    merged = merge(builtin, user)
    assert len(merged["keyword_rules"]) == original_count + 1
    assert merged["keyword_rules"][-1]["pattern"] == r"MyCustomErr\d+"


def test_merge_keyword_rules_user_wins_on_compile():
    """冲突时后编译的 user pattern 优先（因为它在 list 后）。"""
    builtin_rules = {"keyword_rules": [{"pattern": r"shared", "category": "a", "severity": "low"}]}
    user_rules = {"keyword_rules": [{"pattern": r"shared", "category": "b", "severity": "critical"}]}
    merged = merge(builtin_rules, user_rules)
    assert len(merged["keyword_rules"]) == 2
    # 实际胜出由 KeywordScanner 决定（先到先得）；这里只验证合并顺序
    assert merged["keyword_rules"][0]["category"] == "a"
    assert merged["keyword_rules"][1]["category"] == "b"


# ============================================================
# Test 5: voltage_extractors 追加
# ============================================================

def test_merge_voltage_extractors_append(builtin):
    original_count = len(builtin["voltage_extractors"])
    user = {"voltage_extractors": [
        {"name": "我的VBAT", "pattern": r"VBAT=([\d.]+)", "unit": "V", "scale": 1.0, "enabled": True}
    ]}
    merged = merge(builtin, user)
    assert len(merged["voltage_extractors"]) == original_count + 1
    assert merged["voltage_extractors"][-1]["name"] == "我的VBAT"


# ============================================================
# Test 6: 校验失败
# ============================================================

def test_validate_keyword_rule_bad_regex():
    with pytest.raises(RuleValidationError, match="正则无效"):
        validate_keyword_rule({"pattern": "[unclosed", "category": "x", "severity": "high"})


def test_validate_keyword_rule_bad_severity():
    with pytest.raises(RuleValidationError, match="severity"):
        validate_keyword_rule({"pattern": "ok", "category": "x", "severity": "extreme"})


def test_validate_voltage_extractor_bad_unit():
    with pytest.raises(RuleValidationError, match="unit"):
        validate_voltage_extractor({
            "name": "x", "pattern": r"\d+", "unit": "kV", "scale": 1.0
        })


def test_validate_voltage_extractor_negative_scale():
    with pytest.raises(RuleValidationError, match="scale"):
        validate_voltage_extractor({
            "name": "x", "pattern": r"\d+", "unit": "V", "scale": -1.0
        })


def test_validate_user_rules_top_level():
    with pytest.raises(RuleValidationError):
        validate_user_rules("not a dict")


def test_validate_user_rules_bad_subns():
    with pytest.raises(RuleValidationError, match="白名单"):
        validate_user_rules({"number_mappings": {"custom_namespace": {"0": "x"}}})


def test_validate_user_rules_non_digit_key():
    with pytest.raises(RuleValidationError, match="数字字符串"):
        validate_user_rules({"number_mappings": {"soc_mode": {"abc": "x"}}})


def test_validate_user_rules_ok_minimal():
    # Should not raise
    validate_user_rules({})


# ============================================================
# Test 7: validate_pattern 快速接口
# ============================================================

def test_validate_pattern_ok():
    assert validate_pattern("keyword", r"foo\d+")["ok"] is True
    assert validate_pattern("voltage", r"\d+")["ok"] is True


def test_validate_pattern_bad():
    r = validate_pattern("keyword", "[unclosed")
    assert r["ok"] is False
    assert r["error"]


# ============================================================
# Test 8: save_user + load_user roundtrip
# ============================================================

def test_save_and_reload_roundtrip(tmp_user_path):
    user = {
        "version": "0.2.0",
        "number_mappings": {"soc_mode": {"0": "X"}},
        "keyword_rules": [{"pattern": r"x\d", "category": "c", "severity": "low"}],
        "voltage_extractors": [{"name": "v", "pattern": r"\d+", "unit": "V", "scale": 1.0, "enabled": True}],
    }
    save_user(user, tmp_user_path)
    reloaded = load_user(tmp_user_path)
    assert reloaded == user


def test_save_rejects_bad_rule(tmp_user_path):
    bad = {"keyword_rules": [{"pattern": "[bad", "category": "x", "severity": "low"}]}
    with pytest.raises(RuleValidationError):
        save_user(bad, tmp_user_path)
    # 文件不应被创建
    assert not tmp_user_path.exists()
