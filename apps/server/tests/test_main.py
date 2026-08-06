from typing import Any

from ai_design_server import main
from ai_design_server.config import (
    AIConfig,
    AuthConfig,
    DatabaseConfig,
    RuntimeConfig,
    ServerConfig,
)


def _config(address: str = ":8081") -> RuntimeConfig:
    return RuntimeConfig(
        server=ServerConfig(address=address, idle_timeout=12.1, shutdown_timeout=4.2),
        database=DatabaseConfig(dsn="postgresql://localhost/aidp"),
        ai=AIConfig(base_url="https://ai.test", api_key="test-key"),
        auth=AuthConfig(fixed_user_password="test-password"),
    )


def test_server_endpoint_maps_wildcard_and_explicit_hosts() -> None:
    assert main._server_endpoint(":8081") == ("0.0.0.0", 8081)
    assert main._server_endpoint("127.0.0.1:9000") == ("127.0.0.1", 9000)
    assert main._server_endpoint("[::1]:9001") == ("::1", 9001)


def test_run_applies_runtime_server_config(monkeypatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(main, "load_config", lambda: _config("127.0.0.1:9000"))
    monkeypatch.setattr(
        main.uvicorn,
        "run",
        lambda application, **kwargs: captured.update(application=application, **kwargs),
    )

    main.run()

    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 9000
    assert captured["timeout_keep_alive"] == 13
    assert captured["timeout_graceful_shutdown"] == 5
