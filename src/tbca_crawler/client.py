from __future__ import annotations

import logging
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .constants import BASE_URL


logger = logging.getLogger(__name__)


class TBCAClient:
    def __init__(
        self,
        base_url: str = BASE_URL,
        delay: float = 1.0,
        timeout: tuple[float, float] = (5.0, 30.0),
        max_retries: int = 4,
        backoff_factor: float = 1.0,
    ) -> None:
        
        if delay < 0:
            raise ValueError("delay não pode ser negativo")

        if max_retries < 0:
            raise ValueError("max_retries não pode ser negativo")

        if backoff_factor < 0:
            raise ValueError("backoff_factor não pode ser negativo")

        self.base_url = base_url.rstrip("/") + "/"
        self.delay = delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        self.session = self._create_session()
        self._last_request_finished_at: float | None = None


    
    def _create_session(self) -> requests.Session:
        session = requests.Session()

        session.headers.update(
            {
                "User-Agent": (
                    "TBCADataCollector/1.0 (Python requests)"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,*/*;q=0.8"
                ),
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            }
        )

        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)

        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session


    def _wait_before_request(self) -> None:
        if self._last_request_finished_at is None:
            return

        elapsed = time.monotonic() - self._last_request_finished_at
        remaining = self.delay - elapsed

        if remaining > 0:
            time.sleep(remaining)

    def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> requests.Response:
        self._wait_before_request()

        logger.info(f"Executando requisição {method.upper()} {url}")

        try:
            response = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **kwargs,
            )

            response.raise_for_status()

            return response
        finally:
            self._last_request_finished_at = time.monotonic()

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        return self.request("POST", url, **kwargs)

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> TBCAClient:
        return self

    def __exit__(
        self,
        exception_type: object,
        exception_value: object,
        traceback: object,
    ) -> None:
        self.close()
