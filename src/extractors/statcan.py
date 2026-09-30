# src/extractors/statcan.py
"""Statistics Canada Web Data Service extractor.

Uses the bulk CSV download endpoint for full table history. Statistics
Canada PIDs are permanent identifiers visible in the table URL, and the
CSV endpoint returns the complete historical series — the most reliable
path for time-series data going back to 1975.

Reference: https://www.statcan.gc.ca/eng/developers/wds
"""

import io
from pathlib import Path

import pandas as pd

from src.extractors.base import BaseExtractor
from src.utils.logger import get_logger

log = get_logger(__name__)


class StatCanExtractor(BaseExtractor):
    """Extract Statistics Canada tables via bulk CSV download.

    The bulk endpoint follows the pattern:
        https://www150.statcan.gc.ca/t1/tbl1/en/dtblDownload/{pid}/download/{pid}.csv
    """

    def __init__(self, base_url: str = "https://www150.statcan.gc.ca/t1/tbl1/en"):
        super().__init__(base_url)

    def download_table(self, pid: str) -> pd.DataFrame:
        """Download a full Statistics Canada table as a DataFrame.

        Args:
            pid: Statistics Canada Product ID, e.g. "18100004" for CPI.

        Returns:
            DataFrame with raw StatCan columns (REF_DATE, GEO, VALUE, etc.).
        """
        path = f"dtblDownload/{pid}/download/{pid}.csv"
        log.info("statcan_download_start", pid=pid)

        resp = self.get(path)
        df = pd.read_csv(
            io.BytesIO(resp.content),
            encoding="latin-1",
            low_memory=False,
        )
        log.info("statcan_download_complete", pid=pid, rows=len(df), cols=len(df.columns))
        return df

    def download_all(self, tables: dict) -> dict[str, pd.DataFrame]:
        """Download every table declared in the sources config.

        Args:
            tables: Mapping of logical name -> {pid, name, ...}.

        Returns:
            Mapping of logical name -> raw DataFrame.
        """
        results: dict[str, pd.DataFrame] = {}
        for logical_name, meta in tables.items():
            try:
                df = self.download_table(meta["pid"])
                results[logical_name] = df
            except Exception as exc:
                log.error("statcan_download_failed", table=logical_name, error=str(exc))
                raise
        return results

    def filter_by_geography(self, df: pd.DataFrame, geographies: list[str]) -> pd.DataFrame:
        """Keep only rows whose GEO is in the requested geography list."""
        if "GEO" not in df.columns:
            return df
        mask = df["GEO"].isin(geographies)
        filtered = df.loc[mask].copy()
        log.info("statcan_filtered", original=len(df), filtered=len(filtered))
        return filtered

    def filter_by_year(self, df: pd.DataFrame, start_year: int) -> pd.DataFrame:
        """Keep rows with REF_DATE >= start_year."""
        if "REF_DATE" not in df.columns:
            return df
        df = df.copy()
        df["year"] = pd.to_numeric(
            df["REF_DATE"].astype(str).str[:4], errors="coerce"
        )
        return df.loc[df["year"] >= start_year].copy()
