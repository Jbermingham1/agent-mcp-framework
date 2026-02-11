"""Tests for MCP server module."""

import json

import pytest

from agent_mcp_framework.agent import AgentContext, AgentResult
from agent_mcp_framework.pipeline import PipelineResult, SequentialPipeline
from agent_mcp_framework.server import AgentMCPServer, format_pipeline_result

from .conftest import CounterAgent, EchoAgent


class TestAgentMCPServer:
    def test_create_server(self):
        server = AgentMCPServer("test", description="A test server")
        assert server.name == "test"
        assert server.description == "A test server"

    def test_add_agent_tool(self):
        server = AgentMCPServer("test")
        agent = EchoAgent("echo")
        result = server.add_agent_tool(agent, name="echo_tool", description="Echo input")
        assert result is server  # Returns self for chaining
        assert "echo_tool" in server._agents

    def test_add_pipeline_tool(self):
        server = AgentMCPServer("test")
        pipeline = SequentialPipeline("pipe", agents=[CounterAgent("c1")])
        result = server.add_pipeline_tool(
            pipeline, name="count", description="Count things"
        )
        assert result is server
        assert "count" in server._pipelines

    def test_chaining(self):
        server = AgentMCPServer("test")
        result = (
            server
            .add_agent_tool(EchoAgent("a"), name="tool_a", description="A")
            .add_agent_tool(EchoAgent("b"), name="tool_b", description="B")
        )
        assert result is server
        assert len(server._agents) == 2

    def test_default_agent_name(self):
        server = AgentMCPServer("test")
        agent = EchoAgent("my-echo", description="My echo agent")
        server.add_agent_tool(agent)
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
            context_mapper=mapper,
        )
        # The mapper itself works correctly
        ctx = mapper({"code": "hello"})
        assert ctx.get("input") == "hello"
