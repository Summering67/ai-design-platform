import pytest
from sqlalchemy import Text

from ai_design_server.database import AttemptModel, MessageModel, _async_dsn


@pytest.mark.parametrize("dsn", [
    "postgres://user:password@127.0.0.1:5432/aidp",
    "postgresql://user:password@127.0.0.1:5432/aidp",
])
def test_async_dsn_matches_go_postgres_formats(dsn: str) -> None:
    assert _async_dsn(dsn).startswith("postgresql+psycopg://")


def test_async_dsn_rejects_malformed_value() -> None:
    with pytest.raises(ValueError, match="数据库 DSN"):
        _async_dsn("postgresql://invalid value")


def test_models_map_authoritative_postgres_constraints() -> None:
    assert isinstance(MessageModel.__table__.c.role.type, Text)
    assert isinstance(AttemptModel.__table__.c.status.type, Text)
    assert {constraint.name for constraint in MessageModel.__table__.constraints} >= {
        "messages_role_check",
        "messages_content_check",
        "messages_project_id_client_message_id_key",
    }
    assert {index.name for index in AttemptModel.__table__.indexes} >= {
        "generation_attempts_one_running_project_idx",
        "generation_attempts_user_message_idx",
    }
