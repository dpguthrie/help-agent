import pytest
from tools.base import Tool, ToolResult
from tools.registry import ToolRegistry


class FakeTool(Tool):
    name = "fake_tool"
    description = "A fake tool for testing"
    parameters = {"type": "object", "properties": {"x": {"type": "string"}}}

    async def execute(self, params, session):
        return ToolResult(status="ok", output={"echo": params["x"]})


def test_register_and_get():
    registry = ToolRegistry()
    tool = FakeTool()
    registry.register(tool)
    assert registry.get("fake_tool") is tool


def test_get_unknown_returns_none():
    registry = ToolRegistry()
    assert registry.get("nonexistent") is None


def test_get_tools_for_names():
    registry = ToolRegistry()
    registry.register(FakeTool())
    tools = registry.get_tools_for_names(["fake_tool", "nonexistent"])
    assert len(tools) == 1
    assert tools[0].name == "fake_tool"


def test_get_openai_tool_schemas():
    registry = ToolRegistry()
    registry.register(FakeTool())
    schemas = registry.get_openai_tool_schemas(["fake_tool"])
    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "fake_tool"


@pytest.mark.asyncio
async def test_execute_tool():
    registry = ToolRegistry()
    registry.register(FakeTool())
    result = await registry.execute("fake_tool", {"x": "hello"}, session=None)
    assert result.status == "ok"
    assert result.output["echo"] == "hello"


@pytest.mark.asyncio
async def test_execute_unknown_tool():
    registry = ToolRegistry()
    result = await registry.execute("nonexistent", {}, session=None)
    assert result.status == "error"
