"""Minimal quickstart example showing core concepts.

Run:
    python examples/quickstart.py
"""

import asyncio

from agent_mcp_framework import Agent, AgentContext, AgentResult, SequentialPipeline


class GreeterAgent(Agent):
    async def run(self, context: AgentContext) -> AgentResult:
        name = context.get("name", "World")
        greeting = f"Hello, {name}!"
        context.set("greeting", greeting)
        return AgentResult(success=True, output=greeting)


class ShoutAgent(Agent):
    async def run(self, context: AgentContext) -> AgentResult:
        greeting = context.get("greeting", "")
        shouted = greeting.upper()
        return AgentResult(success=True, output=shouted)


async def main():
    pipeline = SequentialPipeline("greet-and-shout", agents=[
        GreeterAgent("greeter", description="Says hello"),
        ShoutAgent("shouter", description="Makes it loud"),
    ])

    ctx = AgentContext(data={"name": "Developer"})
    result = await pipeline.execute(ctx)

    print(f"Pipeline: {result.pipeline_name}")
    print(f"Success: {result.success}")
    print(f"Duration: {result.duration_ms:.0f}ms")
    for r in result.results:
        print(f"  [{r.agent_name}] {r.output}")


if __name__ == "__main__":
    asyncio.run(main())
