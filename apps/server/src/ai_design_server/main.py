from __future__ import annotations

from math import ceil

import uvicorn

from .app import create_app
from .config import RuntimeConfig, load_config

app = create_app()


def _server_endpoint(address: str) -> tuple[str, int]:
    host, _, port = address.strip().rpartition(":")
    return host.strip("[]") or "0.0.0.0", int(port)


def run() -> None:
    config: RuntimeConfig = load_config()
    host, port = _server_endpoint(config.server.address)
    uvicorn.run(
        create_app(config),
        host=host,
        port=port,
        timeout_keep_alive=ceil(config.server.idle_timeout),
        timeout_graceful_shutdown=ceil(config.server.shutdown_timeout),
    )


if __name__ == "__main__":
    run()
