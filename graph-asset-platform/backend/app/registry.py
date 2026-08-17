import yaml
from pathlib import Path
from typing import Optional

class Registry:
    def __init__(self, types: dict):
        self._t = types  # {TypeName: {layer,scope,...}}

    @classmethod
    def load_default(cls, path: Optional[Path] = None) -> "Registry":
        from app.config import DEFAULT_REGISTRY_PATH
        path = path or DEFAULT_REGISTRY_PATH
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(data.get("object_types", {}))

    def get(self, type_name: str) -> Optional[dict]:
        return self._t.get(type_name)

    def layer_of(self, type_name: str) -> Optional[str]:
        e = self.get(type_name)
        return e["layer"] if e else None

    def merge_extensions(self, ext: dict) -> list:
        """bundle 扩展覆盖默认；返回告警列表。"""
        warnings = []
        for name, spec in (ext or {}).items():
            if name in self._t:
                warnings.append(f"类型 {name} 被 bundle 扩展覆盖")
            self._t[name] = spec
        return warnings

    def known(self, type_name: str) -> bool:
        return type_name in self._t

    def types_in_layer(self, layer: str) -> list:
        """该 layer 下所有 type 名（如 ``'Task'`` → ``[Task, AtomTask, CompoundTask, FeatureTask]``）。"""
        return [name for name, e in self._t.items() if e.get("layer") == layer]
