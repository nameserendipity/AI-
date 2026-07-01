"""Repository for dynamic crypto pool candidates."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..connection import get_database_manager
from ..models.crypto_pool import CryptoPoolCandidate


class CryptoPoolRepository:
    def __init__(self, db_session: Optional[Session] = None):
        self.db_session = db_session

    def _get_session(self) -> Session:
        if self.db_session:
            return self.db_session
        return get_database_manager().get_session()

    def replace_candidates(
        self,
        *,
        exchange_id: str,
        market_type: str,
        candidates: list[dict],
        scanned_at: datetime,
    ) -> None:
        session = self._get_session()
        try:
            session.query(CryptoPoolCandidate).filter(
                CryptoPoolCandidate.exchange_id == exchange_id,
                CryptoPoolCandidate.market_type == market_type,
            ).delete()
            for candidate in candidates:
                session.add(
                    CryptoPoolCandidate(
                        exchange_id=exchange_id,
                        market_type=market_type,
                        scanned_at=scanned_at,
                        **candidate,
                    )
                )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if not self.db_session:
                session.close()

    def top_candidates(
        self,
        *,
        exchange_id: str = "okx",
        market_type: str = "swap",
        quote_currency: str = "USDT",
        limit: int = 5,
        max_age_seconds: int = 180,
    ) -> list[CryptoPoolCandidate]:
        session = self._get_session()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
            items = (
                session.query(CryptoPoolCandidate)
                .filter(
                    CryptoPoolCandidate.exchange_id == exchange_id,
                    CryptoPoolCandidate.market_type == market_type,
                    CryptoPoolCandidate.quote_currency == quote_currency,
                    CryptoPoolCandidate.status == "active",
                    CryptoPoolCandidate.scanned_at >= cutoff,
                )
                .order_by(desc(CryptoPoolCandidate.score), desc(CryptoPoolCandidate.quote_volume))
                .limit(limit)
                .all()
            )
            for item in items:
                session.expunge(item)
            return items
        finally:
            if not self.db_session:
                session.close()


def get_crypto_pool_repository(
    db_session: Optional[Session] = None,
) -> CryptoPoolRepository:
    return CryptoPoolRepository(db_session=db_session)
