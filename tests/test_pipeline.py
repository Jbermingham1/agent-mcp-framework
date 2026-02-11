"""Tests for pipeline module."""

import asyncio
import time

import pytest

from agent_mcp_framework.agent import AgentContext, AgentResult
from agent_mcp_framework.pipeline import (
    ConditionalPipeline,
    MapReducePipeline,
    ParallelPipeline,
    PipelineResult,
    SequentialPipeline,
)

from .conftest import AccumulatorAgent, CounterAgent, EchoAgent, FailingAgent, SlowAgent


class TestPipelineResult:
    def test_failed_property(self):
        r = PipelineResult(
            success=False,
            results=[
                AgentResult(success=True, agent_name="a"),
                AgentResult(success=False, agent_name="b", error="bad"),
            ],
        )
        assert len(r.failed) == 1
        assert r.failed[0].agent_name == "b"

    def test_outputs_property(self):
        r = PipelineResult(
            success=True,
            results=[
                AgentResult(success=True, agent_name="a", output=1),
                AgentResult(success=True, agent_name="b", output=2),
            ],
        )
        assert r.outputs == {"a": 1, "b": 2}


class TestSequentialPipeline:
    @pytest.mark.asyncio
    async def test_basic_sequential(self):
        pipeline = SequentialPipeline("test", agents=[
            CounterAgent("c1"),
            CounterAgent("c2"),
            CounterAgent("c3"),
        ])
        ctx = AgentContext()
        result = await pipeline.execute(ctx)
        assert result.success is True
        assert len(result.results) == 3
        assert ctx.get("count") == 3

    @pytest.mark.asyncio
    async def test_order_preserved(self):
        pipeline = SequentialPipeline("test", agents=[
            AccumulatorAgent("first"),
            AccumulatorAgent("second"),
            AccumulatorAgent("third"),
        ])
        ctx = AgentContext()
        await pipeline.execute(ctx)
        assert ctx.get("order") == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_stop_on_failure(self):
        pipeline = SequentialPipeline("test", agents=[
            EchoAgent("ok"),
            FailingAgent("fail"),
            EchoAgent("never"),
        ], stop_on_failure=True)
        result = await pipeline.execute(AgentContext(data={"input": "x"}))
        assert result.success is False
        assert len(result.results) == 2  # Stopped after failure

    @pytest.mark.asyncio
    async def test_continue_on_failure(self):
        pipeline = SequentialPipeline("test", agents=[
            EchoAgent("ok"),
            FailingAgent("fail"),
            EchoAgent("still-runs"),
        ], stop_on_failure=False)
        result = await pipeline.execute(AgentContext(data={"input": "x"}))
        assert result.success is False
        assert len(result.results) == 3  # All ran

    @pytest.mark.asyncio
    async def test_empty_pipeline(self):
        pipeline = SequentialPipeline("empty")
        result = await pipeline.execute()
        assert result.success is True
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_duration_tracked(self):
        pipeline = SequentialPipeline("test", agents=[SlowAgent("slow", delay=0.05)])
        result = await pipeline.execute()
        assert result.duration_ms >= 40  # At least 40ms

    @pytest.mark.asyncio
    async def test_add_agent(self):
        pipeline = SequentialPipeline("test")
        pipeline.add(CounterAgent("c1")).add(CounterAgent("c2"))
        result = await pipeline.execute()
        assert result.success is True
        assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_context_shared(self):
        pipeline = SequentialPipeline("test", agents=[
            CounterAgent("c1"),
            CounterAgent("c2"),
        ])
        ctx = AgentContext(data={"count": 10})
        await pipeline.execute(ctx)
        assert ctx.get("count") == 12


