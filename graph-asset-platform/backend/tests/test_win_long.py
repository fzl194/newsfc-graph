"""win_long（\\\\?\\ 长路径前缀）单测 + 深路径枚举回归。

背景（2026-08-25 长路径修复评审）：Windows LongPathsEnabled=0 时 >260 路径的
fs 调用抛 WinError 3；而**普通路径的 rglob/exists 对 >260 条目不报错而是静默
漏扫/False**——所以枚举与存在性判断也必须走长前缀。本文件锁定：
1. 前缀生成规则（盘符 / UNC / 幂等）
2. exporter 内联副本与 config.win_long 行为一致（两处同步要求）
3. 深路径真实行为：普通 rglob 漏扫、长前缀 rglob 命中（Windows only）
"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

from app.config import win_long


# ---------- 前缀生成规则 ----------

@pytest.mark.skipif(os.name != "nt", reason="Windows 长路径语义")
def test_win_long_drive_path(tmp_path):
    p = win_long(tmp_path / "a.md")
    assert str(p).startswith("\\\\?\\")
    assert ":" in str(p)  # 盘符保留
    assert not str(p).startswith("\\\\?\\\\")  # 不是误拼的双反斜杠（UNC bug 形态）


@pytest.mark.skipif(os.name != "nt", reason="Windows 长路径语义")
def test_win_long_unc_path():
    """UNC → \\\\?\\UNC\\server\\share（直接拼 \\\\?\\ 是非法路径，评审 MEDIUM-3）。"""
    p = win_long(Path("\\\\fileserver\\share\\gap\\assets"))
    assert str(p).startswith("\\\\?\\UNC\\")
    assert "fileserver" in str(p)
    assert not str(p).startswith("\\\\?\\\\")  # 非法形态红线


@pytest.mark.skipif(os.name != "nt", reason="Windows 长路径语义")
def test_win_long_idempotent(tmp_path):
    once = win_long(tmp_path)
    assert win_long(once) == once  # 已带前缀原样返回


def test_win_long_relative_resolved(tmp_path, monkeypatch):
    """相对路径经 abspath 解析为绝对（\\?\\ 前缀要求绝对路径）。"""
    if os.name != "nt":
        pytest.skip("Windows 长路径语义")
    monkeypatch.chdir(tmp_path)
    p = win_long(Path("sub/x.md"))
    assert p.is_absolute()
    assert str(p).startswith("\\\\?\\")


# ---------- exporter 内联副本同步 ----------

def _load_exporter():
    """与 runner._load_exporter 同款按路径加载（含 sys.modules 注册）。"""
    f = Path(__file__).resolve().parents[1] / "app" / "pipeline" / "product_doc_md_exporter_optimized.py"
    spec = importlib.util.spec_from_file_location("test_pipeline_exporter", f)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(os.name != "nt", reason="Windows 长路径语义")
def test_exporter_inline_copy_matches_config(tmp_path):
    """两处 _win_long 行为一致（文档要求'改动时两处同步'，本用例锁死该约定）。"""
    exp = _load_exporter()
    cases = [
        tmp_path / "a.md",
        Path("\\\\srv\\share\\x"),
        win_long(tmp_path),  # 幂等入参
        Path("rel/x.md"),   # 相对入参
    ]
    for c in cases:
        assert str(exp._win_long(c)) == str(win_long(c)), f"不一致: {c}"


# ---------- 解压长路径（extract_hdx_file 逐成员版，2026-08-25 解压失败回归） ----------

@pytest.mark.skipif(os.name != "nt", reason="Windows 长路径语义")
def test_extract_long_path_deep_member(tmp_path):
    """归档内 >260 成员（嵌套资源 zip 同款）解压成功且内容正确。

    原 ``extractall`` 普通路径 open() 抛 FileNotFoundError（内网现场）。
    """
    import zipfile
    exp = _load_exporter()
    deep_name = "/".join(["d" * 90] * 3 + ["UDG_" + "x" * 90 + "_CH_0000002282477504.zip"])
    zpath = tmp_path / "arch.hwics"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("index.html", "<html></html>")
        z.writestr(deep_name, "ZIPCONTENT")
    try:
        extracted = exp.extract_hdx_file(str(zpath))
        f = Path(extracted) / Path(*deep_name.split("/"))
        assert len(str(f)) > 260
        assert win_long(f).read_bytes() == b"ZIPCONTENT"
        # 正常成员不受影响
        assert win_long(Path(extracted) / "index.html").exists()
    finally:
        import shutil
        shutil.rmtree(win_long(Path(extracted)), ignore_errors=True)


def test_extract_sanitizes_zip_slip(tmp_path):
    """成员名含 ``..`` → 剥离后落解压目录内，不逃逸（沿用 CPython 清洗规则）。"""
    import zipfile
    exp = _load_exporter()
    zpath = tmp_path / "arch2.hwics"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("../../evil.txt", "EVIL")
        z.writestr("ok.txt", "OK")
    extracted = exp.extract_hdx_file(str(zpath))
    extracted = Path(extracted)
    try:
        assert (extracted / "evil.txt").read_text(encoding="utf-8") == "EVIL"
        assert (extracted / "ok.txt").exists()
        assert not (tmp_path / "evil.txt").exists()  # 未逃逸到解压目录之外
    finally:
        import shutil
        shutil.rmtree(extracted, ignore_errors=True)


# ---------- 深路径真实行为（回归：静默漏扫 vs 长前缀命中） ----------

@pytest.mark.skipif(os.name != "nt", reason="Windows 长路径语义")
def test_deep_path_enumeration_normal_misses_long_finds(tmp_path):
    """>260 文件：普通 rglob 静默漏扫（统计偏小根因）、长前缀命中——修复的落点依据。"""
    deep = tmp_path / ("x" * 80) / ("y" * 80) / ("z" * 70) / ("d" * 60) / ("e" * 60)
    f = deep / "a.md"
    try:
        win_long(f.parent).mkdir(parents=True)
        win_long(f).write_text("x", encoding="utf-8")
        assert len(str(f)) > 260
        # 普通路径：不抛错但漏扫（评审 MEDIUM-1 的实测依据）
        assert sum(1 for _ in tmp_path.rglob("*.md")) == 0
        # 长前缀：命中
        assert sum(1 for _ in win_long(tmp_path).rglob("*.md")) == 1
        # 普通相对计算在长前缀下会算错 → rel 计算两侧须同前缀（locate 修复依据）
        rel = win_long(f).relative_to(win_long(tmp_path)).as_posix()
        assert rel.endswith("a.md")
    finally:
        import shutil
        shutil.rmtree(win_long(tmp_path / ("x" * 80)), ignore_errors=True)
