"""Fund and FundHolding models for tracking mutual fund holdings."""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import DetachedInstanceError
from sqlalchemy.sql import func

from .base import Base


class Fund(Base):
    """Fund model representing a user-tracked mutual fund."""

    __tablename__ = "funds"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True, comment="User identifier")
    name = Column(String(200), nullable=False, comment="Fund display name")
    code = Column(String(50), nullable=True, comment="Fund code (e.g., 014811)")
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="Creation timestamp",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp",
    )

    # Relationships
    holdings = relationship(
        "FundHolding", back_populates="fund", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Fund(id={self.id}, name='{self.name}', code='{self.code}')>"

    def to_dict(self) -> dict:
        holdings_count = 0
        try:
            if self.holdings is not None:
                holdings_count = len(self.holdings)
        except DetachedInstanceError:
            pass
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "code": self.code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "holdings_count": holdings_count,
        }


class FundHolding(Base):
    """Individual stock holding within a fund."""

    __tablename__ = "fund_holdings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    fund_id = Column(
        Integer,
        ForeignKey("funds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticker = Column(
        String(50),
        nullable=False,
        comment="Stock ticker (e.g., 688409 for A-share)",
    )
    name = Column(String(200), nullable=True, comment="Stock display name")
    weight = Column(
        Float,
        nullable=False,
        default=0.0,
        comment="Holding weight percentage (e.g., 8.5 means 8.5%)",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="Creation timestamp",
    )

    # Relationships
    fund = relationship("Fund", back_populates="holdings")

    def __repr__(self) -> str:
        return (
            f"<FundHolding(id={self.id}, ticker='{self.ticker}', "
            f"weight={self.weight})>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "fund_id": self.fund_id,
            "ticker": self.ticker,
            "name": self.name,
            "weight": self.weight,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
