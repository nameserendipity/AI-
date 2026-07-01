"""Database models for scheduled market-memory analysis runs."""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class AStockMemoryRun(Base):
    """One scheduled market-memory analysis run.

    The name keeps the current A-share focus, while columns such as market_type
    and analyzer_type keep the table usable for future US/HK market analyzers.
    """

    __tablename__ = "astock_memory_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), unique=True, nullable=False, index=True)
    market_type = Column(String(32), nullable=False, default="astock", index=True)
    analyzer_type = Column(String(64), nullable=False, default="astock_analysis")
    status = Column(String(32), nullable=False, default="completed", index=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    interval_minutes = Column(Integer, nullable=True)
    history_limit = Column(Integer, nullable=True)

    total_items = Column(Integer, nullable=False, default=0)
    analyzed_items = Column(Integer, nullable=False, default=0)
    skipped_items = Column(Integer, nullable=False, default=0)
    error_items = Column(Integer, nullable=False, default=0)

    model_provider = Column(String(64), nullable=True)
    model_id = Column(String(200), nullable=True)
    market_summary = Column(Text, nullable=True)
    overall_risk_level = Column(String(32), nullable=True)
    llm_raw = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    run_metadata = Column(JSON, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    items = relationship(
        "AStockMemoryItem",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class AStockMemoryItem(Base):
    """Per-symbol market-memory analysis item."""

    __tablename__ = "astock_memory_items"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(
        String(64),
        ForeignKey("astock_memory_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    ticker = Column(String(80), nullable=False, index=True)
    normalized_symbol = Column(String(80), nullable=True, index=True)
    display_name = Column(String(200), nullable=True)
    market_type = Column(String(32), nullable=False, default="astock", index=True)
    analyzer_type = Column(String(64), nullable=False, default="astock_analysis")
    data_source = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default="analyzed", index=True)
    skip_reason = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    trend = Column(String(32), nullable=True, index=True)
    confidence = Column(Float, nullable=True)
    horizon = Column(String(64), nullable=True)
    reason = Column(Text, nullable=True)
    memory_delta = Column(String(32), nullable=True)
    score = Column(Float, nullable=True)
    action = Column(String(32), nullable=True)
    bias = Column(String(32), nullable=True)
    latest_price = Column(Float, nullable=True)
    change_5d_pct = Column(Float, nullable=True)
    change_20d_pct = Column(Float, nullable=True)

    risk_flags = Column(JSON, nullable=True)
    key_points = Column(JSON, nullable=True)
    blocked_reasons = Column(JSON, nullable=True)
    analysis_snapshot = Column(JSON, nullable=True)
    llm_item = Column(JSON, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    run = relationship("AStockMemoryRun", back_populates="items")
