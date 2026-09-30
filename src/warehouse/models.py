# src/warehouse/models.py
"""SQLAlchemy 2.0 ORM models for the regional cost of living warehouse.

Star schema design:
    - dim_regions   (geography dimension)
    - dim_dates     (time dimension, generated)
    - fct_indicators (fact table, long/narrow format)
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all warehouse models."""
    pass


# ---------------------------------------------------------------------------
# Dimension: regions
# ---------------------------------------------------------------------------

class DimRegion(Base):
    """Geography dimension: countries, provinces/states, cities."""

    __tablename__ = "dim_regions"

    region_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    province_state: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    geo_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, unique=True)
    created_at: Mapped[date] = mapped_column(
        Date, server_default=func.current_date(), nullable=False
    )

    indicators: Mapped[list["FctIndicator"]] = relationship(
        back_populates="region", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "country", "province_state", "city",
            name="uq_region_country_province_city",
        ),
        Index("ix_region_lookup", "country", "province_state"),
    )

    def __repr__(self) -> str:
        return f"DimRegion(id={self.region_id}, {self.country}/{self.province_state})"


# ---------------------------------------------------------------------------
# Dimension: dates
# ---------------------------------------------------------------------------

class DimDate(Base):
    """Time dimension: one row per calendar date at month granularity."""

    __tablename__ = "dim_dates"

    date_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    is_recession: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    indicators: Mapped[list["FctIndicator"]] = relationship(back_populates="dim_date")

    def __repr__(self) -> str:
        return f"DimDate({self.full_date})"


# ---------------------------------------------------------------------------
# Fact: indicators
# ---------------------------------------------------------------------------

class FctIndicator(Base):
    """Fact table: economic indicator observations in long/narrow format.

    A composite unique constraint on (region_id, date_id, indicator_type)
    allows idempotent upserts via ON CONFLICT DO NOTHING.
    """

    __tablename__ = "fct_indicators"

    indicator_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("dim_regions.region_id", ondelete="CASCADE"), nullable=False
    )
    date_id: Mapped[int] = mapped_column(
        ForeignKey("dim_dates.date_id", ondelete="CASCADE"), nullable=False
    )
    indicator_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    is_inflation_adjusted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_table: Mapped[str] = mapped_column(String(200), nullable=False)
    status_flag: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    loaded_at: Mapped[date] = mapped_column(
        Date, server_default=func.current_date(), nullable=False
    )

    region: Mapped["DimRegion"] = relationship(back_populates="indicators")
    dim_date: Mapped["DimDate"] = relationship(back_populates="indicators")

    __table_args__ = (
        UniqueConstraint(
            "region_id", "date_id", "indicator_type",
            name="uq_indicator_region_date_type",
        ),
        CheckConstraint("value > 0", name="ck_indicator_value_positive"),
        Index("ix_indicator_type_date", "indicator_type", "date_id"),
        Index("ix_indicator_region_type", "region_id", "indicator_type"),
    )

    def __repr__(self) -> str:
        return (
            f"FctIndicator(id={self.indicator_id}, "
            f"type={self.indicator_type}, value={self.value})"
        )
