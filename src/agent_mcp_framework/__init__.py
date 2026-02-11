"""agent-mcp-framework: Build multi-agent MCP servers in Python."""

from agent_mcp_framework.agent import Agent, AgentContext, AgentResult
from agent_mcp_framework.pipeline import Pipeline, SequentialPipeline, ParallelPipeline, ConditionalPipeline
from agent_mcp_framework.server import AgentMCPServer

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "AgentContext",
    "AgentResult",
    "Pipeline",
    "SequentialPipeline",
    "ParallelPipeline",
    "ConditionalPipeline",
    "AgentMCPServer",
]
