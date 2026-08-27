"""入图闸门（gate，2026-08-26 抽取任务化）：沙箱 → diff 报告 → 三选 → 按任务回退。

架构：构建脚本写**沙箱 assets 根**（``DATA_DIR/.extract_gate/{job_id}/storage/``，
先预拷目标现有层供跨层读），正式资产目录永不见未确认内容——重启 mtime 对账不
污染、cancel 即删沙箱。confirm 时按磁盘实时重分类把变更文件拷入正式资产 +
增量索引；被覆盖文件旧版备份到 ``originals/{job_id}/`` 供按任务回退（revert）。

- diff：`_` 前缀 sidecar（_build_manifest.json）只静默同步不进报告（built_at 每次必变）；
  文本（.md/.txt）差异计 ±行数，二进制记字节大小。
- apply 以**实时磁盘重分类**为准（报告仅参考——awaiting 与 confirm 之间磁盘可能变过）。
- revert sha 守卫：磁盘内容 ≠ 清单记录（后续任务已覆盖）→ 跳过并计入警告，不误删。
- 锁序（与 run_mine 一致）：router 持 kind 互斥 → 本模块索引段取 service.import_lock。

全部文件系统操作走 ``win_long`` 长前缀（>260 路径静默漏扫教训，2026-08-25）。
"""
import difflib
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .. import config, jobs
from ..config import win_long as _win_long
from . import bundles

# 层 → 构建清单计数字段（result.layers 形状沿用旧 JobPanel）
COUNT_KEYS = {"Command": "command_count", "ConfigObject": "object_count",
              "License": "license_count", "Feature": "feature_count"}
_TEXT_SUFFIXES = {".md", ".txt"}
_MODIFIED_CAP = 500  # 报告内 modified 明细截断（modified_total 存真值）


def gate_root() -> Path:
    return config.DATA_DIR / ".extract_gate"


def gate_dir(job_id: str) -> Path:
    return gate_root() / job_id


def gate_storage(job_id: str) -> Path:
    """沙箱 assets 根（构建脚本 --storage 指向这里）。"""
    return gate_dir(job_id) / "storage"


def gate_originals(job_id: str) -> Path:
    """被覆盖文件的旧版备份（revert modify 项的还原源）。"""
    return gate_dir(job_id) / "originals"


# ---------- 基础件 ----------

def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(str(_win_long(p)), "rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _iter_files(base: Path):
    """长前缀枚举 base 下全部文件的相对 posix 路径（排序稳定）。"""
    root = _win_long(base)
    if not root.is_dir():
        return
    for p in sorted(root.rglob("*")):
        if p.is_file():
            yield p.relative_to(root).as_posix()


def _copy(src: Path, dst: Path) -> None:
    d = _win_long(dst)
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(_win_long(src)), str(d))


def cleanup(job_id: str) -> None:
    """删除该任务的整个门目录（沙箱+备份）。"""
    d = gate_dir(job_id)
    if _win_long(d).exists():
        shutil.rmtree(str(_win_long(d)), ignore_errors=True)


def sweep_orphan_gates() -> int:
    """启动清扫孤儿门目录：failed/cancelled/无主任务（processing 已被
    sweep_interrupted 标 failed → 其沙箱即孤儿）。

    **done 任务的 originals/ 备份是 revert 的还原源，必须保留**（直到按任务回退
    或删除任务历史时 cleanup）——评审修复 2026-08-26：清扫不得误删；
    awaiting（待闸门确认）的沙箱同样跨重启存活。
    """
    root = gate_root()
    if not root.is_dir():
        return 0
    n = 0
    for d in list(_win_long(root).iterdir()):  # list 化：边迭代边删安全
        if not d.is_dir():
            continue
        j = jobs.get_job(d.name)
        if j is None or j.status in ("failed", "cancelled"):
            shutil.rmtree(str(_win_long(d)), ignore_errors=True)
            n += 1
    return n


# ---------- 沙箱 ----------

