"""A-share analysis agent."""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional

from loguru import logger

from valuecell.core.agent.responses import streaming
from valuecell.core.types import BaseAgent, StreamResponse
from valuecell.server.services.astock import AStockAnalysisService, extract_astock_symbol


class AStockAnalysisAgent(BaseAgent):
    """Low-cost A-share analysis agent based on the local A-share data layer."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.analysis_service = AStockAnalysisService()

    async def stream(
        self,
        query: str,
        conversation_id: str,
        task_id: str,
        dependencies: Optional[Dict] = None,
    ) -> AsyncGenerator[StreamResponse, None]:
        try:
            yield streaming.tool_call_started(task_id, "astock_analysis")
            content = await self.run(query, dependencies=dependencies)
            yield streaming.tool_call_completed(content, task_id, "astock_analysis")
            yield streaming.message_chunk(content)
            yield streaming.done()
        except Exception as exc:
            logger.warning("AStockAnalysisAgent failed: {}", exc)
            yield streaming.failed(f"A股分析失败：{exc}")

    async def run(self, query: str, **kwargs: Any) -> str:
        symbol = extract_astock_symbol(query)
        if symbol is None:
            return "请提供一个 A股代码，例如：300750、600519.SH、SZSE:000001。"
        report = await self.analysis_service.analyze_symbol(symbol)
        return self.analysis_service.to_markdown(report)

    async def analyze(self, symbol: str):
        """Return the structured analysis report for internal callers."""
        return await self.analysis_service.analyze_symbol(symbol)

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": "AStock Analysis Agent",
            "description": "Analyze A-share snapshots from the local structured data layer.",
            "tools": ["AStockDataService", "AStockAnalyzer"],
            "supported_queries": [
                "分析 300750",
                "帮我看一下 600519.SH 的走势",
                "宁德时代 300750 当前风险如何",
            ],
        }
