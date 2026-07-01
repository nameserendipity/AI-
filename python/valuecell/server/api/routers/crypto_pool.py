"""Dynamic crypto pool API routes."""

from fastapi import APIRouter, Query

from valuecell.server.db.repositories.crypto_pool_repository import (
    get_crypto_pool_repository,
)

from ..schemas import SuccessResponse


def create_crypto_pool_router() -> APIRouter:
    router = APIRouter(prefix="/crypto-pool", tags=["CryptoPool"])

    @router.get("/latest", summary="Get latest dynamic crypto pool candidates")
    async def latest_crypto_pool(
        exchange_id: str = Query("okx"),
        market_type: str = Query("swap"),
        quote_currency: str = Query("USDT"),
        limit: int = Query(5, ge=1, le=20),
    ):
        items = get_crypto_pool_repository().top_candidates(
            exchange_id=exchange_id,
            market_type=market_type,
            quote_currency=quote_currency,
            limit=limit,
            max_age_seconds=3600,
        )
        return SuccessResponse.create(
            data=[
                {
                    "symbol": item.symbol,
                    "score": item.score,
                    "last_price": item.last_price,
                    "percentage_24h": item.percentage_24h,
                    "quote_volume": item.quote_volume,
                    "spread_pct": item.spread_pct,
                    "reason": item.reason,
                    "scanned_at": item.scanned_at.isoformat()
                    if item.scanned_at
                    else None,
                }
                for item in items
            ]
        )

    return router
