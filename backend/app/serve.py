"""Backend entrypoint that serves one app on two sockets.

The uvicorn CLI binds a single port, so this binds the main API port and the
remote MCP port itself and hands both sockets to one uvicorn server. Both
listeners then share a single lifespan, database engine and MCP session
manager. Pass --reload for the dev stack.
"""

from __future__ import annotations

import socket
import sys

import uvicorn

from .core.config import settings


def _bind(port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", port))
    return sock


def serve() -> None:
    server = uvicorn.Server(uvicorn.Config("app.main:app"))
    server.run(
        sockets=[
            _bind(settings.api_listen_port),
            _bind(settings.remote_mcp_listen_port),
        ]
    )


def main() -> None:
    if "--reload" in sys.argv[1:]:
        import watchfiles

        # Restarts serve() in a fresh process on every source change, which
        # mirrors what `uvicorn --reload` does for a single-port server.
        watchfiles.run_process("app", target=serve)
        return
    serve()


if __name__ == "__main__":
    main()
