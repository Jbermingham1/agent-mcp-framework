"""agent-mcp-framework: Build multi-agent MCP servers in Python."""

from agent_mcp_framework.agent import (
    Agent,
    AgentContext,
    AgentResult,
    FunctionAgent,
    LLMAgent,
)
from agent_mcp_framework.pipeline import (
    ConditionalPipeline,
    MapReducePipeline,
    ParallelPipeline,
    Pipeline,
    PipelineResult,
    SequentialPipeline,
)
from agent_mcp_framework.server import AgentMCPServer

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "AgentContext",
    "AgentResult",
    "AgentMCPServer",
    "ConditionalPipeline",
    "FunctionAgent",
    "LLMAgent",
    "MapReducePipeline",
    "ParallelPipeline",
    "Pipeline",
    "PipelineResult",
    "SequentialPipeline",
]
