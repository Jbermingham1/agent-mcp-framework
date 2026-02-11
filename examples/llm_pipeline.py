"""Example: LLM-powered multi-agent pipeline.

This shows how to use LLMAgent with Claude for intelligent analysis.
Requires ANTHROPIC_API_KEY environment variable.

Run:
    python examples/llm_pipeline.py
"""

import asyncio

from agent_mcp_framework import AgentContext, AgentResult, SequentialPipeline
from agent_mcp_framework.agent import LLMAgent


class SummarizerAgent(LLMAgent):
    """Summarizes text content using Claude."""

    async def run(self, context: AgentContext) -> AgentResult:
        text = context.get("text", "")
        if not text:
            return AgentResult(success=False, error="No text provided")

        summary = await self.complete(
            f"Summarize this text in 2-3 sentences:\n\n{text}"
        )
        context.set("summary", summary)
        return AgentResult(success=True, output=summary)


class SentimentAgent(LLMAgent):
    """Analyzes sentiment of text using Claude."""

    async def run(self, context: AgentContext) -> AgentResult:
        text = context.get("text", "")
        if not text:
            return AgentResult(success=False, error="No text provided")

        analysis = await self.complete(
            f"Analyze the sentiment of this text. "
            f"Return one of: positive, negative, neutral, mixed.\n\n{text}"
        )
        context.set("sentiment", analysis.strip().lower())
        return AgentResult(success=True, output=analysis.strip())


class InsightsAgent(LLMAgent):
    """Generates insights combining summary and sentiment."""

    async def run(self, context: AgentContext) -> AgentResult:
        summary = context.get("summary", "")
        sentiment = context.get("sentiment", "")

        insights = await self.complete(
            f"Given this summary: {summary}\n"
            f"And this sentiment: {sentiment}\n\n"
            f"Provide 3 actionable insights in bullet points."
        )
        return AgentResult(success=True, output=insights)


pipeline = SequentialPipeline("text-analysis", agents=[
    SummarizerAgent("summarizer", system_prompt="You are a concise summarizer."),
    SentimentAgent("sentiment", system_prompt="You are a sentiment analyst."),
    InsightsAgent("insights", system_prompt="You are a business analyst."),
])


async def main():
    sample_text = """
    The new product launch exceeded expectations with 50,000 signups in the first week.
    Customer feedback has been overwhelmingly positive, with particular praise for the
    intuitive interface and fast performance. However, several users reported issues with
    the mobile experience and the onboarding flow could be smoother. The engineering team
    is already working on fixes for the next release.
    """

    ctx = AgentContext(data={"text": sample_text})
    result = await pipeline.execute(ctx)

    print(f"Pipeline: {result.pipeline_name}")
    print(f"Success: {result.success}")
    print(f"Duration: {result.duration_ms:.0f}ms\n")
    for r in result.results:
        print(f"--- {r.agent_name} ({r.duration_ms:.0f}ms) ---")
        print(r.output)
        print()


if __name__ == "__main__":
    asyncio.run(main())
