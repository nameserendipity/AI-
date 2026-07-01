"""A2A server entry point for AStockAnalysisAgent."""

import asyncio

from valuecell.core.agent.decorator import create_wrapped_agent

from .core import AStockAnalysisAgent

if __name__ == "__main__":
    agent = create_wrapped_agent(AStockAnalysisAgent)
    asyncio.run(agent.serve())
