"""CLI interface for running agent-mcp-framework servers and pipelines."""

from __future__ import annotations

import asyncio
import importlib
import sys

import click
from rich.console import Console
from rich.table import Table

from agent_mcp_framework import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def main():
    """agent-mcp-framework: Build multi-agent MCP servers in Python."""
    pass


@main.command()
@click.argument("module_path")
@click.option("--transport", "-t", default="stdio", type=click.Choice(["stdio", "sse"]))
def serve(module_path: str, transport: str):
    """Start an MCP server from a Python module.

    MODULE_PATH should be a dotted path to a module containing an AgentMCPServer
    instance named 'server' (e.g., 'my_project.server').
    """
    try:
        mod = importlib.import_module(module_path)
    except ImportError as e:
        console.print(f"[red]Error:[/red] Could not import '{module_path}': {e}")
        sys.exit(1)

    server = getattr(mod, "server", None)
    if server is None:
        console.print(
            f"[red]Error:[/red] Module '{module_path}' has no 'server' attribute. "
            "Define an AgentMCPServer instance named 'server'."
        )
        sys.exit(1)

    console.print(f"[green]Starting MCP server[/green] '{server.name}' via {transport}")
    server.run(transport=transport)


@main.command()
@click.argument("module_path")
@click.option("--input", "-i", "input_data", default=None, help="JSON input data")
@click.option(
    "--format", "-f", "output_format",
    default="text",
    type=click.Choice(["json", "markdown", "text"]),
)
def run(module_path: str, input_data: str | None, output_format: str):
    """Run a pipeline directly from a Python module.

    MODULE_PATH should be a dotted path to a module containing a Pipeline
    instance named 'pipeline' (e.g., 'my_project.pipeline').
    """
    import json as json_mod

    from agent_mcp_framework.agent import AgentContext
    from agent_mcp_framework.server import format_pipeline_result

    try:
        mod = importlib.import_module(module_path)
    except ImportError as e:
        console.print(f"[red]Error:[/red] Could not import '{module_path}': {e}")
        sys.exit(1)

    pipeline = getattr(mod, "pipeline", None)
    if pipeline is None:
        console.print(
            f"[red]Error:[/red] Module '{module_path}' has no 'pipeline' attribute."
        )
        sys.exit(1)

    ctx = AgentContext()
    if input_data:
        try:
            ctx.data = json_mod.loads(input_data)
        except json_mod.JSONDecodeError as e:
            console.print(f"[red]Error:[/red] Invalid JSON input: {e}")
            sys.exit(1)

    result = asyncio.run(pipeline.execute(ctx))
    output = format_pipeline_result(result, output_format)
    console.print(output)

    if not result.success:
        sys.exit(1)


@main.command()
def info():
    """Show framework version and capabilities."""
    table = Table(title="agent-mcp-framework")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Version", __version__)
    table.add_row("Agents", "Agent, LLMAgent, FunctionAgent")
    table.add_row("Pipelines", "Sequential, Parallel, Conditional, MapReduce")
    table.add_row("Transports", "stdio, SSE")
    table.add_row("Output Formats", "JSON, Markdown, Text")

    console.print(table)


if __name__ == "__main__":
    main()
