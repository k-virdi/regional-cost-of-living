# src/transformers/normalize.py
"""Transform raw extractor output into canonical ``IndicatorRecord`` objects.

Each ``normalize_*`` function takes a raw DataFrame from its corresponding
extractor and yields a list of validated Pydantic records.
"""

from datetime import date

import pandas as pd
from pydantic import ValidationError

from src.transformers.schema import (
    Country,
    IndicatorRecord,
    IndicatorType,
    ValidationReport,
)
from src.utils.logger import get_logger

log = get_logger(__name__)


def _validate_batch(records: list[dict]) -> tuple[list[IndicatorRecord], ValidationReport]:
    """Validate a list of candidate record dicts, collecting errors."""
    valid: list[IndicatorRecord] = []
    errors: list[dict] = []

    for idx, raw in enumerate(records):
        try:
            valid.append(IndicatorRecord(**raw))
        except ValidationError as exc:
            errors.append({"index": idx, "raw": raw, "errors": exc.errors()})

    report = ValidationReport(
        total=len(records),
        valid=len(valid),
        invalid=len(errors),
        errors=errors[:20],  # cap error payload
    )
    if errors:
        log.warning("validation_errors", invalid_count=len(errors))
    return valid, report


# ---------------------------------------------------------------------------
# Statistics Canada
# ---------------------------------------------------------------------------

def normalize_statcan_cpi(df: pd.DataFrame) -> tuple[list[IndicatorRecord], ValidationReport]:
    """Normalize StatCan CPI table into IndicatorRecords."""
    required = {"REF_DATE", "GEO", "VALUE"}
    if not required.issubset(df.columns):
        raise ValueError(f"StatCan CPI missing columns: {required - set(df.columns)}")

    records: list[dict] = []
    for _, row in df.iterrows():
        if pd.isna(row["VALUE"]):
            continue
        records.append(
            {
                "country": Country.CANADA,
                "province_state": str(row["GEO"]),
                "city": None,
                "indicator_type": IndicatorType.CPI,
                "reference_date": str(row["REF_DATE"]),
                "value": row["VALUE"],
                "currency": None,       # CPI is an index, not a currency
                "is_inflation_adjusted": False,
                "source_table": "statcan:18100004",
                "status_flag": str(row.get("STATUS", "")) or None,
            }
        )
    return _validate_batch(records)


def normalize_statcan_labour(df: pd.DataFrame) -> tuple[list[IndicatorRecord], ValidationReport]:
    """Normalize StatCan Labour Force table into IndicatorRecords."""
    records: list[dict] = []
    for _, row in df.iterrows():
        if pd.isna(row["VALUE"]):
            continue
        records.append(
            {
                "country": Country.CANADA,
                "province_state": str(row["GEO"]),
                "city": None,
                "indicator_type": IndicatorType.UNEMPLOYMENT_RATE,
                "reference_date": str(row["REF_DATE"]),
                "value": row["VALUE"],
                "currency": None,
                "is_inflation_adjusted": False,
                "source_table": "statcan:14100287",
                "status_flag": str(row.get("STATUS", "")) or None,
            }
        )
    return _validate_batch(records)


# ---------------------------------------------------------------------------
# BLS
# ---------------------------------------------------------------------------

def normalize_bls(df: pd.DataFrame, logical_name: str) -> tuple[list[IndicatorRecord], ValidationReport]:
    """Normalize a BLS series DataFrame into IndicatorRecords."""
    indicator_map = {
        "cpi_all_items": IndicatorType.CPI,
        "cpi_food": IndicatorType.CPI,
        "cpi_rent": IndicatorType.CPI,
        "avg_hourly_earnings": IndicatorType.AVERAGE_HOURLY_EARNINGS,
    }
    indicator_type = indicator_map.get(logical_name, IndicatorType.CPI)

    records: list[dict] = []
    for _, row in df.iterrows():
        if pd.isna(row["value"]):
            continue
        records.append(
            {
                "country": Country.UNITED_STATES,
                "province_state": "United States",
                "city": None,
                "indicator_type": indicator_type,
                "reference_date": row["date"].strftime("%Y-%m") if hasattr(row["date"], "strftime") else str(row["date"]),
                "value": row["value"],
                "currency": "USD" if indicator_type == IndicatorType.AVERAGE_HOURLY_EARNINGS else None,
                "is_inflation_adjusted": False,
                "source_table": f"bls:{row['series_id']}",
                "status_flag": None,
            }
        )
    return _validate_batch(records)


# ---------------------------------------------------------------------------
# Census
# ---------------------------------------------------------------------------

def normalize_census(df: pd.DataFrame) -> tuple[list[IndicatorRecord], ValidationReport]:
    """Normalize a Census ACS DataFrame into IndicatorRecords."""
    income_var = "B19013_001E"
    rent_var = "B25064_001E"
    per_capita_var = "B19301_001E"

    records: list[dict] = []
    for _, row in df.iterrows():
        acs_year = int(row["acs_year"])
        state_name = str(row.get("NAME", "Unknown"))

        for var, indicator_type, currency in [
            (income_var, IndicatorType.MEDIAN_INCOME, "USD"),
            (rent_var, IndicatorType.AVERAGE_RENT, "USD"),
            (per_capita_var, IndicatorType.PER_CAPITA_INCOME, "USD"),
        ]:
            if var not in row or pd.isna(row[var]):
                continue
            records.append(
                {
                    "country": Country.UNITED_STATES,
                    "province_state": state_name,
                    "city": None,
                    "indicator_type": indicator_type,
                    "reference_date": f"{acs_year}-01-01",
                    "value": row[var],
                    "currency": currency,
                    "is_inflation_adjusted": True,  # ACS values are inflation-adjusted
                    "source_table": f"census:acs5:{acs_year}:{var}",
                    "status_flag": None,
                }
            )
    return _validate_batch(records)


# ---------------------------------------------------------------------------
# CMHC
# ---------------------------------------------------------------------------

def normalize_cmhc(df: pd.DataFrame, logical_name: str) -> tuple[list[IndicatorRecord], ValidationReport]:
    """Best-effort normalization of a CMHC rental market CSV.

    CMHC column names vary by vintage; we look for common patterns and
    skip rows we cannot map confidently.
    """
    # Try to find date and rent columns heuristically
    date_col = next((c for c in df.columns if "date" in c.lower() or "year" in c.lower()), None)
    rent_col = next((c for c in df.columns if "rent" in c.lower()), None)
    geo_col = next((c for c in df.columns if "geo" in c.lower() or "centre" in c.lower() or "cma" in c.lower()), None)

    if not (date_col and rent_col and geo_col):
        log.warning("cmhc_columns_unmapped", columns=list(df.columns))
        return [], ValidationReport(total=0, valid=0, invalid=0, errors=[])

    records: list[dict] = []
    for _, row in df.iterrows():
        if pd.isna(row.get(date_col)) or pd.isna(row.get(rent_col)):
            continue
        records.append(
            {
                "country": Country.CANADA,
                "province_state": str(row[geo_col]),
                "city": str(row[geo_col]),
                "indicator_type": IndicatorType.AVERAGE_RENT,
                "reference_date": str(row[date_col]),
                "value": row[rent_col],
                "currency": "CAD",
                "is_inflation_adjusted": False,
                "source_table": f"cmhc:{logical_name}",
                "status_flag": None,
            }
        )
    return _validate_batch(records)
