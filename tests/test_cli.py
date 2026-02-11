"""Tests for CLI module."""

import pytest
from click.testing import CliRunner

from agent_mcp_framework.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestCLI:
    def test_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_info(self, runner):
        result = runner.invoke(main, ["info"])
        assert result.exit_code == 0
        assert "agent-mcp-framework" in result.output
        assert "Sequential" in result.output

    def test_serve_missing_module(self, runner):
        result = runner.invoke(main, ["serve", "nonexistent.module"])
        assert result.exit_code == 1
        assert "Could not import" in result.output

    def test_run_missing_module(self, runner):
        result = runner.invoke(main, ["run", "nonexistent.module"])
        assert result.exit_code == 1
        assert "Could not import" in result.output

    def test_run_invalid_json(self, runner):
        # Create a temp module with a pipeline
        import sys
        import types
        mod = types.ModuleType("_test_pipeline_mod")
        from agent_mcp_framework.pipeline import SequentialPipeline

        from .conftest import CounterAgent
        mod.pipeline = SequentialPipeline("test", agents=[CounterAgent("c")])
        sys.modules["_test_pipeline_mod"] = mod

        result = runner.invoke(main, ["run", "_test_pipeline_mod", "-i", "not-json"])
        assert result.exit_code == 1
        assert "Invalid JSON" in result.output

        del sys.modules["_test_pipeline_mod"]

    def test_run_valid_pipeline(self, runner):
        import sys
        import types
        mod = types.ModuleType("_test_pipeline_mod2")
        from agent_mcp_framework.pipeline import SequentialPipeline

        from .conftest import CounterAgent
        mod.pipeline = SequentialPipeline("test", agents=[CounterAgent("c")])
        sys.modules["_test_pipeline_mod2"] = mod

        result = runner.invoke(main, ["run", "_test_pipeline_mod2"])
        assert result.exit_code == 0
        assert "test" in result.output

        del sys.modules["_test_pipeline_mod2"]

    def test_serve_no_server_attr(self, runner):
        import sys
        import types
        mod = types.ModuleType("_test_no_server")
        sys.modules["_test_no_server"] = mod

        result = runner.invoke(main, ["serve", "_test_no_server"])
        assert result.exit_code == 1
        assert "no 'server' attribute" in result.output

        del sys.modules["_test_no_server"]

    def test_run_no_pipeline_attr(self, runner):
        import sys
        import types
        mod = types.ModuleType("_test_no_pipeline")
        sys.modules["_test_no_pipeline"] = mod

        result = runner.invoke(main, ["run", "_test_no_pipeline"])
        assert result.exit_code == 1
        assert "no 'pipeline' attribute" in result.output

        del sys.modules["_test_no_pipeline"]
