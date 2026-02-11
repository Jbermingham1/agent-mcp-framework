"""Example: Multi-agent code review MCP server.

This demonstrates building a production-ready multi-agent system that:
1. Analyzes code for quality issues
2. Checks for security vulnerabilities
3. Reviews architecture patterns
4. Produces a scored report

Run as MCP server:
    agent-mcp serve examples.code_review_server

Or run the pipeline directly:
    agent-mcp run examples.code_review_server -i '{"code": "import os; os.system(input())"}'
"""

from agent_mcp_framework import (
    Agent,
    AgentContext,
    AgentMCPServer,
    AgentResult,
    ParallelPipeline,
    SequentialPipeline,
)


class QualityAnalyzer(Agent):
    """Checks code quality metrics."""

    async def run(self, context: AgentContext) -> AgentResult:
        code = context.get("code", "")
        lines = code.splitlines()
        issues = []

        if len(lines) > 500:
            issues.append({"severity": "warning", "message": "File exceeds 500 lines"})
        if any("import *" in line for line in lines):
            issues.append({"severity": "error", "message": "Wildcard imports detected"})
        if any(len(line) > 120 for line in lines):
            issues.append({"severity": "info", "message": "Lines exceed 120 chars"})
        has_docstring = any(
            line.strip().startswith('"""') or line.strip().startswith("'''")
            for line in lines
        )
        if not has_docstring:
            issues.append({"severity": "info", "message": "No docstrings found"})

        context.set("quality_issues", issues)
        return AgentResult(
            success=True,
            output={"issues": issues, "count": len(issues)},
        )


class SecurityScanner(Agent):
    """Checks for common security issues."""

    PATTERNS = [
        ("eval(", "Use of eval() — potential code injection"),
        ("exec(", "Use of exec() — potential code injection"),
        ("os.system(", "Use of os.system() — potential command injection"),
        ("subprocess.call(", "Use of subprocess.call with shell=True risk"),
        ("pickle.loads(", "Deserialization of untrusted data"),
        ("__import__(", "Dynamic import — potential security risk"),
        ("password", "Potential hardcoded credentials"),
        ("secret", "Potential hardcoded secrets"),
    ]

    async def run(self, context: AgentContext) -> AgentResult:
        code = context.get("code", "")
        findings = []

        for pattern, message in self.PATTERNS:
            if pattern in code.lower():
                findings.append({"severity": "critical", "message": message, "pattern": pattern})

        context.set("security_findings", findings)
        return AgentResult(
            success=True,
            output={"findings": findings, "count": len(findings)},
        )


class ArchitectureReviewer(Agent):
    """Reviews architectural patterns and best practices."""

    async def run(self, context: AgentContext) -> AgentResult:
        code = context.get("code", "")
        observations = []

        if "class " in code:
            class_count = code.count("class ")
            if class_count > 5:
                observations.append("Multiple classes in one file — consider splitting")
        if code.count("def ") > 20:
            observations.append("Many functions — consider modularizing")
        if "global " in code:
            observations.append("Global state detected — consider dependency injection")
        if code.count("try:") > 10:
            observations.append("Many try/except blocks — consider structured error handling")

        context.set("architecture_notes", observations)
        return AgentResult(
            success=True,
            output={"observations": observations, "count": len(observations)},
        )


class ReportGenerator(Agent):
    """Combines all analysis into a final scored report."""

    async def run(self, context: AgentContext) -> AgentResult:
        quality = context.get("quality_issues", [])
        security = context.get("security_findings", [])
        architecture = context.get("architecture_notes", [])

        # Score calculation
        score = 100
        for issue in quality:
            score -= {"error": 15, "warning": 10, "info": 3}.get(issue.get("severity", "info"), 5)
        for finding in security:
            score -= {"critical": 25, "high": 15, "medium": 10}.get(
                finding.get("severity", "medium"), 10
            )
        score -= len(architecture) * 5
        score = max(0, score)

        grade = "A" if score >= 90 else "B" if score >= 70 else "C" if score >= 50 else "F"

        report = {
            "score": score,
            "grade": grade,
            "quality": {"count": len(quality), "issues": quality},
            "security": {"count": len(security), "findings": security},
            "architecture": {"count": len(architecture), "notes": architecture},
        }

        return AgentResult(success=True, output=report)


# Build the pipeline: analyze in parallel, then generate report
analysis_pipeline = ParallelPipeline(
    "analysis",
    agents=[
        QualityAnalyzer("quality", description="Code quality analysis"),
        SecurityScanner("security", description="Security vulnerability scan"),
        ArchitectureReviewer("architecture", description="Architecture review"),
    ],
)

report_pipeline = SequentialPipeline(
    "report",
    agents=[ReportGenerator("reporter", description="Generate scored report")],
)


# Combined pipeline for CLI usage
class PipelineRunner(Agent):
    """Runs the analysis pipeline then generates a report."""

    async def run(self, context: AgentContext) -> AgentResult:
        await analysis_pipeline.execute(context)
        result = await report_pipeline.execute(context)
        if result.results:
            return result.results[0]
        return AgentResult(success=False, error="No report")


pipeline = SequentialPipeline("code-review", agents=[PipelineRunner("runner")])

# MCP Server
server = AgentMCPServer("code-review", description="Multi-agent code review server")

server.add_pipeline_tool(
    SequentialPipeline("review", agents=[PipelineRunner("runner")]),
    name="review_code",
    description="Analyze code for quality, security, and architecture issues.",
)

if __name__ == "__main__":
    server.run()
