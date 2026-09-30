# dashboard/data_access.py
"""Cached data access layer for the Streamlit dashboard.

Caching strategy (Streamlit best practice):
    - @st.cache_resource  → SQLAlchemy engine (one pool per process)
    - @st.cache_data(ttl) → query results (per unique argument set)

This prevents the dashboard from re-querying PostgreSQL on every rerun,
which would otherwise execute the same query dozens of times per second.
"""

import os
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

# ---------------------------------------------------------------------------
# Connection pool — cached once per process
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    """Return a cached SQLAlchemy engine with connection pooling.

    Reads DATABASE_URL from st.secrets (deployed) or environment (local).
    Uses QueuePool with pool_pre_ping so stale connections are recycled.
    """
    try:
        db_url = st.secrets["DATABASE_URL"]
    except (KeyError, FileNotFoundError):
        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://rcol:rcol_dev_password@localhost:5432/regional_cost_of_living",
        )

    return create_engine(
        db_url,
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,   # reconnect if stale
        pool_recycle=1800,
        future=True,
    )


def is_database_reachable() -> bool:
    """Quick health check used to render a friendly error page."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Reference data — cached for 1 hour (changes rarely)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def load_available_regions() -> pd.DataFrame:
    """Return all distinct regions for filter dropdowns."""
    sql = """
        SELECT DISTINCT country, province_state, city
        FROM dim_regions
        ORDER BY country, province_state, city NULLS FIRST
    """
    return pd.read_sql(sql, get_engine())


@st.cache_data(ttl=3600, show_spinner=False)
def load_indicator_coverage() -> pd.DataFrame:
    """Return coverage metadata: indicator × region × year range."""
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


# ---------------------------------------------------------------------------
# Analytical queries — cached for 5 minutes (data freshness matters)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner="Loading time series…")
def load_time_series(
    indicator_type: str,
    country: Optional[str] = None,
    province_state: Optional[str] = None,
    start_year: int = 1975,
) -> pd.DataFrame:
    """Fetch a single indicator's monthly time series for a region."""
    sql = """
        SELECT
            d.full_date,
            d.year,
            d.month,
            d.is_recession,
            r.country,
            r.province_state,
            r.city,
            f.value,
            f.currency,
            f.is_inflation_adjusted
        FROM fct_indicators f
        JOIN dim_regions r USING (region_id)
        JOIN dim_dates d USING (date_id)
        WHERE f.indicator_type = :indicator_type
          AND d.year >= :start_year
          AND (:country IS NULL OR r.country = :country)
          AND (:province_state IS NULL OR r.province_state = :province_state)
        ORDER BY d.full_date, r.province_state
    """
    params = {
        "indicator_type": indicator_type,
        "start_year": start_year,
        "country": country,
        "province_state": province_state,
    }
    return pd.read_sql(text(sql), get_engine(), params=params)


@st.cache_data(ttl=300, show_spinner="Loading affordability data…")
def load_affordability(
    start_year: int = 1975,
    country: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch rent-to-income ratios and real income from the dbt mart.

    Falls back to an inline computation if the mart has not been built yet.
    """
    sql_mart = """
        SELECT
            full_date, year, country, province_state, city,
            rent_to_income_pct, real_median_income, rent_yoy_pct
        FROM analytics.fct_affordability
        WHERE year >= :start_year
          AND (:country IS NULL OR country = :country)
        ORDER BY full_date, province_state
    """
    try:
        return pd.read_sql(
            text(sql_mart),
            get_engine(),
            params={"start_year": start_year, "country": country},
        )
    except Exception:
        # Mart not built — compute inline from raw facts
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
                WHERE d.year >= :start_year
                GROUP BY 1, 2, 3, 4
            )
            SELECT
                country, province_state, full_date, year,
                ROUND((rent * 12.0 / NULLIF(income, 0)) * 100, 2) AS rent_to_income_pct,
                ROUND(income / NULLIF(cpi, 0) * 100, 2) AS real_median_income,
                NULL::NUMERIC AS rent_yoy_pct
            FROM pivoted
            WHERE income IS NOT NULL AND rent IS NOT NULL
            ORDER BY full_date, province_state
        """
        return pd.read_sql(
            text(sql_inline),
            get_engine(),
            params={"start_year": start_year},
        )


@st.cache_data(ttl=300, show_spinner="Loading regional snapshot…")
def load_regional_snapshot(
    year: int,
    country: Optional[str] = None,
) -> pd.DataFrame:
    """Latest-year snapshot per region: income, rent, unemployment, CPI."""
    sql = """
        WITH latest AS (
            SELECT
                r.country,
                r.province_state,
                f.indicator_type,
                f.value,
                ROW_NUMBER() OVER (
                    PARTITION BY r.region_id, f.indicator_type
                    ORDER BY d.full_date DESC
                ) AS rn
            FROM fct_indicators f
            JOIN dim_regions r USING (region_id)
            JOIN dim_dates d USING (date_id)
            WHERE d.year <= :year
              AND (:country IS NULL OR r.country = :country)
        )
        SELECT
            country,
            province_state,
            MAX(CASE WHEN indicator_type = 'median_income' THEN value END) AS median_income,
            MAX(CASE WHEN indicator_type = 'average_rent' THEN value END) AS average_rent,
            MAX(CASE WHEN indicator_type = 'cpi' THEN value END) AS cpi,
            MAX(CASE WHEN indicator_type = 'unemployment_rate' THEN value END) AS unemployment_rate
        FROM latest
        WHERE rn = 1
        GROUP BY 1, 2
        ORDER BY country, province_state
    """
    return pd.read_sql(
        text(sql),
        get_engine(),
        params={"year": year, "country": country},
    )


@st.cache_data(ttl=300, show_spinner="Loading CPI comparison…")
def load_cpi_comparison(start_year: int = 1975) -> pd.DataFrame:
    """Fetch CPI series for both countries for the inflation adjuster."""
    sql = """
        SELECT
            d.year,
            d.month,
            r.country,
            AVG(f.value) AS cpi
        FROM fct_indicators f
        JOIN dim_regions r USING (region_id)
        JOIN dim_dates d USING (date_id)
        WHERE f.indicator_type = 'cpi'
          AND d.year >= :start_year
        GROUP BY 1, 2, 3
        ORDER BY 1, 2, 3
    """
    return pd.read_sql(text(sql), get_engine(), params={"start_year": start_year})


def clear_all_caches() -> None:
    """Clear both the resource and data caches (wired to a sidebar button)."""
    st.cache_data.clear()
    st.cache_resource.clear()
