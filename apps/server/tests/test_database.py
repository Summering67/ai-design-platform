import pytest

from ai_design_server.database import _async_dsn


@pytest.mark.parametrize("dsn", [
    "postgres://user:password@127.0.0.1:5432/aidp",
    "postgresql://user:password@127.0.0.1:5432/aidp",
])
def test_async_dsn_matches_go_postgres_formats(dsn: str) -> None:
    assert _async_dsn(dsn).startswith("postgresql+psycopg://")


def test_async_dsn_rejects_malformed_value() -> None:
    with pytest.raises(ValueError, match="数据库 DSN"):
        _async_dsn("postgresql://invalid value")
