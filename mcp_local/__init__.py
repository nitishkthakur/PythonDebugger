"""Local stdio MCP tools adapter; no processes start on import."""
from .client import MCPClient, MCPError

__all__ = ["MCPClient", "MCPError"]
