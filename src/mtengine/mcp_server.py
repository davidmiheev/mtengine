"""MCP server exposing the engine's functions as tools (stdio transport).

Register with an MCP client, e.g. in Claude Code's .mcp.json:
  {"mcpServers": {"mtengine": {"command": "<venv>/bin/mtengine-mcp"}}}
Long computations: call job_submit, then poll job_status.
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from . import api

server = MCPServer(
    name="mtengine",
    version=api.core.__version__,
    instructions=("Computational engine for torus actions, matroids and GKM theory, plus "
                  "low-dimensional topology via Regina (triangulations as isomorphism signatures). "
                  "Results come "
                  "with provenance (backend version, input hash, time) and are cached. For anything "
                  "slow use job_submit + job_status."),
)
for _name, _fn in api.FUNCTIONS.items():
    server.add_tool(_fn, name=_name)


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
