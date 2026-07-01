"""MCU_TRACE 主入口。

两种模式：
1. GUI 模式（默认）：启动 pywebview 窗口
2. CLI 模式（--e2e / --analyze）：跑分析并输出 JSON / HTML 报告

用法：
    python -m mcu_trace                       # 启动 GUI
    python -m mcu_trace --e2e <enc_dir>       # E2E 流程，输出 mock_report.html
    python -m mcu_trace --analyze <log_dir>   # 只分析已解密 logcat 目录
    python -m mcu_trace --version             # 显示版本
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from mcu_trace import __version__
from mcu_trace.core.analyzer import analyze_session, session_to_dict
from mcu_trace.core.importer import import_enc_dir

log = logging.getLogger(__name__)


def cmd_gui() -> int:
    """启动 GUI。"""
    try:
        from mcu_trace.app import run_gui
        run_gui()
    except ImportError as e:
        print(f"GUI 启动失败: {e}", file=sys.stderr)
        print("提示：pywebview 可能在某些环境（如 headless server）下无法启动。", file=sys.stderr)
        return 1
    return 0


def cmd_e2e(enc_dir: Path, output: Path) -> int:
    """E2E：解密 → 解析 → 报告。"""
    work_dir = (Path(__file__).parent.parent.parent / "work" / "_e2e").resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] 导入 .enc 目录: {enc_dir}")
    import_result = import_enc_dir(enc_dir, work_dir, progress_cb=_print_progress)
    if import_result.errors:
        print("导入错误：", file=sys.stderr)
        for e in import_result.errors:
            print(f"  - {e}", file=sys.stderr)
        if not import_result.logcat_files:
            return 1
    print(f"  → {len(import_result.logcat_files)} 个 logcat 文件")

    print(f"[2/4] 解析 + 分析")
    session = analyze_session(
        import_result.logcat_files,
        name=enc_dir.name,
    )
    stats = session.stats()
    print(f"  → {stats['mcu_trace_events']} 条 mcu_trace 事件")
    print(f"  → {stats['fsm_transitions']} 条状态转换（{stats['fsm_illegal']} 非法）")
    print(f"  → {stats['voltage_points']} 个电压点")
    print(f"  → {stats['rst_events']} 个复位事件")
    print(f"  → {stats['keyword_hits']} 个关键字命中")

    print(f"[3/4] 导出 JSON 摘要: {output}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".json").write_text(
        json.dumps(session_to_dict(session), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"[4/4] 导出 HTML 报告: {output}")
    try:
        from mcu_trace.core.reporter import export_html_report
        export_html_report(session, output)
    except ImportError as e:
        print(f"  HTML 报告导出失败（matplotlib 缺失?）: {e}", file=sys.stderr)
        print("  跳过 HTML 导出，只保留 JSON", file=sys.stderr)

    print(f"\n✅ E2E 完成！")
    print(f"  HTML: {output.resolve()}")
    print(f"  JSON: {output.with_suffix('.json').resolve()}")
    return 0


def cmd_analyze(log_dir: Path, output: Path) -> int:
    """只分析已解密的 logcat 目录（跳过解密）。"""
    from mcu_trace.core.parser import parse_session
    from mcu_trace.core.importer import _collect_logcat_files
    logcat_files = _collect_logcat_files(log_dir)
    print(f"找到 {len(logcat_files)} 个 logcat 文件")
    events = parse_session(logcat_files)
    print(f"解析到 {len(events)} 条 mcu_trace 事件")

    session = analyze_session(logcat_files, name=log_dir.name)
    print(f"统计: {session.stats()}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".json").write_text(
        json.dumps(session_to_dict(session), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"输出: {output.with_suffix('.json')}")
    return 0


def _print_progress(msg: str, p: float) -> None:
    print(f"  [{int(p*100):3d}%] {msg}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(prog="mcu-trace", description="MCU 日志自动解析分析工具")
    sub = parser.add_subparsers(dest="cmd")

    # 默认（无子命令）= GUI
    parser.add_argument("--version", action="store_true")

    p_e2e = sub.add_parser("e2e", help="E2E：解密 + 解析 + 报告")
    p_e2e.add_argument("enc_dir", type=Path, help=".enc 所在目录")
    p_e2e.add_argument("-o", "--output", type=Path, default=Path("mock_report.html"))

    p_analyze = sub.add_parser("analyze", help="只分析已解密的 logcat 目录")
    p_analyze.add_argument("log_dir", type=Path, help="logcat 根目录（含子目录）")
    p_analyze.add_argument("-o", "--output", type=Path, default=Path("analyze_result.json"))

    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )

    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.version:
        print(f"mcu-trace v{__version__}")
        return 0

    if args.cmd is None:
        # 默认 GUI
        return cmd_gui()
    elif args.cmd == "e2e":
        return cmd_e2e(args.enc_dir, args.output)
    elif args.cmd == "analyze":
        return cmd_analyze(args.log_dir, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
