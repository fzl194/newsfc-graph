"""统计页总览配置（2026-09-03 用户需求：三层图谱进展总览，手动维护）。

数据源是 **配置文件** ``DATA_DIR/stats_overview.json``（随 platform-data 外挂/
迁移，不走库、不进镜像）——用户明确要手动维护；管理员也可经
``PUT /api/v1/stats/overview`` 在页面编辑（等价改文件，保存时校验+规整回写）。

结构（详见 StatsView 编辑弹窗内置模板）：
``{updated_at, updated_by, description, cards: [{title, accent, metrics:
[{label, value, progress?}]}]}``——卡片数/指标数/文案全可配；value 支持数字或
字符串（如 "18 / 22"），progress（0-100）存在时前端渲染进度条（覆盖率/进展）。
"""
import json
import time
from pathlib import Path

from .. import config

_OVERVIEW_NAME = "stats_overview.json"
_MAX_CARDS = 6
_MAX_METRICS = 8


def overview_path() -> Path:
    return Path(config.DATA_DIR) / _OVERVIEW_NAME


def _valid_metric(m: object) -> dict | None:
    if not isinstance(m, dict):
        return None
    label = m.get("label")
    value = m.get("value")
    if not isinstance(label, str) or not label.strip():
        return None
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    out = {"label": label.strip(), "value": value}
    progress = m.get("progress")
    if progress is not None:
        if not isinstance(progress, (int, float)) or isinstance(progress, bool) \
                or not 0 <= progress <= 100:
            return None
        out["progress"] = float(progress)
    return out


def validate(raw: object) -> dict:
    """校验并规整（丢未知键）；不合法抛 ValueError（中文可读，供 400）。"""
    if not isinstance(raw, dict):
        raise ValueError("配置须为 JSON 对象")
    cards = raw.get("cards")
    if not isinstance(cards, list) or not 1 <= len(cards) <= _MAX_CARDS:
        raise ValueError(f"cards 须为 1~{_MAX_CARDS} 张卡片的数组")
    out_cards = []
    for i, c in enumerate(cards, start=1):
        if not isinstance(c, dict) or not isinstance(c.get("title"), str) \
                or not c["title"].strip():
            raise ValueError(f"第 {i} 张卡片缺少非空 title")
        metrics = c.get("metrics", [])
        if not isinstance(metrics, list) or len(metrics) > _MAX_METRICS:
            raise ValueError(f"卡片「{c['title']}」metrics 须为不超过 {_MAX_METRICS} 条的数组")
        cleaned = []
        for m in metrics:
            cm = _valid_metric(m)
            if cm is None:
                raise ValueError(f"卡片「{c['title']}」存在非法指标（label 非空、"
                                 "value 为数字/字符串、progress 为 0~100 数字）")
            cleaned.append(cm)
        card = {"title": c["title"].strip(), "metrics": cleaned}
        accent = c.get("accent")
        if isinstance(accent, str) and accent.strip():
            card["accent"] = accent.strip()
        out_cards.append(card)
    out: dict = {"cards": out_cards}
    for k in ("description", "updated_at", "updated_by"):
        v = raw.get(k)
        if isinstance(v, str) and v.strip():
            out[k] = v
    return out


def load() -> dict:
    """GET 负载：文件缺失 → {available: False}（前端隐藏总览区/管理员见提示）。"""
    p = overview_path()
    if not p.is_file():
        return {"available": False, "config": None}
    try:
        cfg = validate(json.loads(p.read_text(encoding="utf-8")))
    except (ValueError, json.JSONDecodeError) as e:
        return {"available": False, "config": None, "error": f"配置文件无效: {e}"}
    return {"available": True, "config": cfg}


def save(raw: object, updated_by: str = "") -> dict:
    """管理员编辑入口：校验 → 盖 updated_at（无则补）→ 规整写盘。"""
    cfg = validate(raw)
    cfg.setdefault("updated_at", time.strftime("%Y-%m-%d"))
    if updated_by:
        cfg["updated_by"] = updated_by
    overview_path().write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg
