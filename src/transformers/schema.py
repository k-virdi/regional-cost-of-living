# src/transformers/schema.py
"""Pydantic models for validating extracted economic indicator records.

Every extractor must produce records conforming to ``IndicatorRecord``.
This guarantees that downstream layers (warehouse, dashboard, game theory)
receive uniformly typed, validated data — no silent string leaks.
"""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Country(str, Enum):
    CANADA = "CA"
    UNITED_STATES = "US"


class IndicatorType(str, Enum):
    CPI = "cpi"
    MEDIAN_INCOME = "median_income"
    AVERAGE_RENT = "average_rent"
    PER_CAPITA_INCOME = "per_capita_income"
    UNEMPLOYMENT_RATE = "unemployment_rate"
    AVERAGE_HOURLY_EARNINGS = "average_hourly_earnings"
    RENTAL_VACANCY_RATE = "rental_vacancy_rate"


class IndicatorRecord(BaseModel):
    """A single validated economic observation.

    This is the canonical interchange format between extraction and loading.
    """

    country: Country
    province_state: str = Field(..., min_length=1, max_length=100)
    city: Optional[str] = Field(default=None, max_length=100)
    indicator_type: IndicatorType
    reference_date: date
    value: Decimal = Field(..., gt=0)
    currency: Optional[str] = Field(default=None, pattern=r"^[A-Z]{3}$")
    is_inflation_adjusted: bool = False
    source_table: str = Field(..., min_length=1, max_length=200)
    status_flag: Optional[str] = Field(default=None, max_length=10)

    @field_validator("reference_date", mode="before")
    @classmethod
    def parse_date(cls, v):
        """Accept ISO strings, 'YYYY-MM', or 'YYYY' and coerce to date."""
        if isinstance(v, date):
            return v
        s = str(v).strip()
        if len(s) == 4:          # "2023"
            return date(int(s), 1, 1)
        if len(s) == 7:          # "2023-06"
            year, month = s.split("-")
            return date(int(year), int(month), 1)
        return date.fromisoformat(s)

    @field_validator("value", mode="before")
    @classmethod
    def coerce_value(cls, v):
        """Strip commas, percent signs, and whitespace before Decimal conversion."""
        if isinstance(v, (int, float, Decimal)):
            return Decimal(str(v))
        cleaned = str(v).replace(",", "").replace("%", "").strip()
        return Decimal(cleaned)


class ValidationReport(BaseModel):
    """Summary of a validation run over a batch of records."""

    total: int
    valid: int
    invalid: int
    errors: list[dict]
