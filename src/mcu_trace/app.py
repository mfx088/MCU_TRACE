"""pywebview 应用入口（Day 2 完善版）。

GUI 启动入口：python -m mcu_trace
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

def _get_web_dir() -> Path:
    """获取 web 目录（兼容开发模式 + PyInstaller 打包后）"""
    import sys
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后：data 放在 _MEIPASS/mcu_trace/web
        return Path(sys._MEIPASS) / "mcu_trace" / "web"
    # 开发模式
    return Path(__file__).parent / "web"


def run_gui() -> None:
    """启动 pywebview 窗口。"""
    import webview
    import sys

    web_dir = _get_web_dir()
    index_html = web_dir / "index.html"
    if not index_html.is_file():
        raise FileNotFoundError(f"找不到前端页面: {index_html}")

    # 加载用户配置
    from .core.config import UserConfig
    user_cfg = UserConfig.load()

    api = McuTraceApi(user_cfg)

    window = webview.create_window(
        title="MCU TRACE 工具 v0.2.2",
        url=str(index_html),
        width=1400,
        height=900,
        resizable=True,
        text_select=True,
        js_api=api,
    )

    webview.start(debug=False)


class McuTraceApi:
    """暴露给前端的 Python API。"""

    def __init__(self, user_cfg):
        self.user_cfg = user_cfg

    # ============================================================
    # 配置相关
    # ============================================================

    def get_config(self) -> dict:
        """GUI 调用：获取当前配置。"""
        from dataclasses import asdict
        return asdict(self.user_cfg)

    def save_config(self, config: dict) -> dict:
        """GUI 调用：保存配置到 %APPDATA%\\MCU_TRACE\\config.json。"""
        try:
            from dataclasses import fields
            valid_keys = {f.name for f in fields(self.user_cfg.__class__)}
            for k, v in config.items():
                if k in valid_keys:
                    setattr(self.user_cfg, k, v)
            self.user_cfg.save()
            return {"ok": True, "path": str(self.user_cfg.save.__func__.__qualname__)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def check_decrypt_tool(self) -> dict:
        """GUI 调用：检查解密工具路径是否有效。"""
        path = Path(self.user_cfg.decrypt_tool_path)
        return {
            "path": self.user_cfg.decrypt_tool_path,
            "exists": path.is_file(),
            "is_file": path.is_file(),
        }

    def pick_file(self, file_type: str = "directory") -> dict:
        """GUI 调用：弹出文件/目录选择对话框。

        file_type: "directory" / "file" / "save_file"
        """
        import webview
        window = webview.active_window()
        try:
            if file_type == "directory":
                result = window.create_file_dialog(webview.FileDialog.FOLDER)
                if result:
                    return {"path": str(result[0])}
                return {"cancelled": True}
            elif file_type == "file":
                result = window.create_file_dialog(
                    webview.FileDialog.OPEN,
                    file_types=("Log files (*.log;*.txt;*.enc)", "All files (*.*)"),
                )
                if result:
                    return {"path": str(result[0])}
                return {"cancelled": True}
            elif file_type == "save_file":
                result = window.create_file_dialog(
                    webview.FileDialog.SAVE,
                    file_types=("HTML files (*.html)", "All files (*.*)"),
                    save_filename="mcu_trace_report.html",
                )
                if result:
                    return {"path": str(result[0])}
                return {"cancelled": True}
        except Exception as e:
            return {"error": str(e)}
        return {"cancelled": True}

    # ============================================================
    # 分析相关
    # ============================================================

    def get_version(self) -> str:
        from . import __version__
        return __version__

    def analyze_path(self, path: str) -> dict:
        """GUI 调用：分析已解密的 logcat 目录。"""
        from .core.analyzer import analyze_session, session_to_dict
        from .core.importer import _collect_logcat_files
        from pathlib import Path

        p = Path(path)
        if not p.is_dir():
            return {"error": f"目录不存在: {path}"}

        logcat_files = _collect_logcat_files(p)
        if not logcat_files:
            return {"error": f"目录无 logcat 文件: {path}"}

        session = analyze_session(logcat_files, name=p.name)
        return session_to_dict(session)

    def import_and_analyze(self, enc_dir: str) -> dict:
        """GUI 调用：导入 .enc 目录 + 完整分析。

        v0.2.2: 支持实时进度回调（前端用圆形进度环 + 步骤列表展示）。
        进度通过 window.evaluate_js() 推送到前端。
        """
        from pathlib import Path
        import json
        import webview
        from .core.importer import import_enc_dir
        from .core.analyzer import analyze_session, session_to_dict
        from .core.config import get_config_dir

        enc_p = Path(enc_dir)
        if not enc_p.is_dir():
            return {"error": f"目录不存在: {enc_dir}"}

        work_p = get_config_dir() / "work" / enc_p.name

        # 阶段权重：导入 0~60%，分析 60~100%
        def _push(percent, message, phase=None):
            """通过 evaluate_js 把进度推送到前端。失败时静默（CLI/headless 模式）。"""
            try:
                # 限频：避免消息太密（subprocess 输出可能上百条）
                payload = json.dumps({"p": round(percent, 4), "msg": message, "phase": phase})
                window = webview.active_window()
                if window is not None:
                    window.evaluate_js(f"window.__mcuTraceUpdateProgress && window.__mcuTraceUpdateProgress({payload})")
            except Exception:
                pass

        def _importer_progress(msg, p):
            # importer 的 0~1 → 我们 phase=import 0~0.6
            _push(0.6 * p, msg, phase="import")

        # 阶段 1: 导入（解密 + 解压）
        _push(0.0, "🚀 开始导入 .enc 文件...", phase="import")
        try:
            result = import_enc_dir(
                enc_p,
                work_p,
                decrypt_exe=Path(self.user_cfg.decrypt_tool_path),
                progress_cb=_importer_progress,
            )
        except FileNotFoundError as e:
            return {"error": str(e)}
        if result.errors and not result.logcat_files:
            return {"error": "; ".join(result.errors)}
        _push(0.60, f"✅ 导入完成：{len(result.logcat_files)} 个 logcat 文件", phase="import")

        # 阶段 2: 分析（解析 + FSM + 电压 + 复位 + 关键字）
        def _analyzer_progress(p, msg):
            # analyzer 的 0~1 → 我们 phase=analyze 0.6~1.0
            _push(0.6 + 0.4 * p, msg, phase="analyze")

        _push(0.60, "🔍 开始分析...", phase="analyze")
        session = analyze_session(
            result.logcat_files,
            name=enc_p.name,
            progress_cb=_analyzer_progress,
        )

        # 缓存 session 到 work 目录，方便后续 GUI 导出报告
        cache = work_p / "session.json"
        cache.write_text(
            json.dumps(session_to_dict(session), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        _push(1.0, f"🎉 分析完成：{len(session.events)} 条事件", phase="done")
        return {
            "ok": True,
            "work_dir": str(work_p),
            "session": session_to_dict(session),
        }

    def export_html(self, work_dir: str, output: str) -> dict:
        """GUI 调用：从缓存的 session 导出 HTML 报告。"""
        from pathlib import Path
        from .core.reporter import export_html_report
        from .core.models import LogEvent, LogSession, KeywordHit, VoltagePoint, RstEvent, FsmTransition, Severity
        from datetime import datetime
        import json

        wd = Path(work_dir)
        cache = wd / "session.json"
        if not cache.is_file():
            return {"error": f"找不到会话缓存: {cache}"}

        data = json.loads(cache.read_text(encoding="utf-8-sig"))
        # 重建 LogSession（简化版：从 dict 恢复关键字段）
        session = LogSession(name=data["name"], source_files=data.get("source_files", []))
        session.events = [LogEvent(**{k: v for k, v in e.items() if k in LogEvent.__dataclass_fields__}) for e in data.get("events", [])]
        for e in session.events:
            if e.timestamp and isinstance(e.timestamp, str):
                try:
                    e.timestamp = datetime.fromisoformat(e.timestamp)
                except ValueError:
                    e.timestamp = None
        session.voltage_points = [VoltagePoint(**{k: v for k, v in p.items() if k in VoltagePoint.__dataclass_fields__}) for p in data.get("voltage_points", [])]
        for vp in session.voltage_points:
            if isinstance(vp.timestamp, str):
                vp.timestamp = datetime.fromisoformat(vp.timestamp)
        session.rst_events = [RstEvent(**{k: v for k, v in r.items() if k in RstEvent.__dataclass_fields__}) for r in data.get("rst_events", [])]
        for re_ in session.rst_events:
            if isinstance(re_.timestamp, str):
                re_.timestamp = datetime.fromisoformat(re_.timestamp)
        session.fsm_transitions = [FsmTransition(**{k: v for k, v in t.items() if k in FsmTransition.__dataclass_fields__}) for t in data.get("fsm_transitions", [])]
        for t in session.fsm_transitions:
            if isinstance(t.timestamp, str):
                t.timestamp = datetime.fromisoformat(t.timestamp)
        # keyword_hits 嵌套
        khs = []
        for k in data.get("keyword_hits", []):
            ev_data = {kk: vv for kk, vv in k.items() if kk in LogEvent.__dataclass_fields__}
            ev = LogEvent(**ev_data)
            if isinstance(ev.timestamp, str):
                ev.timestamp = datetime.fromisoformat(ev.timestamp)
            khs.append(KeywordHit(
                event=ev,
                pattern=k["pattern"],
                category=k["category"],
                severity=Severity(k.get("severity", 0)),
                matched_text=k["matched_text"],
            ))
        session.keyword_hits = khs
        tr = data.get("time_range", [None, None])
        session.time_range = (
            datetime.fromisoformat(tr[0]) if tr[0] else None,
            datetime.fromisoformat(tr[1]) if tr[1] else None,
        )

        try:
            html_path = export_html_report(session, Path(output))
            return {"ok": True, "path": str(html_path), "size": html_path.stat().st_size}
        except Exception as e:
            import traceback
            return {"error": str(e), "traceback": traceback.format_exc()}

    # ============================================================
    # v0.2+: 规则编辑
    # ============================================================

    def get_user_rules(self) -> dict:
        """GUI 调用：读取 %APPDATA%\\MCU_TRACE\\user_rules.json。"""
        from .core.rules_loader import load_user, get_user_rules_path
        try:
            data = load_user()
            return {
                "ok": True,
                "path": str(get_user_rules_path()),
                "exists": data != {},
                "rules": data,
                # 也返回 builtin 的 number_mappings/keyword_rules/voltage_extractors，
                # 方便 GUI 显示"未改"占位
                "builtin_preview": {
                    "number_mappings_keys": ["soc_mode", "rst_type", "rst_reason"],
                },
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_builtin_rules_preview(self) -> dict:
        """GUI 调用：读取 builtin_rules.json 的 3 类，用于"恢复默认"对比展示。"""
        from .core.rules_loader import load_builtin
        try:
            data = load_builtin()
            return {
                "ok": True,
                "number_mappings": data.get("number_mappings", {}),
                "keyword_rules": data.get("keyword_rules", []),
                "voltage_extractors": data.get("voltage_extractors", []),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def save_user_rules(self, rules: dict) -> dict:
        """GUI 调用：保存用户规则到 %APPDATA%\\MCU_TRACE\\user_rules.json。

        写入前全量校验；任何一条坏规则都拒绝写入。
        """
        from .core.rules_loader import (
            save_user, validate_user_rules, RuleValidationError,
        )
        try:
            validate_user_rules(rules)
            path = save_user(rules)
            return {"ok": True, "path": str(path)}
        except RuleValidationError as e:
            return {"ok": False, "error": str(e), "validation": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def reset_user_rules(self) -> dict:
        """GUI 调用：删除 user_rules.json（恢复仅 builtin 生效）。"""
        from .core.rules_loader import get_user_rules_path
        p = get_user_rules_path()
        if p.is_file():
            try:
                p.unlink()
            except OSError as e:
                return {"ok": False, "error": str(e)}
        return {"ok": True, "path": str(p), "existed": True}

    def validate_pattern(self, category: str, pattern: str) -> dict:
        """GUI 调用：实时校验正则（不写盘）。返回 {ok, error}。"""
        from .core.rules_loader import validate_pattern as _vp
        return _vp(category, pattern)
