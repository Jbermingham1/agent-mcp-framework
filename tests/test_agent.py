"""Tests for agent module."""

import asyncio

import pytest

from agent_mcp_framework.agent import (
    Agent,
    AgentContext,
    AgentResult,
    AgentStatus,
    FunctionAgent,
    LLMAgent,
)

from .conftest import EchoAgent, FailingAgent


class TestAgentContext:
    def test_get_set(self):
        ctx = AgentContext()
        ctx.set("key", "value")
        assert ctx.get("key") == "value"

    def test_get_default(self):
        ctx = AgentContext()
        assert ctx.get("missing") is None
        assert ctx.get("missing", 42) == 42

    def test_merge(self):
        ctx1 = AgentContext(data={"a": 1}, metadata={"m1": True})
        ctx2 = AgentContext(data={"b": 2}, metadata={"m2": True})
        merged = ctx1.merge(ctx2)
        assert merged.get("a") == 1
        assert merged.get("b") == 2
        assert merged.metadata["m1"] is True
        assert merged.metadata["m2"] is True

    def test_merge_override(self):
        ctx1 = AgentContext(data={"a": 1})
        ctx2 = AgentContext(data={"a": 2})
        merged = ctx1.merge(ctx2)
        assert merged.get("a") == 2

    def test_merge_errors(self):
        ctx1 = AgentContext(errors=["err1"])
        ctx2 = AgentContext(errors=["err2"])
        merged = ctx1.merge(ctx2)
        assert merged.errors == ["err1", "err2"]

    def test_empty_context(self):
        ctx = AgentContext()
        assert ctx.data == {}
        assert ctx.metadata == {}
        assert ctx.errors == []


class TestAgentResult:
    def test_success_result(self):
        r = AgentResult(success=True, output="done", agent_name="test")
        assert r.success is True
        assert r.output == "done"
        assert r.error is None

    def test_failure_result(self):
        r = AgentResult(success=False, error="bad", agent_name="test")
        assert r.success is False
        assert r.error == "bad"

    def test_metadata(self):
        r = AgentResult(success=True, metadata={"key": "val"})
        assert r.metadata["key"] == "val"


class TestAgent:
    @pytest.mark.asyncio
    async def test_execute_success(self, echo_agent, context_with_input):
        result = await echo_agent.execute(context_with_input)
        assert result.success is True
        assert result.output == "hello world"
        assert result.agent_name == "echo"
        assert result.duration_ms > 0
        assert echo_agent.status == AgentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_failure(self, failing_agent, context):
        result = await failing_agent.execute(context)
        assert result.success is False
        assert "Intentional failure" in result.error
        assert failing_agent.status == AgentStatus.FAILED
        assert len(context.errors) == 1

    @pytest.mark.asyncio
    async def test_context_mutation(self, echo_agent, context_with_input):
        await echo_agent.execute(context_with_input)
        assert context_with_input.get("echo") == "hello world"

    @pytest.mark.asyncio
    async def test_before_hook(self, echo_agent, context_with_input):
        called = []
        echo_agent.on("before_run", lambda agent, context: called.append("before"))
        await echo_agent.execute(context_with_input)
        assert "before" in called

    @pytest.mark.asyncio
    async def test_after_hook(self, echo_agent, context_with_input):
        results = []
        echo_agent.on("after_run", lambda agent, context, result: results.append(result))
        await echo_agent.execute(context_with_input)
        assert len(results) == 1
        assert results[0].success is True

    @pytest.mark.asyncio
    async def test_error_hook(self, failing_agent, context):
        errors = []
        failing_agent.on("on_error", lambda agent, context, error: errors.append(str(error)))
        await failing_agent.execute(context)
        assert len(errors) == 1
        assert "Intentional failure" in errors[0]

    @pytest.mark.asyncio
    async def test_hook_chaining(self):
        agent = EchoAgent("test")
        result = agent.on("before_run", lambda **kw: None)
        assert result is agent  # Returns self for chaining

    def test_invalid_hook_event(self, echo_agent):
        with pytest.raises(ValueError, match="Unknown event"):
            echo_agent.on("invalid_event", lambda: None)

    @pytest.mark.asyncio
    async def test_initial_status(self):
        agent = EchoAgent("test")
        assert agent.status == AgentStatus.IDLE

    @pytest.mark.asyncio
    async def test_async_hook(self, echo_agent, context_with_input):
        called = []

        async def async_hook(agent, context):
            await asyncio.sleep(0.01)
            called.append("async")

        echo_agent.on("before_run", async_hook)
        await echo_agent.execute(context_with_input)
        assert "async" in called


class TestFunctionAgent:
    @pytest.mark.asyncio
    async def test_sync_function(self):
        def my_fn(ctx):
            return AgentResult(success=True, output="sync")

        agent = FunctionAgent("sync-fn", fn=my_fn)
        result = await agent.execute(AgentContext())
        assert result.success is True
        assert result.output == "sync"

    @pytest.mark.asyncio
    async def test_async_function(self):
        async def my_fn(ctx):
            return AgentResult(success=True, output="async")

        agent = FunctionAgent("async-fn", fn=my_fn)
        result = await agent.execute(AgentContext())
        assert result.success is True
        assert result.output == "async"

    @pytest.mark.asyncio
    async def test_raw_return(self):
        def my_fn(ctx):
            return 42

        agent = FunctionAgent("raw", fn=my_fn)
        result = await agent.execute(AgentContext())
        assert result.success is True
        assert result.output == 42

    @pytest.mark.asyncio
    async def test_function_error(self):
        def my_fn(ctx):
            raise RuntimeError("oops")

        agent = FunctionAgent("error-fn", fn=my_fn)
        result = await agent.execute(AgentContext())
        assert result.success is False
        assert "oops" in result.error

    @pytest.mark.asyncio
    async def test_default_description(self):
        def my_fn(ctx):
            return None

        agent = FunctionAgent("test", fn=my_fn)
        assert "my_fn" in agent.description


class TestLLMAgent:
    def test_model_defaults(self):
        class MyLLM(LLMAgent):
            async def run(self, ctx):
                return AgentResult(success=True)

        agent = MyLLM("test")
        assert agent.model == "claude-sonnet-4-5-20250929"
        assert agent.max_tokens == 4096

    def test_custom_model(self):
        class MyLLM(LLMAgent):
            async def run(self, ctx):
                return AgentResult(success=True)

        agent = MyLLM("test", model="claude-opus-4-6", max_tokens=8192)
        assert agent.model == "claude-opus-4-6"
        assert agent.max_tokens == 8192

    def test_system_prompt(self):
        class MyLLM(LLMAgent):
            async def run(self, ctx):
                return AgentResult(success=True)

        agent = MyLLM("test", system_prompt="You are helpful.")
        assert agent.system_prompt == "You are helpful."
