# src/loaders/parquet_loader.py
"""Persist validated IndicatorRecords to local Parquet files.

Layer 2 (PostgreSQL warehouse) will consume these Parquet files. Writing
to Parquet now gives us a durable, columnar staging layer that is cheap
to re-read and easy to inspect.
"""

from pathlib import Path

import pandas as pd

from src.transformers.schema import IndicatorRecord
from src.utils.logger import get_logger

log = get_logger(__name__)


def records_to_dataframe(records: list[IndicatorRecord]) -> pd.DataFrame:
    """Convert validated Pydantic records into a flat DataFrame."""
    rows = [r.model_dump() for r in records]
    df = pd.DataFrame(rows)
    if not df.empty:
        df["reference_date"] = pd.to_datetime(df["reference_date"])
        df["value"] = df["value"].astype(float)
    return df


def write_parquet(
    df: pd.DataFrame,
    output_dir: Path,
    name: str,
) -> Path:
    """Write a DataFrame to a Parquet file, partitioned by country."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}.parquet"

    if df.empty:
        log.warning("parquet_write_skipped_empty", name=name)
        return path

    df.to_parquet(path, index=False, engine="pyarrow")
    log.info("parquet_written", path=str(path), rows=len(df))
    return path
