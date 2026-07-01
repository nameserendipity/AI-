"""Repository for scheduled market-memory analysis records."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..connection import get_database_manager
from ..models.astock_memory import AStockMemoryItem, AStockMemoryRun


class AStockMemoryRepository:
    """Database access for market-memory runs and per-symbol items."""

    def __init__(self, db_session: Optional[Session] = None):
        self.db_session = db_session

    def _get_session(self) -> Session:
        if self.db_session:
            return self.db_session
        return get_database_manager().get_session()

    def create_run(
        self,
        *,
        run_id: str,
        market_type: str,
        analyzer_type: str,
        status: str,
        started_at: datetime,
        interval_minutes: int,
        history_limit: int,
        model_provider: str | None = None,
        model_id: str | None = None,
        metadata: dict | None = None,
    ) -> AStockMemoryRun:
        session = self._get_session()
        try:
            run = AStockMemoryRun(
                run_id=run_id,
                market_type=market_type,
                analyzer_type=analyzer_type,
                status=status,
                started_at=started_at,
                interval_minutes=interval_minutes,
                history_limit=history_limit,
                model_provider=model_provider,
                model_id=model_id,
                run_metadata=metadata or {},
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            session.expunge(run)
            return run
        except Exception:
            session.rollback()
            raise
        finally:
            if not self.db_session:
                session.close()

    def finalize_run(
        self,
        *,
        run_id: str,
        status: str,
        completed_at: datetime,
        total_items: int,
        analyzed_items: int,
        skipped_items: int,
        error_items: int,
        market_summary: str | None = None,
        overall_risk_level: str | None = None,
        llm_raw: str | None = None,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        session = self._get_session()
        try:
            run = session.query(AStockMemoryRun).filter_by(run_id=run_id).first()
            if run is None:
                return
            run.status = status
            run.completed_at = completed_at
            run.total_items = total_items
            run.analyzed_items = analyzed_items
            run.skipped_items = skipped_items
            run.error_items = error_items
            run.market_summary = market_summary
            run.overall_risk_level = overall_risk_level
            run.llm_raw = llm_raw
            run.error_message = error_message
            if metadata is not None:
                run.run_metadata = metadata
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if not self.db_session:
                session.close()

    def add_item(self, **values) -> AStockMemoryItem:
        session = self._get_session()
        try:
            item = AStockMemoryItem(**values)
            session.add(item)
            session.commit()
            session.refresh(item)
            session.expunge(item)
            return item
        except Exception:
            session.rollback()
            raise
        finally:
            if not self.db_session:
                session.close()

    def recent_runs(
        self,
        *,
        market_type: str = "astock",
        limit: int = 5,
    ) -> list[AStockMemoryRun]:
        session = self._get_session()
        try:
            runs = (
                session.query(AStockMemoryRun)
                .filter(AStockMemoryRun.market_type == market_type)
                .order_by(desc(AStockMemoryRun.completed_at), desc(AStockMemoryRun.id))
                .limit(limit)
                .all()
            )
            for run in runs:
                session.expunge(run)
            return runs
        finally:
            if not self.db_session:
                session.close()


    def latest_run(
        self,
        *,
        market_type: str = "astock",
    ) -> AStockMemoryRun | None:
        session = self._get_session()
        try:
            run = (
                session.query(AStockMemoryRun)
                .filter(AStockMemoryRun.market_type == market_type)
                .order_by(desc(AStockMemoryRun.completed_at), desc(AStockMemoryRun.id))
                .first()
            )
            if run is not None:
                session.expunge(run)
            return run
        finally:
            if not self.db_session:
                session.close()

    def items_for_run(
        self,
        *,
        run_id: str,
        include_skipped: bool = True,
        limit: int = 100,
    ) -> list[AStockMemoryItem]:
        session = self._get_session()
        try:
            query = session.query(AStockMemoryItem).filter(
                AStockMemoryItem.run_id == run_id
            )
            if not include_skipped:
                query = query.filter(AStockMemoryItem.status == "analyzed")
            items = (
                query.order_by(AStockMemoryItem.ticker.asc(), AStockMemoryItem.id.asc())
                .limit(limit)
                .all()
            )
            for item in items:
                session.expunge(item)
            return items
        finally:
            if not self.db_session:
                session.close()
    def recent_items_by_symbol(
        self,
        *,
        normalized_symbol: str,
        market_type: str = "astock",
        limit: int = 5,
    ) -> list[AStockMemoryItem]:
        session = self._get_session()
        try:
            items = (
                session.query(AStockMemoryItem)
                .filter(
                    AStockMemoryItem.market_type == market_type,
                    AStockMemoryItem.normalized_symbol == normalized_symbol,
                )
                .order_by(desc(AStockMemoryItem.created_at), desc(AStockMemoryItem.id))
                .limit(limit)
                .all()
            )
            for item in items:
                session.expunge(item)
            return items
        finally:
            if not self.db_session:
                session.close()


def get_astock_memory_repository(
    db_session: Optional[Session] = None,
) -> AStockMemoryRepository:
    return AStockMemoryRepository(db_session=db_session)

