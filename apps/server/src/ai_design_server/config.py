from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class _EnvOverrides(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="API_", extra="ignore")

    server_address: str | None = None
    server_read_timeout: str | None = None
    server_write_timeout: str | None = None
    server_idle_timeout: str | None = None
    server_shutdown_timeout: str | None = None
    database_dsn: str | None = None
    database_max_open_conns: int | None = None
    database_max_idle_conns: int | None = None
    database_conn_max_lifetime: str | None = None
    database_ping_timeout: str | None = None
    log_environment: str | None = None
    log_level: str | None = None
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    ai_model: str | None = None
    ai_request_timeout: str | None = None
    agent_node_timeout: str | None = None
    agent_total_timeout: str | None = None
    agent_max_input_bytes: int | None = None
    agent_max_output_bytes: int | None = None
    agent_max_pages: int | None = None
    agent_max_nodes: int | None = None
    agent_max_depth: int | None = None
    agent_max_tasks: int | None = None
    agent_max_task_depth: int | None = None
    agent_max_concurrency: int | None = None
    agent_max_retries: int | None = None
    auth_fixed_user_password: str | None = None


class ServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: str = ":8081"
    read_timeout: float = 5.0
    write_timeout: float = 75.0
    idle_timeout: float = 60.0
    shutdown_timeout: float = 10.0


class DatabaseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dsn: str = ""
    max_open_conns: int = 20
    max_idle_conns: int = 10
    conn_max_lifetime: float = 1800.0
    ping_timeout: float = 3.0


class LogConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    environment: str = "development"
    level: str = "info"


class AIConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = ""
    api_key: str = ""
    model: str = "deepseek-v4-flash"
    request_timeout: float = 0.0


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_timeout: float = 0.0
    total_timeout: float = 0.0
    max_input_bytes: int = 512 * 1024
    max_output_bytes: int = 1024 * 1024
    max_pages: int = 20
    max_nodes: int = 500
    max_depth: int = 32
    max_tasks: int = 12
    max_task_depth: int = 4
    max_concurrency: int = 4
    max_retries: int = 1


class AuthConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixed_user_password: str = ""


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)

    @model_validator(mode="after")
    def validate_config(self) -> RuntimeConfig:
        if not _valid_address(self.server.address):
            raise ValueError("服务地址无效")
        if min(self.server.read_timeout, self.server.write_timeout, self.server.idle_timeout, self.server.shutdown_timeout) <= 0:
            raise ValueError("服务超时必须为正数")
        if not self.database.dsn.strip():
            raise ValueError("数据库 DSN 不能为空")
        if self.database.max_open_conns <= 0 or self.database.max_idle_conns <= 0:
            raise ValueError("数据库连接池大小必须为正数")
        if self.database.max_idle_conns > self.database.max_open_conns:
            raise ValueError("数据库最大空闲连接数不能超过最大打开连接数")
        if min(self.database.conn_max_lifetime, self.database.ping_timeout) <= 0:
            raise ValueError("数据库连接生命周期和 Ping 超时必须为正数")
        if self.log.environment not in {"development", "production"}:
            raise ValueError("日志环境必须为 development 或 production")
        if self.log.level.lower() not in {"debug", "info", "warning", "error", "critical"}:
            raise ValueError("日志级别无效")
        parsed = urlparse(self.ai.base_url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("AI BaseURL 必须是有效的 HTTP 地址")
        if not self.ai.api_key.strip() or not self.ai.model.strip() or self.ai.request_timeout < 0:
            raise ValueError("AI 配置无效")
        if not self.auth.fixed_user_password.strip():
            raise ValueError("固定用户密码不能为空")
        if self.ai.request_timeout > 0 and self.server.write_timeout <= self.ai.request_timeout:
            raise ValueError("HTTP 写超时必须大于 AI 请求超时")
        if min(self.agent.node_timeout, self.agent.total_timeout) < 0:
            raise ValueError("Agent 超时不能为负数")
        if self.agent.total_timeout > 0 and self.agent.node_timeout > self.agent.total_timeout:
            raise ValueError("Agent 总超时不能小于节点超时")
        if min(
            self.agent.max_input_bytes,
            self.agent.max_output_bytes,
            self.agent.max_pages,
            self.agent.max_nodes,
            self.agent.max_depth,
            self.agent.max_tasks,
            self.agent.max_task_depth,
            self.agent.max_concurrency,
        ) <= 0 or self.agent.max_retries < 0:
            raise ValueError("Agent 资源上限无效")
        return self


_DURATION = re.compile(r"^(?P<value>[0-9]+(?:\.[0-9]+)?)(?P<unit>ms|s|m|h)$")


def _duration(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    match = _DURATION.fullmatch(value.strip())
    if not match:
        return value
    amount = float(match.group("value"))
    return amount / 1000 if match.group("unit") == "ms" else amount * {"s": 1, "m": 60, "h": 3600}[match.group("unit")]


def _valid_address(address: str) -> bool:
    value = address.strip()
    if value.startswith(":"):
        port = value[1:]
    elif ":" in value:
        port = value.rsplit(":", 1)[-1]
    else:
        return False
    return port.isdigit() and 1 <= int(port) <= 65535


def _workspace_root() -> Path:
    current = Path.cwd().resolve()
    for directory in (current, *current.parents):
        if (directory / "pnpm-workspace.yaml").exists():
            return directory
    return current


def _server_env_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def _merge_nested(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_nested(target[key], value)
        elif value is not None:
            target[key] = value


def _yaml_values() -> dict[str, Any]:
    configured = os.getenv("API_CONFIG_FILE", "").strip()
    path = Path(configured) if configured else Path.cwd() / "config" / "config.yaml"
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise TypeError("配置文件必须是对象")
    return loaded


def load_config() -> RuntimeConfig:
    values: dict[str, Any] = {
        "server": {},
        "database": {},
        "log": {},
        "ai": {},
        "agent": {},
        "auth": {},
    }
    _merge_nested(values, _yaml_values())
    server_env = _parse_env_file(_server_env_path()) if _server_env_path().exists() else {}
    _apply_env_values(values, server_env)
    local_path = os.getenv("API_LOCAL_ENV_FILE", "").strip()
    if local_path != "off" and values["log"].get("environment", "development") == "development":
        candidate = Path(local_path) if local_path else _workspace_root() / ".env.local"
        if candidate.exists():
            local = _parse_env_file(candidate)
            _set_if_blank(values["ai"], "base_url", local.get("DS_BASE_URL", ""))
            _set_if_blank(values["ai"], "api_key", local.get("DS_API_KEY", ""))
            _set_if_blank(values["auth"], "fixed_user_password", local.get("API_AUTH_FIXED_USER_PASSWORD", ""))
    _apply_env_values(values, _EnvOverrides().model_dump(exclude_none=True))
    return RuntimeConfig.model_validate(_convert_durations(values))


def _set_if_blank(target: dict[str, Any], key: str, value: Any) -> None:
    if not str(target.get(key, "")).strip() and value is not None:
        target[key] = value


def _apply_env_values(values: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if value is None or not key.startswith("API_") and "_" not in key:
            continue
        normalized = key.removeprefix("API_").lower()
        if "_" not in normalized:
            continue
        section, field = normalized.split("_", 1)
        if section in values:
            values[section][field] = value


def _convert_durations(values: dict[str, Any]) -> dict[str, Any]:
    converted = {section: dict(fields) for section, fields in values.items()}
    for section, field_names in {
        "server": ("read_timeout", "write_timeout", "idle_timeout", "shutdown_timeout"),
        "database": ("conn_max_lifetime", "ping_timeout"),
        "ai": ("request_timeout",),
        "agent": ("node_timeout", "total_timeout"),
    }.items():
        for field in field_names:
            if field in converted[section] and converted[section][field] is not None:
                converted[section][field] = _duration(converted[section][field])
    return converted
