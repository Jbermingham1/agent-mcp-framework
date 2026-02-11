"""Shared test fixtures."""

import pytest

from agent_mcp_framework.agent import Agent, AgentContext, AgentResult


class EchoAgent(Agent):
    """Test agent that echoes input."""

    async def run(self, context: AgentContext) -> AgentResult:
        data = context.get("input", "")
        context.set("echo", data)
        return AgentResult(success=True, output=data)


class FailingAgent(Agent):
    """Test agent that always fails."""

    async def run(self, context: AgentContext) -> AgentResult:
        raise ValueError("Intentional failure")


class SlowAgent(Agent):
    """Test agent with configurable delay."""

    def __init__(self, name: str, delay: float = 0.1, **kwargs):
        super().__init__(name, **kwargs)
        self.delay = delay

    async def run(self, context: AgentContext) -> AgentResult:
        import asyncio
        await asyncio.sleep(self.delay)
        return AgentResult(success=True, output=f"done after {self.delay}s")


class CounterAgent(Agent):
    """Test agent that increments a counter in context."""

    async def run(self, context: AgentContext) -> AgentResult:
        count = context.get("count", 0)
        count += 1
        context.set("count", count)
        return AgentResult(success=True, output=count)


class AccumulatorAgent(Agent):
    """Test agent that appends its name to a list in context."""

    async def run(self, context: AgentContext) -> AgentResult:
        order = context.get("order", [])
        order.append(self.name)
        context.set("order", order)
        return AgentResult(success=True, output=self.name)


@pytest.fixture
def echo_agent():
    return EchoAgent("echo", description="Echoes input")


@pytest.fixture
def failing_agent():
    return FailingAgent("failer", description="Always fails")


@pytest.fixture
def context():
    return AgentContext()


@pytest.fixture
def context_with_input():
    return AgentContext(data={"input": "hello world"})
