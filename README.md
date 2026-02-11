# agent-mcp-framework

A Python framework for building multi-agent MCP (Model Context Protocol) servers.

Build production-ready multi-agent systems that expose their capabilities as MCP tools — ready to integrate with Claude, VSCode, and any MCP-compatible client.

## Features

- **Agent abstractions** — `Agent`, `LLMAgent`, `FunctionAgent` with lifecycle hooks
- **Pipeline composition** — Sequential, Parallel, Conditional, and MapReduce patterns
- **MCP integration** — Expose agent pipelines as MCP tools over stdio or SSE
- **Output formatting** — JSON, Markdown, and plain text output modes
- **CLI** — Run servers and pipelines from the command line

## Installation

```bash
pip install agent-mcp-framework
```

## Quick Start

```python
from agent_mcp_framework import Agent, AgentContext, AgentResult, SequentialPipeline, AgentMCPServer


class AnalyzerAgent(Agent):
    async def run(self, context: AgentContext) -> AgentResult:
        code = context.get("code", "")
        issues = []
        if len(code.splitlines()) > 500:
            issues.append("File exceeds 500 lines — consider splitting")
        if "import *" in code:
            issues.append("Wildcard imports detected")
        context.set("issues", issues)
        return AgentResult(success=True, output={"issues": issues, "count": len(issues)})


class ScorerAgent(Agent):
    async def run(self, context: AgentContext) -> AgentResult:
        issues = context.get("issues", [])
        score = max(0, 100 - len(issues) * 15)
        return AgentResult(success=True, output={"score": score, "grade": "A" if score >= 90 else "B" if score >= 70 else "C"})


# Compose agents into a pipeline
pipeline = SequentialPipeline("code-review", agents=[
    AnalyzerAgent("analyzer", description="Find code issues"),
    ScorerAgent("scorer", description="Score code quality"),
])

# Expose as an MCP server
server = AgentMCPServer("code-review-server", description="Multi-agent code review")
server.add_pipeline_tool(
    pipeline,
    name="review_code",
    description="Analyze code quality and return a score",
    parameters={"code": str},
)

if __name__ == "__main__":
    server.run()  # Starts MCP server on stdio
```

## Agent Types

### `Agent` — Base class
Implement `run()` to define your agent's logic.

### `LLMAgent` — Claude-powered agent
Built-in Anthropic client with `complete()` helper for LLM calls.

### `FunctionAgent` — Quick inline agents
Wrap any async function as an agent without subclassing.

## Pipeline Patterns

| Pattern | Description |
|---------|-------------|
| `SequentialPipeline` | Run agents one after another, each seeing updated context |
| `ParallelPipeline` | Run agents concurrently with optional concurrency limits |
| `ConditionalPipeline` | Route to agents based on a condition function |
| `MapReducePipeline` | Split work, fan out, and reduce results |

## CLI

```bash
# Start an MCP server
agent-mcp serve my_project.server

# Run a pipeline directly
agent-mcp run my_project.pipeline --input '{"code": "import *"}'

# Show framework info
agent-mcp info
```

## License

MIT
