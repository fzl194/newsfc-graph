from app.classify import classify
from app.registry import Registry

R = Registry.load_default()

def test_nf_command():
    rel, fname = classify("UDG@MMLCommand@ADD URR", R, {"version": "20.15.2"})
    assert fname == "UDG@MMLCommand@ADD URR.md"
    assert rel == "Command/UDG/20.15.2"

def test_nf_configobject():
    rel, fname = classify("UDG@ConfigObject@URR", R, {"version": "20.15.2"})
    assert rel == "ConfigObject/UDG/20.15.2"
    assert fname == "UDG@ConfigObject@URR.md"

def test_business_domain():
    rel, fname = classify("BusinessDomain@demo", R, {"domain": "demo-domain"})
    assert rel == "Business/demo-domain"
    assert fname == "BusinessDomain@demo.md"

def test_business_scenario():
    rel, fname = classify("NetworkScenario@demo", R, {"domain": "demo-domain", "scenario": "demo"})
    assert rel == "Business/demo-domain/demo"

def test_business_solution():
    rel, fname = classify("ConfigurationSolution@demo-online", R, {"domain": "demo-domain", "scenario": "demo"})
    assert rel == "Business/demo-domain/demo"
    assert fname == "ConfigurationSolution@demo-online.md"

def test_missing_version_raises():
    import pytest
    with pytest.raises(ValueError):
        classify("UDG@MMLCommand@ADD URR", R, {})  # NF 类缺 version

def test_task_types_use_type_name_dir_without_version():
    # Task 层去版本：路径 {type}/{nf}/（type 名做顶层，非 layer 名 "Task"）；无 version 段
    for tid in ("UDG@AtomTask@ADD URR", "UDG@CompoundTask@charging-trio",
                "UDG@FeatureTask@GWFD-020301"):
        rel, fname = classify(tid, R, {})
        typ = tid.split("@")[1]
        assert rel == f"{typ}/UDG"
        assert fname == f"{tid}.md"
