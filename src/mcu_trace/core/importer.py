"""解密 + 解压编排：负责把 .enc 复制到 decrypt-update 目录、调 hsaedecrypt.exe、解 .dec、整理成可解析的 logcat 路径列表。

GUI 调用：
    paths = importer.import_enc_dir(src_dir, progress_cb=...)
    # paths: [Path, ...] 按文件名时间戳升序
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)

# decrypt-update 工具默认位置（用户在 GUI 设置面板可改）
DEFAULT_DECRYPT_DIR = Path(r"E:\Data\桌面工具\decrypt-update\decrypt-update\logd")
DEFAULT_DECRYPT_EXE = Path(r"E:\Data\桌面工具\decrypt-update\decrypt-update\hsaedecrypt.exe")


@dataclass
class ImportResult:
    """导入结果。"""
    enc_files: list[Path]             # 复制进去的 .enc（按时间排序）
    logcat_files: list[Path]          # 解密 + 解压后的 logcat 文件（按时间+序号排序）
    work_dir: Path                    # 工作目录（用户配置的目标位置）
    skipped: list[Path] = None        # 跳过的 .enc
    errors: list[str] = None          # 错误信息

    def __post_init__(self):
        if self.skipped is None:
            self.skipped = []
        if self.errors is None:
            self.errors = []


ProgressCb = Callable[[str, float], None]   # (message, progress 0~1)


def import_enc_dir(
    src_dir: Path,
    work_dir: Path,
    *,
    decrypt_dir: Path = DEFAULT_DECRYPT_DIR,
    decrypt_exe: Path = DEFAULT_DECRYPT_EXE,
    progress_cb: Optional[ProgressCb] = None,
    keep_existing: bool = True,
) -> ImportResult:
    """导入 .enc 目录：

    1. 在 src_dir 找所有 .zip.enc（按文件名时间戳升序）
    2. 复制到 decrypt_dir（保留原 .bak 备份）
    3. 调用 hsaedecrypt.exe logd 原地解密 → 生成 .dec
    4. 把 .dec 文件按 zipfile 解压到 enc_basename 子目录
    5. 把子目录里的 logcat/logcat.NNN 拷贝到 work_dir
    6. 返回 logcat 文件列表（按时间+序号排序）
    """
    def _progress(msg: str, p: float) -> None:
        log.info("[%.0f%%] %s", p * 100, msg)
        if progress_cb:
            progress_cb(msg, p)

    result = ImportResult(enc_files=[], logcat_files=[], work_dir=work_dir)

    # 0. 校验
    if not src_dir.is_dir():
        raise FileNotFoundError(f"源目录不存在: {src_dir}")
    if not decrypt_exe.is_file():
        raise FileNotFoundError(
            f"hsaedecrypt.exe 不存在: {decrypt_exe}\n"
            f"请在 GUI 设置面板配置解密工具路径。"
        )
    decrypt_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1. 找所有 .zip.enc
    _progress("扫描 .enc 文件...", 0.05)
    enc_files = sorted(src_dir.glob("*.zip.enc"))
    if not enc_files:
        result.errors.append(f"源目录无 .zip.enc 文件: {src_dir}")
        return result
    result.enc_files = enc_files
    _progress(f"找到 {len(enc_files)} 个 .enc", 0.1)

    # 2. 复制到 decrypt_dir
    _progress(f"复制 {len(enc_files)} 个 .enc 到解密目录...", 0.15)
    for i, enc in enumerate(enc_files, 1):
        dst = decrypt_dir / enc.name
        try:
            shutil.copy2(enc, dst)
        except OSError as e:
            result.errors.append(f"复制失败: {enc.name} -> {e}")
        _progress(f"复制 {enc.name}", 0.15 + 0.1 * i / len(enc_files))

    # 3. 调 hsaedecrypt.exe logd → 生成 .dec
    _progress("调用 hsaedecrypt.exe 解密...", 0.3)
    try:
        proc = subprocess.run(
            [str(decrypt_exe), "logd"],
            cwd=decrypt_dir.parent,
            capture_output=True,
            text=True,
            timeout=600,
        )
        log.info("hsaedecrypt stdout: %s", proc.stdout[:500])
        if proc.returncode != 0:
            result.errors.append(
                f"hsaedecrypt 退出码 {proc.returncode}\n"
                f"stderr: {proc.stderr[:500]}"
            )
            return result
    except subprocess.TimeoutExpired:
        result.errors.append("hsaedecrypt 超时（>10min）")
        return result
    _progress("解密完成", 0.4)

    # 4. 解压 .dec → 子目录
    # .dec 文件名: 001_001_20260629122126.zip.dec
    # enc_basename: 001_001_20260629122126
    _progress("解压 .dec 文件...", 0.45)
    dec_count = 0
    dec_files = list(decrypt_dir.glob("*.dec"))
    for dec_file in dec_files:
        stem = dec_file.name
        if stem.endswith(".zip.dec"):
            enc_base = stem[:-len(".zip.dec")]
        else:
            enc_base = dec_file.stem
        target_dir = decrypt_dir / enc_base
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            _extract_flat(dec_file, target_dir)
            dec_count += 1
        except zipfile.BadZipFile as e:
            result.errors.append(f"解压失败: {dec_file.name} -> {e}")
    _progress(f"解压 {dec_count} 个 .dec 完成", 0.55)

    # 5. 把子目录里的 logcat 文件拷到 work_dir
    _progress("整理 logcat 文件...", 0.6)
    for i, enc in enumerate(enc_files, 1):
        sub = decrypt_dir / enc.name[:-len(".zip.enc")]
        if not sub.is_dir():
            log.warning("解密后无子目录: %s", sub)
            result.skipped.append(enc)
            continue
        target = work_dir / enc.name[:-len(".zip.enc")]
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(sub, target)
        _progress(
            f"整理 {enc.name}",
            0.6 + 0.3 * i / len(enc_files),
        )

    # 6. 收集所有 logcat 文件
    _progress("排序 logcat 文件...", 0.9)
    logcat_files = _collect_logcat_files(work_dir)
    result.logcat_files = logcat_files
    _progress(f"共 {len(logcat_files)} 个 logcat 文件就绪", 1.0)

    return result


def _collect_logcat_files(work_dir: Path) -> list[Path]:
    """从 work_dir 下所有子目录收集 logcat / logcat.NNN 文件并排序。

    排序规则：
    1. 顶层子目录按名字字典序（XXX_YYY_YYYYMMDDHHMMSS）= 时间正序
    2. 单个目录内：logcat.NNN 按 N 倒序（020→001→0），logcat 排最后（最新）
    """
    subdirs = sorted(
        [d for d in work_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )
    result: list[Path] = []
    for sub in subdirs:
        files = list(sub.glob("logcat*"))

        def sort_key(p: Path) -> tuple:
            name = p.name
            if name == "logcat":
                return (1, 0)
            if name.startswith("logcat."):
                num_str = name[len("logcat."):]
                try:
                    num = int(num_str)
                    return (0, -num)
                except ValueError:
                    return (2, name)
            return (3, name)
        files_sorted = sorted(files, key=sort_key)
        result.extend(files_sorted)
    return result


def parse_enc_timestamp(enc_name: str) -> Optional[datetime]:
    """从 .enc 文件名提取时间戳。文件名格式: XXX_YYY_YYYYMMDDHHMMSS.zip.enc"""
    import re
    m = re.search(r"(\d{14})", enc_name)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
        except ValueError:
            return None
    return None


def _extract_flat(zip_path: Path, target_dir: Path) -> None:
    """解压 zip 到 target_dir，展平一层目录（去掉 zip 内的顶层目录）。"""
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            # 形如 "001_001_20260629122126/logcat.001" -> "logcat.001"
            if "/" in member:
                target_name = member.split("/", 1)[1]
            else:
                target_name = member
            if not target_name or target_name.endswith("/"):
                continue
            target_path = target_dir / target_name
            with zf.open(member) as src, open(target_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
