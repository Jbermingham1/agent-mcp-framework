"""Core Agent abstraction for multi-agent systems."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentContext(BaseModel):
    """Shared context passed between agents in a pipeline."""

    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def merge(self, other: AgentContext) -> AgentContext:
        """Merge another context into this one, returning a new context."""
        merged_data = {**self.data, **other.data}
        merged_metadata = {**self.metadata, **other.metadata}
        merged_errors = self.errors + other.errors
        return AgentContext(data=merged_data, metadata=merged_metadata, errors=merged_errors)


class AgentResult(BaseModel):
    """Result returned by an agent after execution."""

    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    agent_name: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Agent(ABC):
    """Base class for all agents.

    Subclass this and implement `run()` to create an agent.

    Example:
        class MyAgent(Agent):
            async def run(self, context: AgentContext) -> AgentResult:
                data = context.get("input")
                result = process(data)
                context.set("output", result)
                return AgentResult(success=True, output=result, agent_name=self.name)
    """

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.status = AgentStatus.IDLE
        self._hooks: dict[str, list] = {
            "before_run": [],
            "after_run": [],
            "on_error": [],
        }

    def on(self, event: str, callback) -> Agent:
        """Register a lifecycle hook."""
        if event not in self._hooks:
            raise ValueError(f"Unknown event: {event}. Valid: {list(self._hooks.keys())}")
        self._hooks[event].append(callback)
        return self

    async def _fire(self, event: str, **kwargs) -> None:
        for cb in self._hooks.get(event, []):
            result = cb(**kwargs)
            if asyncio.iscoroutine(result):
                await result

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResult:
        """Execute the agent's logic. Must be implemented by subclasses."""
        ...

    async def execute(self, context: AgentContext) -> AgentResult:
        """Run the agent with lifecycle hooks and error handling."""
        self.status = AgentStatus.RUNNING
        start = time.monotonic()
        try:
            await self._fire("before_run", agent=self, context=context)
            result = await self.run(context)
            result.agent_name = self.name
            result.duration_ms = (time.monotonic() - start) * 1000
            self.status = AgentStatus.COMPLETED
            await self._fire("after_run", agent=self, context=context, result=result)
            return result
        except Exception as e:
            self.status = AgentStatus.FAILED
            duration = (time.monotonic() - start) * 1000
            error_result = AgentResult(
                success=False,
                error=str(e),
                agent_name=self.name,
                duration_ms=duration,
            )
            context.errors.append(f"{self.name}: {e}")
            await self._fire("on_error", agent=self, context=context, error=e)
            return error_result


class LLMAgent(Agent):
    """Agent that uses an LLM (Claude) for processing.

    Subclass this for agents that need LLM capabilities. Provides
    a configured Anthropic client and helper methods.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        model: str = "claude-sonnet-5",
        system_prompt: str = "",
        max_tokens: int = 4096,
    ):
        super().__init__(name, description)
        self.model = model
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic()
        return self._client

    async def complete(self, prompt: str, **kwargs) -> str:
        """Send a completion request to Claude."""
        messages = [{"role": "user", "content": prompt}]
        params = {
            "model": kwargs.pop("model", self.model),
            "max_tokens": kwargs.pop("max_tokens", self.max_tokens),
            "messages": messages,
            **kwargs,
        }
        if self.system_prompt:
            params["system"] = self.system_prompt
        response = await self.client.messages.create(**params)
        if not response.content:
            raise ValueError(
                f"Empty response from {params['model']} "
                f"(stop_reason: {response.stop_reason})"
            )
        return response.content[0].text


class FunctionAgent(Agent):
    """Agent created from a plain function.

    Example:
        async def analyze(ctx: AgentContext) -> AgentResult:
            data = ctx.get("input")
            return AgentResult(success=True, output=len(data))

        agent = FunctionAgent("counter", fn=analyze)
    """

    def __init__(self, name: str, fn, description: str = ""):
        super().__init__(name, description or f"Function agent: {fn.__name__}")
        self._fn = fn

    async def run(self, context: AgentContext) -> AgentResult:
        result = self._fn(context)
        if asyncio.iscoroutine(result):
            result = await result
        if isinstance(result, AgentResult):
            return result
        return AgentResult(success=True, output=result, agent_name=self.name)