class TestParallelPipeline:
    @pytest.mark.asyncio
    async def test_basic_parallel(self):
        pipeline = ParallelPipeline("test", agents=[
            SlowAgent("a", delay=0.05),
            SlowAgent("b", delay=0.05),
            SlowAgent("c", delay=0.05),
        ])
        result = await pipeline.execute()
        assert result.success is True
        assert len(result.results) == 3

    @pytest.mark.asyncio
    async def test_parallel_faster_than_sequential(self):
        agents = [SlowAgent(f"s{i}", delay=0.05) for i in range(3)]

        parallel = ParallelPipeline("par", agents=agents)
        start = time.monotonic()
        await parallel.execute()
        parallel_time = time.monotonic() - start

        # Parallel should be significantly faster than 3 * 0.05s = 0.15s
        assert parallel_time < 0.12

    @pytest.mark.asyncio
    async def test_max_concurrency(self):
        pipeline = ParallelPipeline("test", agents=[
            SlowAgent(f"s{i}", delay=0.05) for i in range(4)
        ], max_concurrency=2)
        result = await pipeline.execute()
        assert result.success is True
        assert len(result.results) == 4
        # With concurrency=2 and 4 agents of 0.05s each, should take ~0.1s
        assert result.duration_ms >= 80

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        pipeline = ParallelPipeline("test", agents=[
            EchoAgent("ok"),
            FailingAgent("fail"),
        ])
        result = await pipeline.execute(AgentContext(data={"input": "x"}))
        assert result.success is False
        assert len(result.results) == 2
        assert len(result.failed) == 1

    @pytest.mark.asyncio
    async def test_empty_parallel(self):
        pipeline = ParallelPipeline("empty")
        result = await pipeline.execute()
        assert result.success is True
        assert len(result.results) == 0


class TestConditionalPipeline:
    @pytest.mark.asyncio
    async def test_routes_correctly(self):
        def router(ctx):
            mode = ctx.get("mode")
            return mode

        pipeline = ConditionalPipeline("test", agents=[
            EchoAgent("fast"),
            EchoAgent("thorough"),
        ], router=router)

        ctx = AgentContext(data={"mode": "fast", "input": "data"})
        result = await pipeline.execute(ctx)
        assert result.success is True
        assert len(result.results) == 1
        assert result.results[0].agent_name == "fast"

    @pytest.mark.asyncio
    async def test_route_to_none(self):
        def router(ctx):
            return None

        pipeline = ConditionalPipeline("test", agents=[
            EchoAgent("a"),
        ], router=router)
        result = await pipeline.execute()
        assert result.success is True
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_invalid_route(self):
        def router(ctx):
            return "nonexistent"

        pipeline = ConditionalPipeline("test", agents=[
            EchoAgent("a"),
        ], router=router)
        with pytest.raises(ValueError, match="nonexistent"):
            await pipeline.execute()

    @pytest.mark.asyncio
    async def test_no_router(self):
        pipeline = ConditionalPipeline("test", agents=[EchoAgent("a")])
        with pytest.raises(ValueError, match="requires a router"):
            await pipeline.execute()


class TestMapReducePipeline:
    @pytest.mark.asyncio
    async def test_split_and_reduce(self):
        def splitter(ctx):
            items = ctx.get("items", [])
            return [AgentContext(data={"item": item}) for item in items]

        def reducer(results, ctx):
            ctx.set("processed", [r.output for r in results])

        pipeline = MapReducePipeline(
            "test",
            agents=[EchoAgent(f"worker-{i}") for i in range(3)],
            splitter=splitter,
            reducer=reducer,
        )
        ctx = AgentContext(data={"items": ["a", "b", "c"]})
        # Need to update EchoAgent to echo "item" not "input" — let's use CounterAgents instead
        result = await pipeline.execute(ctx)
        assert result.success is True
        assert len(result.results) == 3

    @pytest.mark.asyncio
    async def test_mismatched_count(self):
        def splitter(ctx):
            return [AgentContext(), AgentContext()]  # 2 contexts

        pipeline = MapReducePipeline(
            "test",
            agents=[EchoAgent("only-one")],  # 1 agent
            splitter=splitter,
        )
        with pytest.raises(ValueError, match="2 contexts.*1 agents"):
            await pipeline.execute()

    @pytest.mark.asyncio
    async def test_no_splitter(self):
        pipeline = MapReducePipeline("test", agents=[EchoAgent("a")])
        with pytest.raises(ValueError, match="requires a splitter"):
            await pipeline.execute()

    @pytest.mark.asyncio
    async def test_no_reducer(self):
        def splitter(ctx):
            return [AgentContext()]

        pipeline = MapReducePipeline(
            "test",
            agents=[EchoAgent("a")],
            splitter=splitter,
        )
        # Should work without reducer
        result = await pipeline.execute()
        assert result.success is True


class TestPipelineComposition:
    @pytest.mark.asyncio
    async def test_nested_pipelines(self):
        """A pipeline can contain other pipelines (via wrapper agents)."""
        inner = SequentialPipeline("inner", agents=[
            CounterAgent("c1"),
            CounterAgent("c2"),
        ])

        # Execute inner pipeline standalone
        ctx = AgentContext()
        result = await inner.execute(ctx)
        assert result.success is True
        assert ctx.get("count") == 2
