# -*- mode: python ; coding: utf-8 -*-
"""MCU_TRACE PyInstaller spec —— 目录模式打包

用法：
    cd MCU_TRACE
    pyinstaller installer/mcu_trace.spec --clean --noconfirm
    Compress-Archive -Path dist/MCU_TRACE -DestinationPath dist/MCU_TRACE_v0.1.0_20260630.zip
"""
import os
from pathlib import Path

block_cipher = None
PROJECT_ROOT = Path(os.path.abspath(SPECPATH)).parent  # SPECPATH = installer/ → parent = project root
SRC = PROJECT_ROOT / "src"
ASSETS = SRC / "mcu_trace" / "assets"
WEB = SRC / "mcu_trace" / "web"

a = Analysis(
    [str(SRC / "mcu_trace" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[
        # 前端 HTML/JS/CSS（包到 mcu_trace/ 下以匹配代码中 __file__.parent.parent 的查找）
        (str(WEB / "index.html"),   "mcu_trace/web"),
        (str(WEB / "vendor"),       "mcu_trace/web/vendor"),
        # 内置配置 + 报告模板
        (str(ASSETS / "config"),    "mcu_trace/assets/config"),
        (str(ASSETS / "templates"), "mcu_trace/assets/templates"),
        (str(ASSETS / "samples"),   "mcu_trace/assets/samples"),
    ],
    hiddenimports=[
        "webview",
        "webview.platforms.winforms",
        "matplotlib",
        "matplotlib.backends.backend_agg",
        "jinja2",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "pydoc",
        "doctest",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "IPython",
        "jupyter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,        # 目录模式关键
    name="MCU_TRACE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                    # 避免杀毒误报
    console=False,                # GUI 模式不弹黑窗
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                    # 可选：放个 .ico 图标
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MCU_TRACE",
)
