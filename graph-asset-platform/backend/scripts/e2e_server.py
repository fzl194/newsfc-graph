"""Playwright e2e 后端启动器：seed 固定语料/账号 → 起 uvicorn。

用法（由 frontend/playwright.config.ts 的 webServer 调起）：
    GAP_DATA_DIR=<abs>/e2e-data E2E_PORT=8001 python scripts/e2e_server.py

关键点：GAP_DATA_DIR 必须在 import app.* **之前**设好（config 在 import 时读环境变量），
因此本脚本先设 env 再做任何 app 导入。
"""
import os
import sys
from pathlib import Path

# backend/ + scripts/ 加入 sys.path（允许从任意 cwd 调起；seed_e2e 在 scripts/ 下）
_SCRIPTS = Path(__file__).resolve().parent
_BACKEND = _SCRIPTS.parent
_REPO = _BACKEND.parent
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_BACKEND))

_DATA_DIR = Path(os.environ.get("GAP_DATA_DIR") or (_REPO / "e2e-data"))
_PORT = int(os.environ.get("E2E_PORT", "8001"))

if __name__ == "__main__":
    os.environ["GAP_DATA_DIR"] = str(_DATA_DIR)
    # seed 必须在 uvicorn import app 之前跑完（先写盘，再起服务全量建库）
    from seed_e2e import seed
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    seed(_DATA_DIR)
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=_PORT, log_level="warning")
