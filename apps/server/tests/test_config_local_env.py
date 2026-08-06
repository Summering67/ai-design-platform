from pathlib import Path

from ai_design_server.config import load_config


def test_local_env_fills_empty_yaml_values(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
database:
  dsn: postgresql://localhost/test
ai:
  base_url: ""
  api_key: ""
auth:
  fixed_user_password: ""
""",
        encoding="utf-8",
    )
    env_path = tmp_path / ".env.local"
    env_path.write_text(
        "DS_BASE_URL=https://local.example\nDS_API_KEY=local-key\nAPI_AUTH_FIXED_USER_PASSWORD=local-password\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("API_CONFIG_FILE", str(config_path))
    monkeypatch.setenv("API_LOCAL_ENV_FILE", str(env_path))
    config = load_config()
    assert config.ai.base_url == "https://local.example"
    assert config.ai.api_key == "local-key"
    assert config.auth.fixed_user_password == "local-password"
