"""News-related tools for the News Agent."""

from datetime import datetime
from typing import Optional

from loguru import logger

from valuecell.agents.utils.search import web_search_with_fallback

REALTIME_SEARCH_UNAVAILABLE = "REALTIME_SEARCH_UNAVAILABLE"


async def web_search(query: str) -> str:
    """Search the web for the given query using middleware-first fallback."""
    return await web_search_with_fallback(query)


async def get_breaking_news() -> str:
    """Get breaking news and urgent updates."""
    try:
        search_query = (
            "latest breaking news urgent updates today past 24 hours "
            "include source urls and publication dates"
        )
        logger.info("Fetching breaking news")
        return await web_search(search_query)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error fetching breaking news: {e}")
        return f"{REALTIME_SEARCH_UNAVAILABLE}: {str(e)}"


async def get_financial_news(
    ticker: Optional[str] = None, sector: Optional[str] = None
) -> str:
    """Get financial and market news."""
    try:
        search_query = "latest financial market news past 7 days include source urls and dates"

        if ticker:
            search_query = (
                f"latest {ticker} stock news past 7 days financial market "
                "include source urls and publication dates"
            )
        elif sector:
            search_query = (
                f"latest {sector} sector financial news past 7 days "
                "include source urls and publication dates"
            )

        today = datetime.now().strftime("%Y-%m-%d")
        search_query += f" as of {today}"

        logger.info(f"Searching for financial news with query: {search_query}")
        return await web_search(search_query)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error fetching financial news: {e}")
        return f"{REALTIME_SEARCH_UNAVAILABLE}: {str(e)}"
