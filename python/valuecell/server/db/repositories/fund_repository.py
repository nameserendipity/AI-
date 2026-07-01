"""Fund repository for database operations."""

from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..connection import get_database_manager
from ..models.fund import Fund, FundHolding


class FundRepository:
    """Repository class for fund database operations."""

    def __init__(self, db_session: Optional[Session] = None):
        self.db_session = db_session

    def _get_session(self) -> Session:
        if self.db_session:
            return self.db_session
        return get_database_manager().get_session()

    def create_fund(
        self,
        user_id: str,
        name: str,
        code: Optional[str] = None,
        holdings: Optional[List[dict]] = None,
    ) -> Optional[Fund]:
        """Create a new fund with optional initial holdings.

        Args:
            user_id: User identifier
            name: Fund display name
            code: Fund code (optional)
            holdings: List of dicts with keys: ticker, name, weight
        """
        session = self._get_session()
        try:
            fund = Fund(user_id=user_id, name=name, code=code)
            session.add(fund)
            session.flush()

            if holdings:
                for h in holdings:
                    holding = FundHolding(
                        fund_id=fund.id,
                        ticker=h["ticker"],
                        name=h.get("name"),
                        weight=float(h.get("weight", 0)),
                    )
                    session.add(holding)

            session.commit()
            session.refresh(fund)
            session.expunge(fund)
            return fund
        except IntegrityError:
            session.rollback()
            return None
        except Exception:
            session.rollback()
            return None
        finally:
            if not self.db_session:
                session.close()

    def get_fund(self, fund_id: int, user_id: str) -> Optional[Fund]:
        """Get a specific fund by ID."""
        session = self._get_session()
        try:
            fund = (
                session.query(Fund)
                .filter(Fund.id == fund_id, Fund.user_id == user_id)
                .first()
            )
            if fund:
                session.expunge(fund)
            return fund
        finally:
            if not self.db_session:
                session.close()

    def get_user_funds(self, user_id: str) -> List[Fund]:
        """Get all funds for a user."""
        session = self._get_session()
        try:
            funds = (
                session.query(Fund)
                .filter(Fund.user_id == user_id)
                .order_by(Fund.created_at.desc())
                .all()
            )
            for f in funds:
                session.expunge(f)
            return funds
        finally:
            if not self.db_session:
                session.close()

    def get_fund_holdings(self, fund_id: int) -> List[FundHolding]:
        """Get all holdings for a fund."""
        session = self._get_session()
        try:
            holdings = (
                session.query(FundHolding)
                .filter(FundHolding.fund_id == fund_id)
                .all()
            )
            for h in holdings:
                session.expunge(h)
            return holdings
        finally:
            if not self.db_session:
                session.close()

    def add_holding(
        self, fund_id: int, ticker: str, name: Optional[str] = None, weight: float = 0.0
    ) -> Optional[FundHolding]:
        """Add a holding to a fund."""
        session = self._get_session()
        try:
            holding = FundHolding(
                fund_id=fund_id, ticker=ticker, name=name, weight=weight
            )
            session.add(holding)
            session.commit()
            session.refresh(holding)
            session.expunge(holding)
            return holding
        except IntegrityError:
            session.rollback()
            return None
        except Exception:
            session.rollback()
            return None
        finally:
            if not self.db_session:
                session.close()

    def remove_holding(self, fund_id: int, ticker: str) -> bool:
        """Remove a holding from a fund."""
        session = self._get_session()
        try:
            holding = (
                session.query(FundHolding)
                .filter(
                    FundHolding.fund_id == fund_id, FundHolding.ticker == ticker
                )
                .first()
            )
            if not holding:
                return False
            session.delete(holding)
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            if not self.db_session:
                session.close()

    def delete_fund(self, fund_id: int, user_id: str) -> bool:
        """Delete a fund and all its holdings."""
        session = self._get_session()
        try:
            fund = (
                session.query(Fund)
                .filter(Fund.id == fund_id, Fund.user_id == user_id)
                .first()
            )
            if not fund:
                return False
            session.delete(fund)
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            if not self.db_session:
                session.close()


_fund_repository: Optional[FundRepository] = None


def get_fund_repository() -> FundRepository:
    global _fund_repository
    if _fund_repository is None:
        _fund_repository = FundRepository()
    return _fund_repository
