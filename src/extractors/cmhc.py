# src/extractors/cmhc.py
"""Canada Mortgage and Housing Corporation (CMHC) data extractor.

CMHC publishes rental market data through the Open Government Portal,
which exposes a CKAN API for programmatic dataset discovery and resource
download. This extractor resolves package IDs to CSV resource URLs and
downloads them.

Reference: https://open.canada.ca/data/en/dataset
CKAN API:  https://docs.ckan.org/en/2.10/api/
"""

import io
from typing import Any

import pandas as pd

from src.extractors.base import BaseExtractor
from src.utils.logger import get_logger

log = get_logger(__name__)

CKAN_BASE = "https://open.canada.ca/data/api/3/action"


class CMHCExtractor(BaseExtractor):
    """Extract CMHC rental market datasets via the CKAN Open Data API."""

    def __init__(self, base_url: str = CKAN_BASE):
        super().__init__(base_url)

    def resolve_package(self, package_id: str) -> dict[str, Any]:
        """Resolve a CKAN package ID to its metadata and resource list."""
        path = "package_show"
        resp = self.get(path, params={"id": package_id})
        payload = resp.json()
        if not payload.get("success"):
            raise RuntimeError(f"CKAN package_show failed for {package_id}")
        return payload["result"]

    def find_csv_resource(self, package: dict, fmt: str = "CSV") -> dict | None:
        """Find the first resource of the requested format in a package."""
        for resource in package.get("resources", []):
            if resource.get("format", "").upper() == fmt.upper():
                return resource
        return None

    def download_resource(self, resource_url: str) -> pd.DataFrame:
        """Download a CSV resource directly (bypassing CKAN base URL)."""
        import requests

        log.info("cmhc_download_start", url=resource_url)
        resp = requests.get(resource_url, timeout=120)
        resp.raise_for_status()
        df = pd.read_csv(io.BytesIO(resp.content), low_memory=False)
        log.info("cmhc_download_complete", rows=len(df))
        return df

    def download_all(self, datasets: dict) -> dict[str, pd.DataFrame]:
        """Download every CMHC dataset declared in the sources config."""
        results: dict[str, pd.DataFrame] = {}
        for logical_name, meta in datasets.items():
            try:
                package = self.resolve_package(meta["package_id"])
                resource = self.find_csv_resource(
                    package, fmt=meta.get("resource_format", "CSV")
                )
                if resource is None:
                    log.warning("cmhc_resource_not_found", dataset=logical_name)
                    continue
                results[logical_name] = self.download_resource(resource["url"])
            except Exception as exc:
                log.error("cmhc_download_failed", dataset=logical_name, error=str(exc))
                continue
        return results
