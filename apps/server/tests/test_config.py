from ai_design_server import config as config_module
from ai_design_server.config import RuntimeConfig


def test_runtime_config_accepts_shared_runtime_values() -> None:
    config = RuntimeConfig.model_validate(
        {
            "database": {"dsn": "postgresql://localhost/aidp"},
            "ai": {"base_url": "https://ai.test", "api_key": "test-key"},
            "auth": {"fixed_user_password": "test-password"},
        }
    )
    assert config.server.address == ":8081"


def test_load_config_reads_server_env_file(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "API_DATABASE_DSN='host=127.0.0.1 user=wd dbname=ai_design_platform'\n"
        "API_AI_BASE_URL=https://ai.test\n"
        "API_AI_API_KEY=test-key\n"
        "API_AUTH_FIXED_USER_PASSWORD=test-password\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "_server_env_path", lambda: env_file)
    monkeypatch.setenv("API_CONFIG_FILE", "off")
    for key in ("API_DATABASE_DSN", "API_AI_BASE_URL", "API_AI_API_KEY", "API_AUTH_FIXED_USER_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    loaded = config_module.load_config()
    assert loaded.database.dsn.startswith("host=127.0.0.1")
