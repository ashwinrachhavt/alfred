from alfred_app.core.config import Settings


def test_settings_defaults_without_env():
    # Avoid reading any .env files during this test
    s = Settings(_env_file=None)

    assert s.app_env == "dev"
    assert s.redis_url.startswith("redis://")