def create_sandbox(job_id: str, layers, nf: str, version: str) -> list:
    """把目标 (nf,version) 已存在的层预拷进沙箱（构建脚本跨层读闭环）。

    分次累积语义依赖此步：第二批发号命令时，第一批命令 md 已在沙箱 Command 层，
    build_configobjects 才能基于全量命令产出。返回实际拷贝的层。
    """
    copied = []
    for layer in layers:
        src = config.ASSETS_DIR / layer / nf / version
        if not _win_long(src).is_dir():
            continue
        dst = gate_storage(job_id) / layer / nf / version
        _win_long(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(_win_long(src)), str(_win_long(dst)))
        copied.append(layer)
    return copied


# ---------- diff 报告 ----------

def _classify(sandbox_dir: Path, live_dir: Path):
    """沙箱 vs 正式逐文件分类。yields (rest_rel, kind, detail)：
    kind ∈ sidecar|new|identical|modified；detail=±行 dict 或 None。"""
    for rel in _iter_files(sandbox_dir):
        if Path(rel).name.startswith("_"):
            yield rel, "sidecar", None
            continue
        live = live_dir / rel
        if not _win_long(live).exists():
            yield rel, "new", None
            continue
        if _sha(live_dir / rel) == _sha(sandbox_dir / rel):
            yield rel, "identical", None
            continue
        if Path(rel).suffix.lower() in _TEXT_SUFFIXES:
            a = _win_long(live_dir / rel).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            b = _win_long(sandbox_dir / rel).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            plus = minus = 0
            for ln in difflib.unified_diff(a, b, n=0):
                # 头两行是无文件名的 "--- "/"+++ " 头；strip 精确匹配跳过，
                # 避免误跳以 ++ 开头的内容行（如 diff 嵌套文档）
                if ln.strip() in ("---", "+++"):
                    continue
                if ln.startswith("+"):
                    plus += 1
                elif ln.startswith("-"):
                    minus += 1
            yield rel, "modified", {"plus": plus, "minus": minus}
        else:
            yield rel, "modified", {
                "binary": True,
                "old_bytes": _win_long(live_dir / rel).stat().st_size,
                "new_bytes": _win_long(sandbox_dir / rel).stat().st_size,
            }


def diff_report(job_id: str, written_layers, nf: str, version: str) -> dict:
    """逐 written 层 diff 沙箱 vs 正式资产 → 闸门报告（awaiting 时入 job.result）。"""
    report = {
        "stage": "gate", "layers": list(written_layers),
        "new_total": 0, "new_by_layer": {},
        "identical_total": 0, "modified_total": 0, "modified": [], "sidecars": 0,
    }
    for layer in written_layers:
        sand = gate_storage(job_id) / layer / nf / version
        live = config.ASSETS_DIR / layer / nf / version
        for rel, kind, detail in _classify(sand, live):
            if kind == "sidecar":
                report["sidecars"] += 1
            elif kind == "new":
                report["new_total"] += 1
                report["new_by_layer"][layer] = report["new_by_layer"].get(layer, 0) + 1
            elif kind == "identical":
                report["identical_total"] += 1
            elif len(report["modified"]) < _MODIFIED_CAP:
                report["modified_total"] += 1
                report["modified"].append({"path": f"{layer}/{nf}/{version}/{rel}", **detail})
            else:
                report["modified_total"] += 1
    return report


# ---------- 三选 ----------

