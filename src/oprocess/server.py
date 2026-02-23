"""O'Process MCP Server — FastMCP entry point.

Run:
    python -m oprocess.server                  # stdio (default)
    python -m oprocess.server --transport sse  # SSE on port 8000
    python -m oprocess.server --transport sse --port 9000
"""

from __future__ import annotations

import argparse

from fastmcp import FastMCP

from oprocess.tools.registry import register_tools
from oprocess.tools.resources import register_resources

mcp = FastMCP(
    "O'Process",
    instructions="AI-native process classification framework (OPF). "
    "Query 2325 processes + 3910 KPIs from APQC PCF 7.4 + ITIL 4 + SCOR 12.0.",
)

register_tools(mcp)
register_resources(mcp)

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

    mcp.run(transport=args.transport, **kwargs)


if __name__ == "__main__":
    main()
