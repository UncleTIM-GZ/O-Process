"""O'Process MCP Server — FastMCP entry point.

Run:
    python -m oprocess.server                  # stdio (default)
    python -m oprocess.server --transport sse  # SSE on port 8000
    python -m oprocess.server --transport sse --port 9000
"""

from __future__ import annotations

import argparse
import logging
import os

from fastmcp import FastMCP
from mcp.types import Icon

from oprocess.config import get_config
from oprocess.prompts import register_prompts
from oprocess.tools.rate_limit import RateLimitMiddleware
from oprocess.tools.registry import register_tools
from oprocess.tools.resources import register_resources


def _configure_logging() -> None:
    """Configure structured logging from LOG_LEVEL env var."""
    level_name = os.environ.get("LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    oprocess_logger = logging.getLogger("oprocess")
    oprocess_logger.setLevel(level)
    if not oprocess_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(name)s %(levelname)s %(message)s",
            ),
        )
        oprocess_logger.addHandler(handler)


_configure_logging()

# Blue gradient circle with white 3-level process tree (64x64 SVG)
_ICON_DATA_URI = (
    "data:image/svg+xml;base64,"
    "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIg"
    "aGVpZ2h0PSI2NCIgdmlld0JveD0iMCAwIDY0IDY0Ij4KICA8ZGVmcz4KICAgIDxsaW5l"
    "YXJHcmFkaWVudCBpZD0iYmciIHgxPSIwIiB5MT0iMCIgeDI9IjAiIHkyPSIxIj4KICAg"
    "ICAgPHN0b3Agb2Zmc2V0PSIwJSIgc3RvcC1jb2xvcj0iIzNCODJGNiIvPgogICAgICA8"
    "c3RvcCBvZmZzZXQ9IjEwMCUiIHN0b3AtY29sb3I9IiMxRDRFRDgiLz4KICAgIDwvbGlu"
    "ZWFyR3JhZGllbnQ+CiAgPC9kZWZzPgogIDxjaXJjbGUgY3g9IjMyIiBjeT0iMzIiIHI9"
    "IjMwIiBmaWxsPSJ1cmwoI2JnKSIvPgogIDxsaW5lIHgxPSIzMiIgeTE9IjE4IiB4Mj0i"
    "MjAiIHkyPSIyNyIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIxLjUiIG9wYWNp"
    "dHk9IjAuODUiLz4KICA8bGluZSB4MT0iMzIiIHkxPSIxOCIgeDI9IjQ0IiB5Mj0iMjci"
    "IHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMS41IiBvcGFjaXR5PSIwLjg1Ii8+"
    "CiAgPGxpbmUgeDE9IjIwIiB5MT0iMzMiIHgyPSIxNCIgeTI9IjQxIiBzdHJva2U9Indo"
    "aXRlIiBzdHJva2Utd2lkdGg9IjEuMiIgb3BhY2l0eT0iMC42NSIvPgogIDxsaW5lIHgx"
    "PSIyMCIgeTE9IjMzIiB4Mj0iMjYiIHkyPSI0MSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tl"
    "LXdpZHRoPSIxLjIiIG9wYWNpdHk9IjAuNjUiLz4KICA8bGluZSB4MT0iNDQiIHkxPSIz"
    "MyIgeDI9IjM4IiB5Mj0iNDEiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMS4y"
    "IiBvcGFjaXR5PSIwLjY1Ii8+CiAgPGxpbmUgeDE9IjQ0IiB5MT0iMzMiIHgyPSI1MCIg"
    "eTI9IjQxIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjEuMiIgb3BhY2l0eT0i"
    "MC42NSIvPgogIDxjaXJjbGUgY3g9IjMyIiBjeT0iMTQiIHI9IjQiIGZpbGw9IndoaXRl"
    "Ii8+CiAgPGNpcmNsZSBjeD0iMjAiIGN5PSIzMCIgcj0iMy41IiBmaWxsPSJ3aGl0ZSIv"
    "PgogIDxjaXJjbGUgY3g9IjQ0IiBjeT0iMzAiIHI9IjMuNSIgZmlsbD0id2hpdGUiLz4K"
    "ICA8Y2lyY2xlIGN4PSIxNCIgY3k9IjQ0IiByPSIzIiBmaWxsPSJ3aGl0ZSIgb3BhY2l0"
    "eT0iMC44Ii8+CiAgPGNpcmNsZSBjeD0iMjYiIGN5PSI0NCIgcj0iMyIgZmlsbD0id2hp"
    "dGUiIG9wYWNpdHk9IjAuOCIvPgogIDxjaXJjbGUgY3g9IjM4IiBjeT0iNDQiIHI9IjMi"
    "IGZpbGw9IndoaXRlIiBvcGFjaXR5PSIwLjgiLz4KICA8Y2lyY2xlIGN4PSI1MCIgY3k9"
    "IjQ0IiByPSIzIiBmaWxsPSJ3aGl0ZSIgb3BhY2l0eT0iMC44Ii8+Cjwvc3ZnPgo="
)

mcp = FastMCP(
    "O'Process",
    version="0.3.0",
    instructions="AI-native process classification framework (OPF). "
    "Query 2325 processes + 3910 KPIs from APQC PCF 7.4 + ITIL 4 + SCOR 12.0.",
    icons=[Icon(src=_ICON_DATA_URI, mimeType="image/svg+xml")],
)

_cfg = get_config()
mcp.add_middleware(RateLimitMiddleware(
    max_calls=int(_cfg["rate_limit_max_calls"]),
    window_seconds=int(_cfg["rate_limit_window_seconds"]),
))
register_tools(mcp)
register_resources(mcp)
register_prompts(mcp)

_VALID_TRANSPORTS = ("stdio", "sse", "streamable-http")


def main() -> None:
    """Parse CLI args and start MCP server."""
    parser = argparse.ArgumentParser(description="O'Process MCP Server")
    parser.add_argument(
        "--transport",
        choices=_VALID_TRANSPORTS,
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for SSE/HTTP (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE/HTTP (default: 8000)",
    )
    args = parser.parse_args()

    kwargs: dict = {}
    if args.transport != "stdio":
        kwargs["host"] = args.host
        kwargs["port"] = args.port

        from starlette.middleware import Middleware

        from oprocess.auth import BearerAuthMiddleware

        kwargs["middleware"] = [Middleware(BearerAuthMiddleware)]

    mcp.run(transport=args.transport, **kwargs)


if __name__ == "__main__":
    main()