def _manifest_counts(job_id: str, written_layers, nf: str, version: str):
    """从沙箱构建清单读层计数（result.layers 形状沿用，JobPanel 兼容）。
    返回 (counts, missing_layers)——缺清单的层计 0 并告警（D20 沿用）。"""
    counts, missing = {}, []
    for layer in written_layers:
        p = gate_storage(job_id) / layer / nf / version / "_build_manifest.json"
        try:
            m = json.loads(_win_long(p).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            m = {}
            missing.append(layer)
        counts[layer] = m.get(COUNT_KEYS.get(layer, ""), 0) or 0
    return counts, missing


def apply_gate(job_id: str, action: str) -> dict:
    """confirm：把沙箱变更落正式资产 + 增量索引 + 产物清单入库。

    action ∈ overwrite（全量覆盖，modified 先备份旧版）| new_only（只落新文件，
    重复保留现有）。调用方须持 kind 互斥；job 须为 awaiting（router 已校验）。

    **崩溃自愈**（评审修复 2026-08-26）：清单行完全由「沙箱 vs 正式」分类推导
    （sha=沙箱内容=应用后内容），故**先写清单后拷贝**——拷贝中途崩溃重试时，
    已落盘文件分类为 identical，其上次清单行 merge 保留；未落盘文件重分类照常
    补拷。任何路径下清单都覆盖全部应落盘文件，revert 不会丢覆盖面。
    """
    from ..repos import extract_files_repo
    from ..service import get_service, import_lock
    svc = get_service()
    j = jobs.get_job(job_id)
    res = dict(j.result or {})
    nf, ver = res["target_nf"], res["target_version"]
    written = res.get("layers") or []
    stats = {"added": 0, "modified": 0, "skipped_identical": 0,
             "skipped_existing": 0, "sidecars": 0}
    extra_warnings: list = []

    # ---- Pass A：分类 + 计划（不落盘）----
    plan: list = []           # [(layer, rel, kind, sha_sandbox)]
    for layer in written:
        sand = gate_storage(job_id) / layer / nf / ver
        live_dir = config.ASSETS_DIR / layer / nf / ver
        for rel, kind, _detail in _classify(sand, live_dir):
            plan.append((layer, rel, kind, _sha(sand / rel) if kind != "sidecar" else ""))

    # ---- 清单先行（可完整推导）：当前分类行 ∪ 上次失败尝试的行 ----
    # 上次 apply 写过清单（成功后任务已 done 不可重试——只可能来自失败重试）
    prev = {r["path"]: r for r in extract_files_repo.list_for_job(svc.db, job_id)}
    rows_map: dict = {}
    for layer, rel, kind, sha_p in plan:
        rel_full = f"{layer}/{nf}/{ver}/{rel}"
        if kind == "sidecar":
            continue                                          # sidecar 不入清单
        if kind == "new":
            rows_map[rel_full] = (rel_full, "add", sha_p, layer)
        elif kind == "modified" and action == "overwrite":
            rows_map[rel_full] = (rel_full, "modify", sha_p, layer)
    for p, r in prev.items():                                 # 失败重试：已落盘文件保行
        rows_map.setdefault(p, (p, r["op"], r["sha256"], r["layer"]))
    with import_lock:
        extract_files_repo.replace_for_job(svc.db, job_id, list(rows_map.values()))
        svc.db.commit()

    # ---- Pass B：执行拷贝（清单已在库——中断重试自愈）----
    for layer, rel, kind, _sha_p in plan:
        sand = gate_storage(job_id) / layer / nf / ver
        live_dir = config.ASSETS_DIR / layer / nf / ver
        rel_full = f"{layer}/{nf}/{ver}/{rel}"
        if kind == "sidecar":
            _copy(sand / rel, live_dir / rel)
            stats["sidecars"] += 1
        elif kind == "new":
            _copy(sand / rel, live_dir / rel)
            stats["added"] += 1
        elif kind == "identical":
            stats["skipped_identical"] += 1
        elif action == "new_only":
            stats["skipped_existing"] += 1
        else:  # modified + overwrite：旧版备份后覆盖
            _copy(live_dir / rel, gate_originals(job_id) / rel_full)
            _copy(sand / rel, live_dir / rel)
            stats["modified"] += 1

    counts, missing = _manifest_counts(job_id, written, nf, ver)
    extra_warnings += [f"{L} 构建后 manifest 缺失（计数未知，请核查）" for L in missing]
    with import_lock:
        try:
            ix = svc.reindex_prefixes([f"{L}/{nf}/{ver}" for L in written])
        except Exception as e:  # noqa: BLE001 资产已落盘+清单已写——标 done 带告警（留在 awaiting 重试会因全 identical 空转）
            ix = {"indexed": 0, "removed": 0}
            extra_warnings.append(f"增量索引失败（{e}）——资产已入库，索引将由启动对账/下次抽取补齐")
        # 包元信息（最近抽取器；包可能已被替换/删除——尽力而为）
        try:
            bd = bundles.bundle_dir(res.get("bundle_nf", ""), res.get("bundle_version", ""))
            meta = bundles.read_meta(bd)
            if meta is not None:
                meta["mode_id"] = res.get("script", "")
                meta["mined_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                bundles.write_meta(bd, meta)
        except Exception:  # noqa: BLE001
            pass
    # 沙箱大头可清（originals 留给 revert）
    shutil.rmtree(str(_win_long(gate_storage(job_id))), ignore_errors=True)

    jobs.update_job(job_id, status="done",
                    result={**res, "stage": "applied", "applied": stats,
                            "layers": counts, "total": sum(counts.values())},
                    warnings=list(j.warnings or []) + extra_warnings,
                    added=stats["added"] + stats["modified"])
    return {"stats": stats, "layers": counts, "reindex": ix}


def cancel_gate(job_id: str) -> None:
    """撤销：沙箱全删，任务终态 cancelled——**正式资产零改动**（沙箱模型承诺）。

    apply 失败重试路径可能已**部分落盘**（清单先行设计）→ 按清单 sha 守卫回滚
    已落盘文件（add→删除，modify→还原 originals），再清沙箱与清单行。
    泄漏文件从未被索引（reindex 在拷贝之后），无需动 DB。
    """
    from ..repos import extract_files_repo
    from ..service import get_service
    svc = get_service()
    try:
        rows = extract_files_repo.list_for_job(svc.db, job_id)
    except Exception:  # noqa: BLE001
        rows = []
    for r in rows:
        live = config.ASSETS_DIR / r["path"]
        try:
            cur = _sha(live) if _win_long(live).exists() else None
        except OSError:
            cur = None
        if cur is None or cur != r["sha256"]:
            continue  # 未落盘（清单先行的正常形态）或已被外部改动——不动
        if r["op"] == "add":
            _win_long(live).unlink()
        else:  # modify → 还原旧版
            orig = gate_originals(job_id) / r["path"]
            if _win_long(orig).exists():
                _copy(orig, live)
    cleanup(job_id)
    try:
        extract_files_repo.delete_for_job(svc.db, job_id)
        svc.db.commit()
    except Exception:  # noqa: BLE001 孤儿清单行无害（job 已 cancelled 不可回退）
        pass
    jobs.update_job(job_id, status="cancelled")


# ---------- 按任务回退 ----------

def revert_job(job_id: str, deleted_by: str = "") -> dict:
    """移除本次抽取的内容：add→软删进回收站；modify→还原 originals 旧版。
    sha 守卫：磁盘内容 ≠ 清单记录（后续任务已覆盖）→ 跳过不误删。
    调用方须持 kind 互斥。"""
    from ..repos import extract_files_repo, trash_repo
    from ..service import get_service, import_lock
    j = jobs.get_job(job_id)
    res = dict(j.result or {})
    svc = get_service()
    out = {"soft_deleted": 0, "restored": 0, "skipped": []}
    prefixes: set = set()

    def _skip(path: str, why: str) -> None:
        out["skipped"].append(f"{path}（{why}）")

    with import_lock:
        for r in extract_files_repo.list_for_job(svc.db, job_id):
            live = config.ASSETS_DIR / r["path"]
            try:
                cur = _sha(live) if _win_long(live).exists() else None
            except OSError:
                cur = None
            if cur is None:
                _skip(r["path"], "文件已不存在")
                continue
            if cur != r["sha256"]:
                _skip(r["path"], "已被后续任务/手工修改，跳过防误删")
                continue
            try:
                if r["op"] == "add":
                    trash_id = svc.store.soft_delete(r["path"])
                    trash_repo.insert(
                        svc.db, trash_id=trash_id, original_path=r["path"],
                        is_dir=False, md_count=1 if r["path"].endswith(".md") else 0,
                        deleted_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        deleted_by=deleted_by)
                    out["soft_deleted"] += 1
                else:  # modify → 还原旧版
                    orig = gate_originals(job_id) / r["path"]
                    if not _win_long(orig).exists():
                        _skip(r["path"], "旧版备份缺失")
                        continue
                    _copy(orig, live)
                    out["restored"] += 1
            except (OSError, ValueError) as e:
                _skip(r["path"], f"操作失败: {e}")
                continue
            prefixes.add("/".join(r["path"].split("/")[:3]))  # Layer/nf/version

        svc.db.commit()
        if prefixes:
            out["reindex"] = svc.reindex_prefixes(sorted(prefixes))
        else:
            out["reindex"] = {"indexed": 0, "removed": 0}
        extract_files_repo.delete_for_job(svc.db, job_id)
        svc.db.commit()

    cleanup(job_id)  # originals 已消费
    jobs.update_job(job_id, status="done", result={
        **res, "stage": "applied", "reverted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "revert": {"soft_deleted": out["soft_deleted"], "restored": out["restored"],
                   "skipped": out["skipped"]}})
    return out


def reconcile_interrupted() -> int:
    """重启对账（main.py 在 ``sweep_interrupted`` **之前**调用）：中断于确认/回退
    **执行中**（status=processing + result.stage ∈ applying/reverting）的抽取任务复位。

    - applying → awaiting：清单先行+sha 守卫使重试安全；也可撤销（cancel 会按
      清单回滚已落盘部分）；
    - reverting → done + 告警：reverted_at 未写、清单行未消费（末尾才删），
      每文件守卫使重新发起「移除产出」安全。

    真正的抽取运行中断（stage=running）不在本函数范围——仍由 sweep_interrupted
    标 failed。返回复位数。
    """
    import time as _time
    db = jobs._db()
    try:
        rows = db.execute(
            "SELECT job_id, result, warnings FROM import_jobs "
            "WHERE kind='product_doc_mine' AND status='processing'").fetchall()
    except Exception:  # noqa: BLE001
        return 0
    n = 0
    for r in rows:
        try:
            res = json.loads(r["result"] or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if res.get("stage") == "applying":
            res["stage"] = "gate"
            res["confirm_error"] = "后端重启，入库执行中断——可重新确认或撤销"
            db.execute("UPDATE import_jobs SET status='awaiting', result=? WHERE job_id=?",
                       (json.dumps(res, ensure_ascii=False), r["job_id"]))
            n += 1
        elif res.get("stage") == "reverting":
            try:
                warns = json.loads(r["warnings"] or "[]")
            except (json.JSONDecodeError, TypeError):
                warns = []
            warns.append("后端重启，回退执行中断——可重新发起「移除产出」")
            res["revert_error"] = "后端重启，回退执行中断"
            db.execute(
                "UPDATE import_jobs SET status='done', result=?, warnings=?, finished_at=? "
                "WHERE job_id=?",
                (json.dumps(res, ensure_ascii=False), json.dumps(warns, ensure_ascii=False),
                 _time.time(), r["job_id"]))
            n += 1
    db.commit()
    # 内存副本同步（重启后 registry 为空；测试/同进程场景用）
    with jobs._lock:
        for jid in [r["job_id"] for r in rows]:
            if jid in jobs._registry:
                fresh = db.execute("SELECT * FROM import_jobs WHERE job_id=?", (jid,)).fetchone()
                if fresh:
                    jobs._registry[jid] = jobs._from_row(fresh)
    return n
