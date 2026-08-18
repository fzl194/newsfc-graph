"""docs router：原始产品文档（output/ 目录）只读浏览。

「上传产品文档」的导出 md 留存于 ``GAP_DATA_DIR/output/{nf}_{version}/``——
**不进数据库、不进图谱**（与 assets 隔离），前端「图谱资产」tab 可切换浏览。

- 权限：走默认 frontend（只读，同 /objects 等前端接口；无写端点）。
- 返回结构与 ``/fs/children`` 同构（``[{name, path, is_dir, size}]``），
  前端文件浏览器切换根目录即可复用。
- 路径防逃逸：resolve 后必须仍在 OUTPUT_DIR 内。
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from .. import config

router = APIRouter()

_IMG_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico"}


def _resolve(rel: str) -> Path:
    """rel（相对 output 根，正斜杠）→ 防逃逸绝对路径。"""
    root_path = config.OUTPUT_DIR
    root_path.mkdir(parents=True, exist_ok=True)
    p = (root_path / rel).resolve() if rel else root_path.resolve()
    root = root_path.resolve()
    if p != root and root not in p.parents:
        raise HTTPException(status_code=400, detail="路径越界")
    return p


@router.get("/docs/children")
def list_children(path: str = ""):
    """列 output 下目录直接子项（懒加载；结构同 /fs/children，目录在前字母序）。"""
    d = _resolve(path)
    if not d.exists() or not d.is_dir():
        return []
    items = []
    for p in sorted(d.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        if p.name.startswith("."):
            continue
        items.append({
            "name": p.name,
            "path": str(p.relative_to(config.OUTPUT_DIR.resolve())).replace("\\", "/"),
            "is_dir": p.is_dir(),
            "size": p.stat().st_size if p.is_file() else 0,
        })
    return items


@router.get("/docs/file", response_class=PlainTextResponse)
def read_file(path: str):
    """读 md 文本（预览用；仅允许文本类扩展名）。"""
    p = _resolve(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail=f"文件不存在: {path}")
    if p.suffix.lower() not in {".md", ".txt", ".json", ".csv", ".xml", ".html"}:
        raise HTTPException(status_code=400, detail=f"不支持预览的文件类型: {p.suffix}")
    try:
        return PlainTextResponse(p.read_text(encoding="utf-8"),
                                 media_type="text/markdown; charset=utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="非 UTF-8 文本，请下载后查看")


@router.get("/docs/raw")
def read_raw(path: str):
    """图片二进制（output 内 md 的 ![](x.assets/y.png) 引用展示）。"""
    p = _resolve(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail=f"文件不存在: {path}")
    if p.suffix.lower() not in _IMG_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"仅支持图片文件: {p.suffix}")
    return FileResponse(p)
