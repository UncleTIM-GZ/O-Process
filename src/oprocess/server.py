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

mcp = FastMCP(
    "O'Process",
    version="0.3.0",
    instructions="AI-native process classification framework (OPF). "
    "Query 2325 processes + 3910 KPIs from APQC PCF 7.4 + ITIL 4 + SCOR 12.0.",
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
