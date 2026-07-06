"""Tests for MCP server module."""

import json

import pytest

from agent_mcp_framework.agent import Agent, AgentContext, AgentResult
from agent_mcp_framework.pipeline import PipelineResult, SequentialPipeline
from agent_mcp_framework.server import AgentMCPServer, format_pipeline_result

from .conftest import CounterAgent, EchoAgent


def _first_text(call_result):
    """Normalize FastMCP call_tool output to its first text payload.

    call_tool returns a content-block sequence, or a (content, structured)
    tuple / plain dict on some SDK versions.
    """
    if isinstance(call_result, tuple):
        call_result = call_result[0]
    if isinstance(call_result, dict):
        return json.dumps(call_result)
    return call_result[0].text


class TestAgentMCPServer:
    def test_create_server(self):
        server = AgentMCPServer("test", description="A test server")
        assert server.name == "test"
        assert server.description == "A test server"

    def test_add_agent_tool(self):
        server = AgentMCPServer("test")
        agent = EchoAgent("echo")
        result = server.add_agent_tool(
            agent, name="echo_tool", description="Echo input", parameters={"input": str}
        )
        assert result is server  # Returns self for chaining
        assert "echo_tool" in server._agents

    def test_add_pipeline_tool(self):
        server = AgentMCPServer("test")
        pipeline = SequentialPipeline("pipe", agents=[CounterAgent("c1")])
        result = server.add_pipeline_tool(
            pipeline, name="count", description="Count things", parameters={"count": int}
        )
        assert result is server
        assert "count" in server._pipelines

    def test_chaining(self):
        server = AgentMCPServer("test")
        result = (
            server
            .add_agent_tool(EchoAgent("a"), name="a", description="A", parameters={"input": str})
            .add_agent_tool(EchoAgent("b"), name="b", description="B", parameters={"input": str})
        )
        assert result is server
        assert len(server._agents) == 2

    def test_default_agent_name(self):
        server = AgentMCPServer("test")
        agent = EchoAgent("my-echo", description="My echo agent")
        server.add_agent_tool(agent, parameters={"input": str})
        assert "my-echo" in server._agents


class TestFormatPipelineResult:
    def _make_result(self, success=True):
        return PipelineResult(
            success=success,
            pipeline_name="test-pipe",
            duration_ms=150.7,
            results=[
                AgentResult(success=True, agent_name="agent1", output="out1", duration_ms=50.3),
                AgentResult(success=False, agent_name="agent2", error="err2", duration_ms=100.4),
            ],
        )

    def test_json_format(self):
        result = self._make_result(success=False)
        output = format_pipeline_result(result, "json")
        parsed = json.loads(output)
        assert parsed["success"] is False
        assert parsed["pipeline"] == "test-pipe"
        assert len(parsed["results"]) == 2
        assert parsed["results"][0]["agent"] == "agent1"
        assert parsed["results"][1]["error"] == "err2"

    def test_markdown_format(self):
        result = self._make_result()
        output = format_pipeline_result(result, "markdown")
        assert "test-pipe" in output
        assert "agent1" in output
        assert "agent2" in output
        assert "err2" in output

    def test_text_format(self):
        result = self._make_result()
        output = format_pipeline_result(result, "text")
        assert "test-pipe" in output
        assert "OK" in output or "FAIL" in output


class TestContextMapper:
    @pytest.mark.asyncio
    async def test_custom_context_mapper(self):
        def mapper(params):
            return AgentContext(data={"input": params.get("code", "")})

        server = AgentMCPServer("test")
        agent = EchoAgent("echo")
        server.add_agent_tool(
            agent,
            name="echo",
            description="Echo",
            parameters={"code": str},
            context_mapper=mapper,
        )
        # The mapper transforms tool params end-to-end through a real call
        result = await server._mcp.call_tool("echo", {"code": "hello"})
        payload = json.loads(_first_text(result))
        assert payload["output"] == "hello"


class TestMCPBoundary:
    """Tests that cross the real MCP layer: schema generation and tool calls.

    Registration-only tests once masked a bug where every tool advertised a
    single opaque required `kwargs` argument instead of its declared inputs,
    so client arguments never reached the agents.
    """

    def _echo_server(self):
        server = AgentMCPServer("test")
        server.add_agent_tool(
            EchoAgent("echo"),
            name="echo",
            description="Echo input",
            parameters={"input": str},
        )
        return server

    @pytest.mark.asyncio
    async def test_tool_schema_exposes_declared_parameters(self):
        server = self._echo_server()
        tools = await server._mcp.list_tools()
        tool = next(t for t in tools if t.name == "echo")
        props = tool.inputSchema.get("properties", {})
        assert "input" in props
        assert "kwargs" not in props
        assert "input" in tool.inputSchema.get("required", [])

    @pytest.mark.asyncio
    async def test_tool_call_reaches_agent_context(self):
        server = self._echo_server()
        result = await server._mcp.call_tool("echo", {"input": "hello mcp"})
        payload = json.loads(_first_text(result))
        assert payload["success"] is True
        assert payload["output"] == "hello mcp"

    @pytest.mark.asyncio
    async def test_pipeline_tool_input_changes_output(self):
        class WildcardAnalyzer(Agent):
            async def run(self, context: AgentContext) -> AgentResult:
                code = context.get("code", "")
                issues = 1 if "import *" in code else 0
                return AgentResult(success=True, output={"issues": issues})

        server = AgentMCPServer("review")
        server.add_pipeline_tool(
            SequentialPipeline("review", agents=[WildcardAnalyzer("analyzer")]),
            name="review_code",
            description="Analyze code",
            parameters={"code": str},
        )
        bad = json.loads(_first_text(
            await server._mcp.call_tool("review_code", {"code": "from os import *"})
        ))
        clean = json.loads(_first_text(
            await server._mcp.call_tool("review_code", {"code": "import os"})
        ))
        assert bad["results"][0]["output"]["issues"] == 1
        assert clean["results"][0]["output"]["issues"] == 0
