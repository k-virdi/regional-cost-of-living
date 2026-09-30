# src/extractors/bls.py
"""US Bureau of Labor Statistics Public Data API v2 extractor.

The BLS API v2 supports up to 50 series per POST request for registered
users, and returns up to 20 years of data per call. For history going back
to 1975, we paginate across 20-year windows.

Reference: https://www.bls.gov/developers/api_signature_v2.htm
"""

import os
from typing import Any

import pandas as pd

from src.extractors.base import BaseExtractor
from src.utils.logger import get_logger

log = get_logger(__name__)

BLS_BASE = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
MAX_YEARS_PER_REQUEST = 20


class BLSExtractor(BaseExtractor):
    """Extract US economic time series from the BLS Public Data API v2."""

    def __init__(self, base_url: str = BLS_BASE):
        super().__init__(base_url)
        self.api_key = os.getenv("BLS_API_KEY")
        if not self.api_key:
            log.warning(
                "bls_api_key_missing",
                detail="No BLS_API_KEY set; falling back to unregistered limits "
                       "(25 series/day, 10 years/history).",
            )

    def fetch_series(
        self,
        series_ids: list[str],
        start_year: int,
        end_year: int,
    ) -> list[dict[str, Any]]:
        """Fetch one or more BLS series across a year range.

        Paginates internally in 20-year chunks because BLS v2 caps each
        request at 20 years of history.

        Returns a flat list of observation dicts:
            {series_id, year, period, period_name, value, footnotes}
        """
        all_observations: list[dict[str, Any]] = []

        for window_start in range(start_year, end_year + 1, MAX_YEARS_PER_REQUEST):
            window_end = min(window_start + MAX_YEARS_PER_REQUEST - 1, end_year)
            log.info(
                "bls_fetch_window",
                series_count=len(series_ids),
                start=window_start,
                end=window_end,
            )
            payload: dict[str, Any] = {
                "seriesid": series_ids,
                "startyear": str(window_start),
                "endyear": str(window_end),
            }
            if self.api_key:
                payload["registrationkey"] = self.api_key

            resp = self.post(json_body=payload)
            data = resp.json()

            if data.get("status") != "REQUEST_SUCCEEDED":
                messages = data.get("message", [])
                log.error("bls_request_failed", messages=messages)
                raise RuntimeError(f"BLS API error: {messages}")

            for series in data.get("Results", {}).get("series", []):
                sid = series["seriesID"]
                for obs in series.get("data", []):
                    all_observations.append(
                        {
                            "series_id": sid,
                            "year": obs["year"],
                            "period": obs["period"],
                            "period_name": obs.get("periodName", ""),
                            "value": obs["value"],
                            "footnotes": obs.get("footnotes", []),
                        }
                    )

        log.info("bls_fetch_complete", observations=len(all_observations))
        return all_observations

    def to_dataframe(self, observations: list[dict[str, Any]]) -> pd.DataFrame:
        """Convert BLS observation dicts into a tidy DataFrame."""
        df = pd.DataFrame(observations)
        if df.empty:
            return df
        # Convert BLS "M01".."M12" period codes to month numbers
        df["month"] = (
            df["period"].astype(str).str.replace("M", "", regex=False).astype(int)
        )
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["date"] = pd.to_datetime(
            df[["year", "month"]].assign(day=1)
        )
        return df

    def download_all(self, series_config: dict) -> dict[str, pd.DataFrame]:
        """Download every series declared in the sources config.

        Args:
            series_config: Mapping of logical name -> {series_id, start_year, ...}.

        Returns:
            Mapping of logical name -> DataFrame.
        """
        results: dict[str, pd.DataFrame] = {}
        for logical_name, meta in series_config.items():
            try:
                obs = self.fetch_series(
                    [meta["series_id"]],
                    start_year=meta["start_year"],
                    end_year=pd.Timestamp.now().year,
                )
                results[logical_name] = self.to_dataframe(obs)
            except Exception as exc:
                log.error("bls_download_failed", series=logical_name, error=str(exc))
                raise
        return results
