# src/extractors/census.py
"""US Census Bureau API extractor for ACS economic indicators.

Uses the American Community Survey 5-year estimates API:
    https://api.census.gov/data/{year}/acs/acs5?get=B19013_001E&for=state:*
"""

import os
from typing import Any

import pandas as pd

from src.extractors.base import BaseExtractor
from src.utils.logger import get_logger

log = get_logger(__name__)

CENSUS_BASE = "https://api.census.gov/data"


class CensusExtractor(BaseExtractor):
    """Extract US state-level economic indicators from the Census ACS API."""

    def __init__(self, base_url: str = CENSUS_BASE):
        super().__init__(base_url)
        self.api_key = os.getenv("CENSUS_API_KEY")
        if not self.api_key:
            log.warning(
                "census_api_key_missing",
                detail="No CENSUS_API_KEY set; requests may be rate-limited.",
            )

    def fetch_acs(
        self,
        year: int,
        variables: list[str],
        geography: str = "state:*",
    ) -> pd.DataFrame:
        """Fetch ACS 5-year estimates for the given variables and year.

        Args:
            year: ACS survey year (e.g. 2023).
            variables: List of variable codes (e.g. ["B19013_001E"]).
            geography: Census geography clause (e.g. "state:*").

        Returns:
            DataFrame with one column per requested variable plus geography.
        """
        path = f"{year}/acs/acs5"
        params = {
            "get": ",".join(["NAME"] + variables),
            "for": geography,
        }
        if self.api_key:
            params["key"] = self.api_key

        log.info("census_fetch_start", year=year, variables=variables)
        resp = self.get(path, params=params)
        raw = resp.json()

        # Census returns a list of lists: first row is headers
        headers, *rows = raw
        df = pd.DataFrame(rows, columns=headers)
        df["acs_year"] = year
        log.info("census_fetch_complete", year=year, rows=len(df))
        return df

    def download_all(self, config: dict) -> dict[int, pd.DataFrame]:
        """Download all configured years and variables.

        Args:
            config: The ``census`` block from sources.yaml.

        Returns:
            Mapping of year -> DataFrame.
        """
        variable_codes = list(config["variables"].values())
        results: dict[int, pd.DataFrame] = {}

        for year in config["years"]:
            try:
                df = self.fetch_acs(
                    year=year,
                    variables=variable_codes,
                    geography=config.get("geography", "state:*"),
                )
                results[year] = df
            except Exception as exc:
                log.error("census_download_failed", year=year, error=str(exc))
                # Census ACS 5-year data may not exist for every year; continue
                continue

        return results

    def to_dataframe(self, yearly_frames: dict[int, pd.DataFrame]) -> pd.DataFrame:
        """Concatenate yearly frames into a single tidy DataFrame."""
        if not yearly_frames:
            return pd.DataFrame()
        return pd.concat(yearly_frames.values(), ignore_index=True)
