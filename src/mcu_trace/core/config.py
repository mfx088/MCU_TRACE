"""用户级配置管理：读写 %APPDATA%\\MCU_TRACE\\config.json

GUI 启动时加载；用户在设置面板改路径后保存。
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

CONFIG_DIR_NAME = "MCU_TRACE"
CONFIG_FILENAME = "config.json"


def get_config_dir() -> Path:
    """获取用户配置目录：%APPDATA%\\MCU_TRACE\\"""
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / CONFIG_DIR_NAME
    # 兜底
    return Path.home() / ".mcu_trace"


def get_config_path() -> Path:
    return get_config_dir() / CONFIG_FILENAME


def get_user_rules_path() -> Path:
    """用户规则文件路径：%APPDATA%\\MCU_TRACE\\user_rules.json（v0.2+）。"""
    return get_config_dir() / "user_rules.json"


@dataclass
class UserConfig:
    """用户级配置。"""
    decrypt_tool_path: str = r"E:\Data\桌面工具\decrypt-update\decrypt-update\hsaedecrypt.exe"
    default_logd_dir: str = ""
    theme: str = "light"          # light / dark
    work_dir: str = ""            # 默认工作目录（保存解密的 logcat）
    # 扩展配置（GUI 自定义关键字等）
    custom_voltage_patterns: list[dict] = field(default_factory=list)
    custom_keyword_patterns: list[dict] = field(default_factory=list)
    # v0.2+：用户自定义规则（number_mappings / keyword_rules / voltage_extractors）
    # 结构与 builtin_rules.json 兼容；规则合并见 core/rules_loader.py
    user_rules: dict = field(default_factory=dict)
    # 元数据
    version: str = "0.2.0"
    last_updated: str = ""

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "UserConfig":
        path = path or get_config_path()
        if not path.is_file():
            log.info("用户配置不存在，使用默认: %s", path)
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            cfg = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            log.info("加载用户配置: %s", path)
            return cfg
        except (json.JSONDecodeError, TypeError) as e:
            log.warning("用户配置损坏，用默认: %s (%s)", path, e)
            return cls()

    def save(self, path: Optional[Path] = None) -> Path:
        path = path or get_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        import datetime
        self.last_updated = datetime.datetime.now().isoformat()
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        log.info("用户配置已保存: %s", path)
        return path

    def decrypt_exe_exists(self) -> bool:
        return Path(self.decrypt_tool_path).is_file()
