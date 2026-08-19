#!/usr/bin/env python3
"""重置平台数据（重新测试用）：清图谱索引库 + 资产 + 原始文档 + 回收站/打点，
**保留管理员账号**（删库前把 users 表导回 users.json，重启时自动迁移恢复同 KEY）。

清什么：
  platform.db(+wal/shm)   索引/边/任务历史/打点/回收站记录（users 表先导出）
  assets/*                图谱资产 md/图片
  output/*                产品文档解压包（bundle）
  .trash/*                回收站文件
  telemetry/*             打点 jsonl（raw 备份）
  .pdoc_* / .pdoc_up_*    孤儿临时目录
不动：
  users.json              用户备份（删库前由 users 表刷新）
  tests/                  测试用例子系统（非图谱数据）
  users.json 之外的环境配置

用法（**先停平台**）：
  python scripts/reset_data.py          # 预览（dry-run，默认）
  python scripts/reset_data.py --yes    # 真正执行
"""
import argparse
import importlib.util
import json
import shutil
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _load_config():
    """按路径加载 app.config（支持 GAP_DATA_DIR 环境变量覆盖）。"""
    spec = importlib.util.spec_from_file_location("reset_cfg", BACKEND / "app" / "config.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def export_users(db_path: Path, users_file: Path) -> int:
    """users 表 → users.json（删库前保命；重启 migrate_users 自动导回，KEY 不变）。"""
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT username, key, can_frontend, can_assets, can_upload, "
            "can_test, can_skill, is_admin, created_at FROM users").fetchall()
    finally:
        conn.close()
    users = [dict(r) for r in rows]
    if users:
        users_file.write_text(
            json.dumps({"users": users}, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(users)


def clear_dir(d: Path, really: bool) -> int:
    """清空目录内容（保留目录本身）。返回清除条数。"""
    if not d.is_dir():
        return 0
    n = 0
    for p in d.iterdir():
        if p.name.startswith("."):
            continue
        n += 1
        if really:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)
    return n


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="重置平台数据（保留管理员）")
    ap.add_argument("--yes", action="store_true", help="真正执行（默认 dry-run 预览）")
    args = ap.parse_args()

    cfg = _load_config()
    data = cfg.DATA_DIR
    db = cfg.DB_PATH
    really = args.yes

    print(f"数据目录: {data}")
    print(f"{'【执行】' if really else '【预览，加 --yes 真正执行】'}")

    # 0. 导出用户（无论 dry-run 与否都先展示将保留的用户名）
    users_file = data / "users.json"
    n_users = export_users(db, users_file) if really else _count_users(db)
    print(f"  保留用户（users.json，重启自动恢复同 KEY）: {n_users} 个")

    # 1. 删库（含 wal/shm）——被占用说明平台还在跑：先中止，避免半清状态
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db) + suffix)
        if p.exists():
            size_kb = p.stat().st_size // 1024
            if really:
                try:
                    p.unlink()
                except PermissionError:
                    print(f"\n[中止] {p.name} 被占用——平台仍在运行。请先停止后端进程再执行 --yes。"
                          "\n（users.json 已导出，其余数据未动）")
                    return 1
            print(f"  删除: {p.name} ({size_kb} KB)")

    # 2. 清资产 / 原始文档 / 回收站 / 打点
    for name, label in (("assets", "图谱资产"), ("output", "原始产品文档"),
                        (".trash", "回收站"), ("telemetry", "打点")):
        n = clear_dir(data / name, really)
        print(f"  清空: {name}/（{label}）{n} 项")

    # 3. 孤儿临时目录
    n = 0
    for pat in (".pdoc_*", ".pdoc_up_*"):
        for p in data.glob(pat):
            n += 1
            if really:
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    p.unlink(missing_ok=True)
    print(f"  清理: 孤儿临时目录/文件 {n} 个")

    print(f"  保留: users.json / tests/（测试用例子系统）")
    if really:
        print("\n完成。启动平台后：users.json 自动迁移恢复管理员（KEY 不变）；"
              "索引为空库，重新上传/抽取即重建。")
    return 0


def _count_users(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
