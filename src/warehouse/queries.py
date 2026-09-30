# src/warehouse/queries.py
"""Analytical query library against the warehouse.

All functions return pandas DataFrames and are designed to be consumed
directly by the Streamlit dashboard (Layer 3).
"""

import pandas as pd

from src.warehouse.session import get_engine


def get_time_series(
    indicator_type: str,
    country: str | None = None,
    province_state: str | None = None,
    start_year: int = 1975,
) -> pd.DataFrame:
    """Fetch a single indicator's time series for a region."""
    sql = """
        SELECT
            d.full_date,
            d.year,
            d.month,
            r.country,
            r.province_state,
            r.city,
            f.value,
            f.currency,
            f.is_inflation_adjusted
        FROM fct_indicators f
        JOIN dim_regions r USING (region_id)
        JOIN dim_dates d USING (date_id)
        WHERE f.indicator_type = %(indicator_type)s
          AND d.year >= %(start_year)s
          AND (%(country)s IS NULL OR r.country = %(country)s)
          AND (%(province_state)s IS NULL OR r.province_state = %(province_state)s)
        ORDER BY d.full_date, r.province_state
    """
    params = {
        "indicator_type": indicator_type,
        "start_year": start_year,
        "country": country,
        "province_state": province_state,
    }
    return pd.read_sql(sql, get_engine(), params=params)


def get_rent_to_income(
    start_year: int = 1975,
    country: str | None = None,
) -> pd.DataFrame:
    """Fetch rent-to-income ratios from the dbt mart (if dbt has been run).

    Falls back to computing on the fly if the mart is not present.
    """
    sql = """
        SELECT
            full_date,
            year,
            country,
            province_state,
            city,
            rent_to_income_pct,
            real_median_income,
            rent_yoy_pct
        FROM analytics.fct_affordability
        WHERE year >= %(start_year)s
          AND (%(country)s IS NULL OR country = %(country)s)
        ORDER BY full_date, province_state
    """
    try:
        return pd.read_sql(
            sql, get_engine(), params={"start_year": start_year, "country": country}
        )
    except Exception:
        # Mart not yet built — compute inline
        sql_inline = """
            WITH pivoted AS (
                SELECT
                    r.country, r.province_state, d.full_date, d.year,
                    MAX(CASE WHEN f.indicator_type = 'median_income' THEN f.value END) AS income,
                    MAX(CASE WHEN f.indicator_type = 'average_rent' THEN f.value END) AS rent,
                    MAX(CASE WHEN f.indicator_type = 'cpi' THEN f.value END) AS cpi
                FROM fct_indicators f
                JOIN dim_regions r USING (region_id)
                JOIN dim_dates d USING (date_id)
                WHERE d.year >= %(start_year)s
                GROUP BY 1, 2, 3, 4
            )
            SELECT
                country, province_state, full_date, year,
                ROUND((rent * 12.0 / NULLIF(income, 0)) * 100, 2) AS rent_to_income_pct,
                ROUND(income / NULLIF(cpi, 0) * 100, 2) AS real_median_income
            FROM pivoted
            WHERE income IS NOT NULL AND rent IS NOT NULL
            ORDER BY full_date, province_state
        """
        return pd.read_sql(
            sql_inline, get_engine(),
            params={"start_year": start_year},
        )


def get_available_regions() -> pd.DataFrame:
    """Return all distinct regions for dashboard filter dropdowns."""
    sql = """
        SELECT DISTINCT country, province_state, city
        FROM dim_regions
        ORDER BY country, province_state, city NULLS FIRST
    """
    return pd.read_sql(sql, get_engine())


def get_indicator_coverage() -> pd.DataFrame:
    """Return a coverage report: which indicators exist for which regions/years."""
    sql = """
        SELECT
            f.indicator_type,
            r.country,
            MIN(d.year) AS min_year,
            MAX(d.year) AS max_year,
            COUNT(*) AS row_count
        FROM fct_indicators f
        JOIN dim_regions r USING (region_id)
        JOIN dim_dates d USING (date_id)
        GROUP BY 1, 2
        ORDER BY 1, 2
    """
    return pd.read_sql(sql, get_engine())
