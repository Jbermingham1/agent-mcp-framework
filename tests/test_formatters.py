"""Tests for formatters module."""

import json

import pytest

from agent_mcp_framework.agent import AgentResult
from agent_mcp_framework.formatters import format_result


class TestJsonFormat:
    def test_success_result(self):
        r = AgentResult(success=True, output="data", agent_name="test", duration_ms=42.5)
        output = format_result(r, "json")
        parsed = json.loads(output)
        assert parsed["success"] is True
        assert parsed["output"] == "data"
        assert parsed["agent"] == "test"
        assert parsed["duration_ms"] == 42.5

    def test_failure_result(self):
        r = AgentResult(success=False, error="bad", agent_name="test")
        output = format_result(r, "json")
        parsed = json.loads(output)
        assert parsed["success"] is False
        assert parsed["error"] == "bad"

    def test_metadata_included(self):
        r = AgentResult(success=True, metadata={"k": "v"}, agent_name="test")
        output = format_result(r, "json")
        parsed = json.loads(output)
        assert parsed["metadata"]["k"] == "v"

    def test_no_output_excluded(self):
        r = AgentResult(success=True, agent_name="test")
        output = format_result(r, "json")
        parsed = json.loads(output)
        assert "output" not in parsed

    def test_dict_output(self):
        r = AgentResult(success=True, output={"a": 1, "b": [1, 2]}, agent_name="test")
        output = format_result(r, "json")
        parsed = json.loads(output)
        assert parsed["output"]["a"] == 1


class TestMarkdownFormat:
    def test_success_icon(self):
        r = AgentResult(success=True, agent_name="test", duration_ms=100)
        output = format_result(r, "markdown")
        assert "[+]" in output
        assert "test" in output
        assert "100ms" in output

    def test_failure_icon(self):
        r = AgentResult(success=False, error="bad", agent_name="test", duration_ms=50)
        output = format_result(r, "markdown")
        assert "[x]" in output
        assert "bad" in output

    def test_output_in_code_block(self):
        r = AgentResult(success=True, output="result data", agent_name="test")
        output = format_result(r, "markdown")
        assert "```" in output
        assert "result data" in output

    def test_dict_output_formatted(self):
        r = AgentResult(success=True, output={"key": "val"}, agent_name="test")
        output = format_result(r, "markdown")
        assert "key" in output


class TestTextFormat:
    def test_success(self):
        r = AgentResult(success=True, output="done", agent_name="test", duration_ms=25)
        output = format_result(r, "text")
        assert "[OK]" in output
        assert "test" in output
        assert "done" in output

    def test_failure(self):
        r = AgentResult(success=False, error="bad", agent_name="test", duration_ms=10)
        output = format_result(r, "text")
        assert "[FAIL]" in output
        assert "bad" in output

    def test_invalid_format(self):
        r = AgentResult(success=True)
        with pytest.raises(ValueError, match="Unknown format"):
            format_result(r, "xml")
