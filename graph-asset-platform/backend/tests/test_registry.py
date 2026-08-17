from app.registry import Registry
from app.config import DEFAULT_REGISTRY_PATH

def test_load_default():
    r = Registry.load_default()
    assert r.get("MMLCommand")["layer"] == "Command"
    assert r.get("MMLCommand")["scope"] == "nf"
    assert r.get("NetworkScenario")["path_fields"] == ["domain", "scenario"]

def test_layer_of_type():
    r = Registry.load_default()
    assert r.layer_of("MMLCommand") == "Command"
    assert r.layer_of("ConfigurationSolution") == "Business"

def test_merge_extension_overrides():
    r = Registry.load_default()
    r.merge_extensions({"MMLCommand": {"layer": "Command", "scope": "nf", "id_segments": 3, "frontmatter_required": ["id"]}})
    # 覆盖默认，不报错
    assert r.get("MMLCommand")["frontmatter_required"] == ["id"]

def test_unknown_type():
    r = Registry.load_default()
    assert r.get("Nope") is None
