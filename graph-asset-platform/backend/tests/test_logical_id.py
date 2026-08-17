from app.logical_id import split_id, segment_count, is_nf_scoped

def test_nf_3seg():
    assert split_id("UDG@MMLCommand@ADD URR") == ("UDG", "MMLCommand", "ADD URR")
    assert segment_count("UDG@MMLCommand@ADD URR") == 3
    assert is_nf_scoped("UDG@MMLCommand@ADD URR") is True

def test_cross_2seg():
    assert split_id("NetworkScenario@demo") == (None, "NetworkScenario", "demo")
    assert segment_count("NetworkScenario@demo") == 2
    assert is_nf_scoped("NetworkScenario@demo") is False

def test_command_name_keeps_space():
    nf, typ, local = split_id("UDG@MMLCommand@ACT LICCTL")
    assert local == "ACT LICCTL"   # 空格保留，@ 不在 local 内
