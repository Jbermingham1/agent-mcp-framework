"""Pipeline composition patterns for multi-agent workflows."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Callable

from pydantic import BaseModel, Field

from agent_mcp_framework.agent import Agent, AgentContext, AgentResult


class PipelineResult(BaseModel):
    """Aggregated result from a pipeline execution."""

    success: bool
    results: list[AgentResult] = Field(default_factory=list)
    duration_ms: float = 0.0
    pipeline_name: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def failed(self) -> list[AgentResult]:
        return [r for r in self.results if not r.success]

    @property
    def outputs(self) -> dict[str, Any]:
        return {r.agent_name: r.output for r in self.results}


class Pipeline(ABC):
    """Base class for agent composition patterns."""

    def __init__(self, name: str, agents: list[Agent] | None = None):
        self.name = name
        self.agents: list[Agent] = agents or []

    def add(self, agent: Agent) -> Pipeline:
        """Add an agent to the pipeline."""
        self.agents.append(agent)
        return self

    @abstractmethod
    async def execute(self, context: AgentContext | None = None) -> PipelineResult:
        """Execute the pipeline. Must be implemented by subclasses."""
        ...


class SequentialPipeline(Pipeline):
    """Execute agents one after another. Each agent sees the updated context.

    If `stop_on_failure` is True (default), the pipeline stops when any agent fails.
    """

    def __init__(
        self, name: str, agents: list[Agent] | None = None, stop_on_failure: bool = True
    ):
        super().__init__(name, agents)
        self.stop_on_failure = stop_on_failure

    async def execute(self, context: AgentContext | None = None) -> PipelineResult:
        ctx = context or AgentContext()
        results: list[AgentResult] = []
        start = time.monotonic()

        for agent in self.agents:
            result = await agent.execute(ctx)
            results.append(result)
            if not result.success and self.stop_on_failure:
                break

        duration = (time.monotonic() - start) * 1000
        all_ok = all(r.success for r in results)
        return PipelineResult(
            success=all_ok,
            results=results,
            duration_ms=duration,
            pipeline_name=self.name,
        )


class ParallelPipeline(Pipeline):
    """Execute agents concurrently with isolated contexts.

    Each agent receives a snapshot of the input context to prevent race
    conditions on shared mutable state. After all agents complete, their
    contexts are merged back into the original.

    If `max_concurrency` is set, limits how many agents run simultaneously.
    """

    def __init__(
        self,
        name: str,
        agents: list[Agent] | None = None,
        max_concurrency: int | None = None,
    ):
        super().__init__(name, agents)
        self.max_concurrency = max_concurrency

    async def execute(self, context: AgentContext | None = None) -> PipelineResult:
        ctx = context or AgentContext()
        start = time.monotonic()

        # Each agent gets an isolated copy to prevent race conditions
        snapshots = [ctx.model_copy(deep=True) for _ in self.agents]

        if self.max_concurrency:
            sem = asyncio.Semaphore(self.max_concurrency)

            async def run_with_sem(agent: Agent, snap: AgentContext) -> AgentResult:
                async with sem:
                    return await agent.execute(snap)

            results = await asyncio.gather(
                *[run_with_sem(a, s) for a, s in zip(self.agents, snapshots)]
            )
        else:
            results = await asyncio.gather(
                *[a.execute(s) for a, s in zip(self.agents, snapshots)]
            )

        # Merge snapshot data back into the original context
        for snap in snapshots:
            ctx.data.update(snap.data)
            ctx.metadata.update(snap.metadata)
            ctx.errors.extend(e for e in snap.errors if e not in ctx.errors)

        results = list(results)
        duration = (time.monotonic() - start) * 1000
        all_ok = all(r.success for r in results)
        return PipelineResult(
            success=all_ok,
            results=results,
            duration_ms=duration,
            pipeline_name=self.name,
        )


class ConditionalPipeline(Pipeline):
    """Route to different agents based on a condition function.

    The `router` function receives the context and returns the name of the
    agent to execute, or None to skip.
    """

    def __init__(
        self,
        name: str,
        agents: list[Agent] | None = None,
        router: Callable[[AgentContext], str | None] = None,
    ):
        super().__init__(name, agents)
        self.router = router

    def _agent_map(self) -> dict[str, Agent]:
        return {a.name: a for a in self.agents}

    async def execute(self, context: AgentContext | None = None) -> PipelineResult:
        ctx = context or AgentContext()
        start = time.monotonic()

        if self.router is None:
            raise ValueError("ConditionalPipeline requires a router function")

        target_name = self.router(ctx)
        results: list[AgentResult] = []

        if target_name is not None:
            agent_map = self._agent_map()
            if target_name not in agent_map:
                raise ValueError(
                    f"Router returned '{target_name}' but no agent with that name exists. "
                    f"Available: {list(agent_map.keys())}"
                )
            result = await agent_map[target_name].execute(ctx)
            results.append(result)

        duration = (time.monotonic() - start) * 1000
        all_ok = all(r.success for r in results) if results else True
        return PipelineResult(
            success=all_ok,
            results=results,
            duration_ms=duration,
            pipeline_name=self.name,
        )


class MapReducePipeline(Pipeline):
    """Fan-out work across agents, then reduce results.

    The `splitter` function breaks the context into N sub-contexts (one per agent).
    The `reducer` function combines all results into the final context.
    """

    def __init__(
        self,
        name: str,
        agents: list[Agent] | None = None,
        splitter: Callable[[AgentContext], list[AgentContext]] | None = None,
        reducer: Callable[[list[AgentResult], AgentContext], None] | None = None,
    ):
        super().__init__(name, agents)
        self.splitter = splitter
        self.reducer = reducer

    async def execute(self, context: AgentContext | None = None) -> PipelineResult:
        ctx = context or AgentContext()
        start = time.monotonic()

        if self.splitter is None:
            raise ValueError("MapReducePipeline requires a splitter function")

        sub_contexts = self.splitter(ctx)

        if len(sub_contexts) != len(self.agents):
            raise ValueError(
                f"Splitter returned {len(sub_contexts)} contexts but pipeline "
                f"has {len(self.agents)} agents"
            )

        results = await asyncio.gather(
            *[agent.execute(sub_ctx) for agent, sub_ctx in zip(self.agents, sub_contexts)]
        )
        results = list(results)

        if self.reducer:
            self.reducer(results, ctx)

        duration = (time.monotonic() - start) * 1000
        all_ok = all(r.success for r in results)
        return PipelineResult(
            success=all_ok,
            results=results,
            duration_ms=duration,
            pipeline_name=self.name,
        )
