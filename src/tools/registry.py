from __future__ import annotations
import time
from agent.models import SessionState
from tools.base import Tool, ToolResult


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def get_tools_for_names(self, names: list[str]) -> list[Tool]:
        return [self._tools[n] for n in names if n in self._tools]

    def get_openai_tool_schemas(self, names: list[str]) -> list[dict]:
        schemas = []
        for tool in self.get_tools_for_names(names):
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            })
        return schemas

    async def execute(self, name: str, params: dict, session: SessionState | None) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult(status="error", output=f"Unknown tool: {name}")
        start = time.monotonic()
        try:
            result = await tool.execute(params, session)
            result.latency_ms = (time.monotonic() - start) * 1000
            return result
        except Exception as e:
            return ToolResult(
                status="error",
                output=str(e),
                latency_ms=(time.monotonic() - start) * 1000,
            )
