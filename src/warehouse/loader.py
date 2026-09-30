# src/warehouse/loader.py
"""Bulk-load validated Parquet files into the PostgreSQL warehouse.

Uses PostgreSQL's COPY protocol via psycopg3 for maximum throughput.
The loader is idempotent: re-running it will not create duplicates
thanks to the unique constraint on (region_id, date_id, indicator_type)
combined with a temporary staging table.
"""

import io
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import psycopg
from psycopg import sql

from src.utils.logger import get_logger
from src.warehouse.session import get_database_url

log = get_logger(__name__)

# Recession periods (NBER for US, C.D. Howe for Canada — simplified)
RECESSION_PERIODS = [
    (date(1980, 1, 1), date(1980, 7, 1)),
    (date(1981, 7, 1), date(1982, 11, 1)),
    (date(1990, 7, 1), date(1991, 3, 1)),
    (date(2001, 3, 1), date(2001, 11, 1)),
    (date(2007, 12, 1), date(2009, 6, 1)),
    (date(2020, 2, 1), date(2020, 4, 1)),
]


def _is_recession(d: date) -> bool:
    """Return True if the given date falls within a known recession."""
    for start, end in RECESSION_PERIODS:
        if start <= d <= end:
            return True
    return False


def seed_dates(conn: psycopg.Connection, start_year: int = 1975, end_year: int = 2026) -> int:
    """Populate dim_dates with one row per month across the range.

    Returns the number of rows inserted.
    """
    log.info("seeding_dates", start=start_year, end=end_year)
    rows = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            d = date(year, month, 1)
            rows.append((d, year, month, (month - 1) // 3 + 1, _is_recession(d)))

    with conn.cursor() as cur:
        # Use COPY for speed
        with cur.copy(
            "COPY dim_dates (full_date, year, month, quarter, is_recession) "
            "FROM STDIN WITH (FORMAT CSV)"
        ) as copy:
            buf = io.StringIO()
            for row in rows:
                buf.write(
                    f"{row[0].isoformat()},{row[1]},{row[2]},{row[3]},{str(row[4]).lower()}\n"
                )
            buf.seek(0)
            copy.write(buf.read())
        conn.commit()

    log.info("seeded_dates", count=len(rows))
    return len(rows)


def seed_regions_from_indicators(conn: psycopg.Connection, parquet_dir: Path) -> int:
    """Extract distinct (country, province_state, city) tuples from Parquet
    files and insert them into dim_regions.
    """
    log.info("seeding_regions", parquet_dir=str(parquet_dir))
    region_set: set[tuple] = set()

    for pq_file in Path(parquet_dir).glob("*.parquet"):
        df = pd.read_parquet(pq_file, columns=["country", "province_state", "city"])
        for _, row in df.iterrows():
            region_set.add(
                (
                    str(row["country"]),
                    str(row["province_state"]),
                    str(row["city"]) if pd.notna(row["city"]) else None,
                )
            )

    with conn.cursor() as cur:
        with cur.copy(
            "COPY dim_regions (country, province_state, city) FROM STDIN WITH (FORMAT CSV)"
        ) as copy:
            buf = io.StringIO()
            for country, province, city in region_set:
                city_val = city if city else ""
                buf.write(f"{country},{province},{city_val}\n")
            buf.seek(0)
            copy.write(buf.read())
        conn.commit()

    log.info("seeded_regions", count=len(region_set))
    return len(region_set)


def load_indicators(conn: psycopg.Connection, parquet_file: Path) -> int:
    """Load a single Parquet file into fct_indicators.

    Strategy: create a TEMPORARY staging table, COPY the Parquet data into
    it, then INSERT ... SELECT with a JOIN on dim_regions and dim_dates.
    This handles the surrogate key lookups efficiently and idempotently.
    """
    log.info("loading_indicators", file=str(parquet_file))
    df = pd.read_parquet(parquet_file)

    if df.empty:
        log.warning("empty_parquet", file=str(parquet_file))
        return 0

    # Normalize column names
    df = df.rename(
        columns={
            "reference_date": "full_date",
            "indicator_type": "indicator_type",
        }
    )
    df["full_date"] = pd.to_datetime(df["full_date"]).dt.date

    # Ensure currency is a string or empty
    if "currency" not in df.columns:
        df["currency"] = ""
    df["currency"] = df["currency"].fillna("").astype(str)

    if "status_flag" not in df.columns:
        df["status_flag"] = ""
    df["status_flag"] = df["status_flag"].fillna("").astype(str)

    # Build a temp table with the same column shape as the COPY payload
    staging_cols = [
        "country", "province_state", "city", "indicator_type",
        "full_date", "value", "currency", "is_inflation_adjusted",
        "source_table", "status_flag",
    ]
    df_staging = df[staging_cols].copy()
    df_staging["city"] = df_staging["city"].fillna("")
    df_staging["value"] = df_staging["value"].astype(float)

    with conn.cursor() as cur:
        # 1. Create temporary staging table
        cur.execute("""
            CREATE TEMP TABLE stg_indicators (
                country VARCHAR(2),
                province_state VARCHAR(100),
                city VARCHAR(100),
                indicator_type VARCHAR(50),
                full_date DATE,
                value NUMERIC(15,4),
                currency VARCHAR(3),
                is_inflation_adjusted BOOLEAN,
                source_table VARCHAR(200),
                status_flag VARCHAR(10)
            ) ON COMMIT DROP;
        """)

        # 2. COPY Parquet data into staging
        with cur.copy(
            "COPY stg_indicators FROM STDIN WITH (FORMAT CSV)"
        ) as copy:
            buf = io.StringIO()
            for _, row in df_staging.iterrows():
                city_val = row["city"] if row["city"] else ""
                buf.write(
                    f"{row['country']},{row['province_state']},{city_val},"
                    f"{row['indicator_type']},{row['full_date'].isoformat()},"
                    f"{row['value']},{row['currency']},"
                    f"{str(row['is_inflation_adjusted']).lower()},"
                    f"{row['source_table']},{row['status_flag']}\n"
                )
            buf.seek(0)
            copy.write(buf.read())

        # 3. INSERT ... SELECT with joins to resolve surrogate keys
        cur.execute("""
            INSERT INTO fct_indicators (
                region_id, date_id, indicator_type, value, currency,
                is_inflation_adjusted, source_table, status_flag
            )
            SELECT
                r.region_id,
                d.date_id,
                s.indicator_type,
                s.value,
                NULLIF(s.currency, ''),
                s.is_inflation_adjusted,
                s.source_table,
                NULLIF(s.status_flag, '')
            FROM stg_indicators s
            JOIN dim_regions r
                ON r.country = s.country
               AND r.province_state = s.province_state
               AND COALESCE(r.city, '') = COALESCE(s.city, '')
            JOIN dim_dates d
                ON d.full_date = s.full_date
            ON CONFLICT (region_id, date_id, indicator_type) DO NOTHING;
        """)

        inserted = cur.rowcount
        conn.commit()

    log.info("loaded_indicators", file=str(parquet_file), rows_inserted=inserted)
    return inserted


def run_warehouse_load(parquet_dir: Path) -> dict:
    """Full warehouse load: seed dimensions, then load all fact Parquet files.

    Returns a summary dict with counts per stage.
    """
    database_url = get_database_url().replace("postgresql+psycopg://", "postgresql://")
    summary = {"dates_seeded": 0, "regions_seeded": 0, "indicators_loaded": 0, "files_processed": 0}

    with psycopg.connect(database_url) as conn:
        summary["dates_seeded"] = seed_dates(conn, start_year=1975, end_year=2026)
        summary["regions_seeded"] = seed_regions_from_indicators(conn, parquet_dir)

        for pq_file in sorted(Path(parquet_dir).glob("*.parquet")):
            try:
                n = load_indicators(conn, pq_file)
                summary["indicators_loaded"] += n
                summary["files_processed"] += 1
            except Exception as exc:
                log.error("load_failed", file=str(pq_file), error=str(exc))
                raise

    log.info("warehouse_load_complete", **summary)
    return summary
