"""Database models for dynamic crypto candidate pools."""

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.sql import func

from .base import Base


class CryptoPoolCandidate(Base):
    """Latest scored market candidate for dynamic crypto strategy pools."""

    __tablename__ = "crypto_pool_candidates"

    id = Column(Integer, primary_key=True, index=True)
    exchange_id = Column(String(32), nullable=False, default="okx", index=True)
    market_type = Column(String(32), nullable=False, default="swap", index=True)
    symbol = Column(String(80), nullable=False, index=True)
    normalized_symbol = Column(String(120), nullable=True)
    quote_currency = Column(String(16), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="active", index=True)

    score = Column(Float, nullable=False, default=0.0, index=True)
    last_price = Column(Float, nullable=True)
    percentage_24h = Column(Float, nullable=True)
    quote_volume = Column(Float, nullable=True, index=True)
    base_volume = Column(Float, nullable=True)
    spread_pct = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    metrics = Column(JSON, nullable=True)

    scanned_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
