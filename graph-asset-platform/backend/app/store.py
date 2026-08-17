import shutil
import uuid
from pathlib import Path


class Store:
    """统一资产库读写：在 <data>/assets/ 下按相对路径读写 md 文件。

    所有 rel（相对路径）参数均为使用正斜杠的归一化路径（如
    ``Command/UDG/20.15.2/UDG@MMLCommand@ADD URR.md``）。实现内部会做路径穿越防护，
    任何逃逸 assets 根的路径都会抛 ``ValueError``。

    软删除：trash 根是 assets 的**同级**目录（<data>/.trash），绝不能放进 assets 内——
    ``list_md()`` 用 ``rglob("*.md")`` 不过滤隐藏目录，trash 在 assets 内会被全量
    重建索引扫回。trash 内布局 ``.trash/{trash_id}/{原相对路径}``。
    """

    def __init__(self, assets_dir: Path):
        self.root = Path(assets_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        # resolve 一次缓存，避免每次调用都做系统调用
        self._root_resolved = self.root.resolve()
        # 回收站：assets 同级（config.TRASH_DIR 同一位置），扫描安全
        self.trash = self.root.parent / ".trash"
        self.trash.mkdir(parents=True, exist_ok=True)

    def _resolve(self, rel: str) -> Path:
        """把相对路径解析为绝对路径，并校验未逃逸 assets 根。"""
        rel_path = rel.replace("\\", "/")
        # 严格禁止绝对路径与盘符写法（Windows 下 "C:\\..." 会被 Path 拼接覆盖根）
        if rel_path.startswith("/"):
            raise ValueError(f"非法路径（绝对路径）: {rel}")
        # pathlib 的 join 对含 .. 的路径会原样拼接；用 os.path.normpath 思路：直接 resolve 后比对祖先
        p = (self.root / rel_path).resolve()
        root = self._root_resolved
        if p != root and root not in p.parents:
            raise ValueError(f"非法路径（逃逸 assets 根）: {rel}")
        return p

    def write(self, rel: str, text: str) -> None:
        p = self._resolve(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def write_bytes(self, rel: str, data: bytes) -> None:
        p = self._resolve(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def read(self, rel: str) -> str:
        return self._resolve(rel).read_text(encoding="utf-8")

    def exists(self, rel: str) -> bool:
        return self._resolve(rel).exists()

    def delete(self, rel: str) -> bool:
        """删文件；存在且是文件则删并返回 True，否则 False。"""
        p = self._resolve(rel)
        if p.exists() and p.is_file():
            p.unlink()
            return True
        return False

    def move(self, src_rel: str, dst_rel: str) -> None:
        """移动文件/目录；src 与 dst 都过 _resolve（防穿越）。"""
        src = self._resolve(src_rel)
        dst = self._resolve(dst_rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

    def rmtree(self, rel: str) -> bool:
        """删除整个目录；是目录且存在则删并返回 True。"""
        p = self._resolve(rel)
        if p.exists() and p.is_dir():
            shutil.rmtree(p)
            return True
        return False

    # ---------- 回收站（软删除）----------

    @staticmethod
    def _check_trash_id(trash_id: str) -> None:
        """trash_id 仅允许 hex（防路径穿越拼接）。"""
        if not trash_id or any(c not in "0123456789abcdef" for c in trash_id):
            raise ValueError(f"非法 trash_id: {trash_id}")

    def soft_delete(self, rel: str) -> str:
        """软删除：move 到 ``.trash/{uuid}/{原相对路径}``，返回 trash_id。内容完好可还原。"""
        src = self._resolve(rel)
        if not src.exists():
            raise FileNotFoundError(rel)
        trash_id = uuid.uuid4().hex[:12]
        dst = self.trash / trash_id / Path(rel.replace("\\", "/"))
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return trash_id

    def restore_from_trash(self, trash_id: str, rel: str) -> None:
        """从回收站还原到原路径。原路径被占用抛 FileExistsError（条目留在回收站）。"""
        self._check_trash_id(trash_id)
        if ".." in rel:
            raise ValueError(f"非法路径: {rel}")
        src = self.trash / trash_id / rel
        if not src.exists():
            raise FileNotFoundError(f"回收站条目不存在: {trash_id}")
        dst = self._resolve(rel)  # 校验未逃逸 assets 根
        if dst.exists():
            raise FileExistsError(f"原路径已被占用: {rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        leftover = self.trash / trash_id  # 清残留空目录
        if leftover.exists() and not any(leftover.rglob("*")):
            shutil.rmtree(leftover)

    def purge_trash(self, trash_id: str) -> bool:
        """永久删除单个回收站条目（物理删除，不可恢复）。"""
        self._check_trash_id(trash_id)
        p = self.trash / trash_id
        if p.exists():
            shutil.rmtree(p)
            return True
        return False

    def purge_all_trash(self) -> int:
        """清空回收站（物理删除全部条目）。返回清理的条目数。"""
        n = 0
        if self.trash.exists():
            for p in self.trash.iterdir():
                if p.is_dir():
                    shutil.rmtree(p)
                    n += 1
        return n

    def makedirs(self, rel: str) -> None:
        """建空目录（含父目录）。"""
        p = self._resolve(rel)
        p.mkdir(parents=True, exist_ok=True)

    def abspath(self, rel: str) -> Path:
        """相对路径 → 已校验的绝对路径（供下载等读操作用）。"""
        return self._resolve(rel)

    def cleanup_empty_dirs(self, rel: str) -> None:
        """删除 rel 所在文件/目录后，从其父目录递归向上删空目录（到 assets 根停）。

        用于删 md 后清理残留的空 nf/version/domain/scenario 目录，避免目录树出现
        空层。不会删除 assets 根本身。
        """
        p = self._resolve(rel)
        root = self._root_resolved
        parent = p.parent
        while parent != root and root in parent.parents:
            try:
                next(parent.iterdir())  # 非空 → 立即停
                return
            except StopIteration:
                parent.rmdir()  # 空 → 删，继续向上
                parent = parent.parent

    def list_md(self) -> list:
        """返回所有 md 文件相对 assets 根的归一化路径（正斜杠）。"""
        return [
            str(p.relative_to(self.root)).replace("\\", "/")
            for p in self.root.rglob("*.md")
        ]

    def list_children(self, rel: str = "") -> list:
        """列 rel 目录的直接子项（目录在前、文件在后，各自字母序）。

        返回 ``[{name, path, is_dir, size}]``，path 为相对 assets 根的归一化路径
        （正斜杠）。rel="" 表示 assets 根。文件浏览器目录树懒加载用。跳过隐藏文件。
        """
        d = self._resolve(rel) if rel else self.root
        if not d.exists() or not d.is_dir():
            return []
        items = []
        for p in sorted(d.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if p.name.startswith("."):
                continue
            items.append({
                "name": p.name,
                "path": str(p.relative_to(self.root)).replace("\\", "/"),
                "is_dir": p.is_dir(),
                "size": p.stat().st_size if p.is_file() else 0,
            })
        return items
