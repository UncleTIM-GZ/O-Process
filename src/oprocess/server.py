"""O'Process MCP Server — FastMCP entry point.

Run:
    python -m oprocess.server
    # or
    fastmcp run src/oprocess/server.py
"""

from __future__ import annotations

from fastmcp import FastMCP

from oprocess.tools.registry import register_tools

mcp = FastMCP(
    "O'Process",
    instructions="AI-native process classification framework (OPF). "
    "Query 2325 processes + 3910 KPIs from APQC PCF 7.4 + ITIL 4 + SCOR 12.0.",
)

register_tools(mcp)

if __name__ == "__main__":
    mcp.run()
