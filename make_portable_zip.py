"""重新打 zip：让 exe 直接在解压根目录，没有外层 MCU_TRACE/ 子目录。

用户期望：双击 MCU_TRACE.exe 就能跑，不要 install.ps1。
"""
import os
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, r'E:\Git_PJ\MCU_TRACE\src')

PROJECT = Path(r'E:\Git_PJ\MCU_TRACE')
SRC = PROJECT / "dist" / "MCU_TRACE"
OUT = PROJECT / "dist" / "MCU_TRACE_v0.1.0_portable.zip"
README = PROJECT / "README_PORTABLE.md"

if not SRC.is_dir():
    raise SystemExit(f"Missing: {SRC}")

# 清理旧 zip
if OUT.exists():
    OUT.unlink()

# 写 zip：把 SRC 的内容直接放进 zip 根
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    count = 0
    for root, dirs, files in os.walk(SRC):
        rel_root = Path(root).relative_to(SRC)
        for d in dirs:
            # 不需要中间空目录条目
            pass
        for f in files:
            src_path = Path(root) / f
            # arcname: 用相对 SRC 的路径（去掉外层 MCU_TRACE/）
            arc = (rel_root / f).as_posix()
            zf.write(src_path, arc)
            count += 1
print(f"wrote {count} files to {OUT}")

# 验证顶层
import zipfile as zf2
with zf2.ZipFile(OUT) as zf:
    names = zf.namelist()
    print(f"\n=== 顶层条目（应有 MCU_TRACE.exe 在根）===")
    top_level = sorted(set(n.split('/')[0] for n in names))
    for t in top_level[:20]:
        print(f"  {t}")

# 写 README
readme_content = """# MCU TRACE 工具 v0.1.0 (便携版)

> 绿色版 — 解压即用，不写注册表，不创建额外快捷方式，卸载=删除文件夹。

## 使用方法

1. 把 `MCU_TRACE_v0.1.0_portable.zip` 解压到任意目录（如 `D:\\Tools\\MCU_TRACE\\`）
2. 双击文件夹里的 **`MCU_TRACE.exe`** 启动

## 系统要求

- Windows 10 1803+ / Windows 11
- WebView2 Runtime（Win10 1803+ 一般自带）
- 公司的 `hsaedecrypt.exe`（首次导入 .enc 需用）

## 首次使用

1. 双击 MCU_TRACE.exe 启动
2. 切到「⚙️ 设置」标签
3. 确认 `hsaedecrypt.exe` 路径（默认 `E:\\Data\\桌面工具\\decrypt-update\\decrypt-update\\hsaedecrypt.exe`）
4. 切到「📊 分析」→ 「浏览」选 .enc 目录 → 「📥 导入并分析」
5. 「📄 导出 HTML 报告」存成自包含 .html

## 用户配置

配置文件：`%APPDATA%\\MCU_TRACE\\config.json`
（首次运行自动创建默认配置，无需手动管理）

## 卸载

- 直接删除解压的文件夹即可
- 如需彻底清除：`删除 %APPDATA%\\MCU_TRACE\\ 文件夹`

## 管理员权限？

不需要。普通用户权限即可。
"""

README.write_text(readme_content, encoding='utf-8')
print(f"\nREADME: {README}")
print("done")
