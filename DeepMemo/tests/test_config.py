from tools.utils.config import DATABASE_FILE, CACHE_FILE, get_config_summary


def test_config_paths():
    summary = get_config_summary()
    assert str(DATABASE_FILE)
    assert str(CACHE_FILE)
    assert "api_backend_url" in summary


