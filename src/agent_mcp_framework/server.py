"""MCP Server that exposes agent pipelines as tools."""

from __future__ import annotations

import inspect
import json
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from agent_mcp_framework.agent import Agent, AgentContext
from agent_mcp_framework.formatters import format_result
from agent_mcp_framework.pipeline import Pipeline, PipelineResult


class AgentMCPServer:
    """Wraps agent pipelines as MCP tools served over stdio/SSE.

    Example:
        server = AgentMCPServer("my-server", description="Code analysis tools")
        server.add_agent_tool(
            my_agent,
            name="analyze",
            description="Analyze code quality",
            parameters={"code": str},
        )
        server.run()
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._mcp = FastMCP(name)
        self._agents: dict[str, Agent] = {}
        self._pipelines: dict[str, Pipeline] = {}

    def add_agent_tool(
        self,
        agent: Agent,
        name: str | None = None,
        description: str | None = None,
        *,
        parameters: dict[str, type],
        context_mapper: Callable[[dict[str, Any]], AgentContext] | None = None,
        output_format: str = "json",
    ) -> AgentMCPServer:
        """Register an agent as an MCP tool.

        Args:
            agent: The agent to expose as a tool.
            name: Tool name (defaults to agent.name).
            description: Tool description (defaults to agent.description).
            parameters: The tool's inputs as {param_name: type}. This becomes
                the JSON schema MCP clients see, so every input the agent reads
                from context must be declared here.
            context_mapper: Function to convert tool params into an AgentContext.
            output_format: How to format the result ("json", "markdown", "text").
        """
        tool_name = name or agent.name
        tool_desc = description or agent.description
        self._agents[tool_name] = agent
        mapper = context_mapper or _default_context_mapper

        async def _handle(params: dict[str, Any]) -> str:
            ctx = mapper(params)
            result = await agent.execute(ctx)
            return format_result(result, output_format)

        self._mcp.add_tool(
            _typed_tool_handler(parameters, _handle),
            name=tool_name,
            description=tool_desc,
        )
        return self

    def add_pipeline_tool(
        self,
        pipeline: Pipeline,
        name: str | None = None,
        description: str = "",
        *,
        parameters: dict[str, type],
        context_mapper: Callable[[dict[str, Any]], AgentContext] | None = None,
        output_format: str = "json",
    ) -> AgentMCPServer:
        """Register a pipeline as an MCP tool.

        Args:
            pipeline: The pipeline to expose as a tool.
            name: Tool name (defaults to pipeline.name).
            description: Tool description.
            parameters: The tool's inputs as {param_name: type} — the JSON
                schema MCP clients see.
            context_mapper: Function to convert tool params into an AgentContext.
            output_format: How to format the result ("json", "markdown", "text").
        """
        tool_name = name or pipeline.name
        self._pipelines[tool_name] = pipeline

        mapper = context_mapper or _default_context_mapper

        async def _handle(params: dict[str, Any]) -> str:
            ctx = mapper(params)
            result = await pipeline.execute(ctx)
            return format_pipeline_result(result, output_format)

        self._mcp.add_tool(
            _typed_tool_handler(parameters, _handle),
            name=tool_name,
            description=description,
        )
        return self

    def run(self, transport: str = "stdio") -> None:
        """Start the MCP server."""
        self._mcp.run(transport=transport)

    async def run_async(self, transport: str = "stdio") -> None:
        """Start the MCP server asynchronously."""
        if transport == "stdio":
            await self._mcp.run_stdio_async()
        elif transport == "sse":
            await self._mcp.run_sse_async()
        else:
            raise ValueError(f"Unknown transport: {transport}")


def _default_context_mapper(params: dict[str, Any]) -> AgentContext:
    """Default mapping: put all params into context.data."""
    return AgentContext(data=params)


def _typed_tool_handler(
    parameters: dict[str, type],
    handle: Callable[[dict[str, Any]], Any],
) -> Callable[..., Any]:
    """Build a tool handler whose signature declares `parameters` explicitly.

    FastMCP generates each tool's input schema by inspecting the handler's
    signature. A bare `**kwargs` handler advertises a single opaque required
    argument named "kwargs" instead of the tool's real inputs — arguments then
    never reach the agents. Setting `__signature__` makes the declared
    parameters the schema clients see, and FastMCP validates calls against it.
    """

    async def tool_handler(**kwargs):
        return await handle(kwargs)

    tool_handler.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        parameters=[
            inspect.Parameter(pname, inspect.Parameter.KEYWORD_ONLY, annotation=ptype)
            for pname, ptype in parameters.items()
        ],
    )
    tool_handler.__annotations__ = dict(parameters)
    return tool_handler


def format_pipeline_result(result: PipelineResult, fmt: str = "json") -> str:
    """Format a pipeline result for MCP output."""
    if fmt == "json":
        return json.dumps(
            {
                "success": result.success,
                "pipeline": result.pipeline_name,
                "duration_ms": round(result.duration_ms, 2),
                "results": [
                    {
                        "agent": r.agent_name,
                        "success": r.success,
                        "output": r.output,
                        "error": r.error,
                        "duration_ms": round(r.duration_ms, 2),
                    }
                    for r in result.results
                ],
            },
            indent=2,
            default=str,
        )
    elif fmt == "markdown":
        lines = [f"## Pipeline: {result.pipeline_name}"]
        lines.append(f"**Status:** {'Success' if result.success else 'Failed'}")
        lines.append(f"**Duration:** {result.duration_ms:.0f}ms\n")
        for r in result.results:
            icon = "+" if r.success else "x"
            lines.append(f"### [{icon}] {r.agent_name} ({r.duration_ms:.0f}ms)")
            if r.output is not None:
                lines.append(f"```\n{r.output}\n```")
            if r.error:
                lines.append(f"**Error:** {r.error}")
            lines.append("")
        return "\n".join(lines)
    else:
        parts = [f"Pipeline '{result.pipeline_name}': {'OK' if result.success else 'FAILED'}"]
        for r in result.results:
            status = "OK" if r.success else "FAIL"
            parts.append(f"  [{status}] {r.agent_name}: {r.output or r.error}")
        return "\n".join(parts)
