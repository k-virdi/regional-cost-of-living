# src/extractors/base.py
"""Shared HTTP client with exponential backoff and structured logging."""

from typing import Any, Optional

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from src.utils.logger import get_logger

log = get_logger(__name__)


class BaseExtractor:
    """Base class providing a resilient HTTP session.

    All concrete extractors inherit from this and call ``self.get`` or
    ``self.post`` rather than using ``requests`` directly.
    """

    def __init__(self, base_url: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "regional-cost-of-living/0.1 "
                    "(research; contact: your-email@example.com)"
                )
            }
        )

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=120),
        retry=retry_if_exception_type(
            (requests.ConnectionError, requests.Timeout, requests.HTTPError)
        ),
        before_sleep=before_sleep_log(log, "WARNING"),
        reraise=True,
    )
    def get(self, path: str = "", params: Optional[dict] = None, **kwargs) -> requests.Response:
        """Perform a GET request with automatic retries."""
        url = f"{self.base_url}/{path.lstrip('/')}" if path else self.base_url
        log.debug("http_get", url=url, params=params)
        resp = self.session.get(url, params=params, timeout=self.timeout, **kwargs)
        resp.raise_for_status()
        return resp

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=120),
        retry=retry_if_exception_type(
            (requests.ConnectionError, requests.Timeout, requests.HTTPError)
        ),
        before_sleep=before_sleep_log(log, "WARNING"),
        reraise=True,
    )
    def post(self, path: str = "", json_body: Optional[dict] = None, **kwargs) -> requests.Response:
        """Perform a POST request with automatic retries."""
        url = f"{self.base_url}/{path.lstrip('/')}" if path else self.base_url
        log.debug("http_post", url=url)
        resp = self.session.post(url, json=json_body, timeout=self.timeout, **kwargs)
        resp.raise_for_status()
        return resp

    def close(self) -> None:
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
