"""Playwright e2e 语料种子：写入固定多版本语料 + 固定账号到 GAP_DATA_DIR。

语料与 backend/tests/test_e2e_versions.py 同口径（双版本对象 / 仅旧版本对象 /
语义版本陷阱 / name_zh 中文 / 业务域），保证前端 e2e 与后端回归同源。

账号（users.json，首次启动由 migrate_users 导入 users 表）：
- admin / e2e-admin-key（全权限）
- viewer / e2e-viewer-key（仅 can_frontend，验证菜单显隐）
- agent / e2e-skill-key（仅 can_skill，验证 SKILL 接口鉴权）

幂等性：每次运行重写 assets md + users.json，并删除 platform.db（强制服务端
从 md 全量建库，避免脏库）。
"""
import json
import os
import shutil
import sys
from pathlib import Path


def _cmd_md(id_: str, version: str, name_zh: str, edge: tuple | None = None) -> str:
    lines = [
        "---",
        f"id: {id_}",
        "type: MMLCommand",
        f"name: {id_.split('@')[-1]}",
        f"name_zh: {name_zh}",
        "nf: " + id_.split("@", 1)[0],
        f"version: {version}",
        "status: active",
        "---",
        f"# {id_}",
        "",
        f"{name_zh}（{version}）。",
        "",
        "## 边",
    ]
    if edge is not None:
        lines.append(f"- {edge[0]}: [[{edge[1]}]]")
    return "\n".join(lines) + "\n"


ACT_DEMO = "UDG@MMLCommand@ACT DEMO"
OLD_ONLY = "UDG@MMLCommand@OLD ONLY"
SEM_TRAP = "UNC@MMLCommand@SEM TRAP"

FILES: dict[str, str] = {
    "Command/UDG/20.15.2/UDG@MMLCommand@ACT DEMO.md":
        _cmd_md(ACT_DEMO, "20.15.2", "演示命令", ("操作配置对象", "UDG@ConfigObject@URR")),
    "Command/UDG/20.16.2/UDG@MMLCommand@ACT DEMO.md":
        _cmd_md(ACT_DEMO, "20.16.2", "演示命令", ("参见", OLD_ONLY)),
    "Command/UDG/20.15.2/UDG@MMLCommand@OLD ONLY.md":
        _cmd_md(OLD_ONLY, "20.15.2", "仅旧版本"),
    "Command/UNC/20.9.10/UNC@MMLCommand@SEM TRAP.md":
        _cmd_md(SEM_TRAP, "20.9.10", "语义陷阱"),
    "Command/UNC/20.15.2/UNC@MMLCommand@SEM TRAP.md":
        _cmd_md(SEM_TRAP, "20.15.2", "语义陷阱"),
    "ConfigObject/UDG/20.15.2/UDG@ConfigObject@URR.md":
        "---\nid: UDG@ConfigObject@URR\ntype: ConfigObject\nname: URR\n"
        "name_zh: 用量统计规则\nnf: UDG\nversion: 20.15.2\n---\n# URR\n",
    "Business/demo/BusinessDomain@demo.md":
        "---\nid: BusinessDomain@demo\ntype: BusinessDomain\nname: demo域\n"
        "name_zh: 演示业务域\ndomain: demo\n---\n# demo\n业务域正文。\n",
}

USERS = {
    "users": [
        {"username": "admin", "key": "e2e-admin-key", "can_frontend": True,
         "can_assets": True, "can_upload": True, "can_test": True,
         "can_skill": True, "is_admin": True},
        {"username": "viewer", "key": "e2e-viewer-key", "can_frontend": True,
         "can_assets": False, "can_upload": False, "can_test": False,
         "can_skill": False, "is_admin": False},
        {"username": "agent", "key": "e2e-skill-key", "can_frontend": False,
         "can_assets": False, "can_upload": False, "can_test": False,
         "can_skill": True, "is_admin": False},
    ]
}


def seed(data_dir: Path) -> None:
    assets = data_dir / "assets"
    if assets.exists():
        shutil.rmtree(assets)
    for rel, text in FILES.items():
        p = assets / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    (data_dir / "users.json").write_text(
        json.dumps(USERS, ensure_ascii=False, indent=2), encoding="utf-8")
    # 脏库清理：强制服务端从 md 全量建库 + users.json 迁移
    for suffix in ("", "-wal", "-shm"):
        f = data_dir / f"platform.db{suffix}"
        if f.exists():
            f.unlink()
    print(f"[seed_e2e] 语料 {len(FILES)} md + {len(USERS['users'])} 账号 → {data_dir}", flush=True)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GAP_DATA_DIR", "")
    if not target:
        sys.exit("用法: python seed_e2e.py <data_dir>（或设 GAP_DATA_DIR）")
    seed(Path(target))
