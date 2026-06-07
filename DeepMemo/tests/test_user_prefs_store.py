from tools.utils.user_prefs_store import load_user_prefs, save_user_prefs


def test_user_prefs_save_and_load_roundtrip():
    prefs = load_user_prefs()
    prefs["language"] = "en"
    prefs["daily_limit"] = 12
    save_user_prefs(prefs)

    loaded = load_user_prefs()
    assert loaded["language"] == "en"
    assert loaded["daily_limit"] == 12


