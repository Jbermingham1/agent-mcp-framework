"""Output formatting for agent results."""

from __future__ import annotations

import json
from typing import Any

from agent_mcp_framework.agent import AgentResult


def format_result(result: AgentResult, fmt: str = "json") -> str:
    """Format an agent result for output."""
    if fmt == "json":
        return _format_json(result)
    elif fmt == "markdown":
        return _format_markdown(result)
    elif fmt == "text":
        return _format_text(result)
    else:
        raise ValueError(f"Unknown format: {fmt}. Valid: json, markdown, text")


def _format_json(result: AgentResult) -> str:
    data = {
        "success": result.success,
        "agent": result.agent_name,
        "duration_ms": round(result.duration_ms, 2),
    }
    if result.output is not None:
        data["output"] = result.output
    if result.error:
        data["error"] = result.error
    if result.metadata:
        data["metadata"] = result.metadata
    return json.dumps(data, indent=2, default=str)


def _format_markdown(result: AgentResult) -> str:
    icon = "+" if result.success else "x"
    lines = [
        f"## [{icon}] {result.agent_name}",
        f"**Duration:** {result.duration_ms:.0f}ms",
        "",
    ]
    if result.output is not None:
        output = result.output
        if isinstance(output, (dict, list)):
            output = json.dumps(output, indent=2, default=str)
        lines.append(f"```\n{output}\n```")
    if result.error:
        lines.append(f"**Error:** {result.error}")
    return "\n".join(lines)


def _format_text(result: AgentResult) -> str:
    status = "OK" if result.success else "FAIL"
    parts = [f"[{status}] {result.agent_name} ({result.duration_ms:.0f}ms)"]
    if result.output is not None:
        parts.append(str(result.output))
    if result.error:
        parts.append(f"Error: {result.error}")
    return "\n".join(parts)
