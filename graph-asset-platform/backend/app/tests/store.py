"""tests 资产库读写：在 <data>/tests/ 下读写。

与图谱 app/store.py 同样的路径穿越防护，但根目录不同、代码独立。任何逃逸
tests 根的路径都抛 ValueError。
"""
import shutil
from pathlib import Path


class TestStore:
    def __init__(self, tests_dir: Path):
        self.root = Path(tests_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self._root_resolved = self.root.resolve()

    def _resolve(self, rel: str) -> Path:
        """相对路径 → 绝对路径，校验未逃逸 tests 根。"""
        rel_path = rel.replace("\\", "/")
        if rel_path.startswith("/"):
            raise ValueError(f"非法路径（绝对路径）: {rel}")
        p = (self.root / rel_path).resolve()
        root = self._root_resolved
        if p != root and root not in p.parents:
            raise ValueError(f"非法路径（逃逸 tests 根）: {rel}")
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
        p = self._resolve(rel)
        if p.exists():
            p.unlink()
            return True
        return False

    def move(self, src_rel: str, dst_rel: str) -> None:
        """移动文件/目录（用例改域/场景时移动整个用例文件夹）。"""
        src = self._resolve(src_rel)
        dst = self._resolve(dst_rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

    def rmtree(self, rel: str) -> bool:
        """删除整个目录（删用例/运行文件夹）。"""
        p = self._resolve(rel)
        if p.exists() and p.is_dir():
            shutil.rmtree(p)
            return True
        return False

    def abspath(self, rel: str) -> Path:
        """相对路径 → 已校验的绝对路径（供下载 zip 等读操作用）。"""
        return self._resolve(rel)

    def list_md(self) -> list:
        """所有 md 文件相对 tests 根的归一化路径（正斜杠）。"""
        return [
            str(p.relative_to(self.root)).replace("\\", "/")
            for p in self.root.rglob("*.md")
        ]

    def list_files(self, rel_dir: str) -> list:
        """某目录下直接子文件名（不含子目录）。用于列 Run 产出文件。"""
        d = self._resolve(rel_dir)
        if not d.exists() or not d.is_dir():
            return []
        return sorted(p.name for p in d.iterdir() if p.is_file())
