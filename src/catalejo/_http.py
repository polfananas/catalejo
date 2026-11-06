"""Polite HTTP client for cnmv.es.

Everything catalejo downloads goes through here, so the rules for being a
good citizen live in one place:

* identifiable User-Agent,
* at most one request per ``min_interval`` seconds,
* on-disk cache so repeated calls don't hit the CNMV again,
* a few retries with backoff on 429/5xx and network errors,
* only *.cnmv.es hosts are allowed.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from catalejo import __version__

USER_AGENT = f"catalejo/{__version__} (+https://github.com/polfananas/catalejo)"
ALLOWED_HOST_SUFFIX = "cnmv.es"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class CatalejoHTTPError(RuntimeError):
    """Raised when the CNMV can't be reached or keeps answering with errors."""


@dataclass(frozen=True)
class Response:
    url: str
    status_code: int
    content: bytes
    content_type: str
    from_cache: bool = False

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


def default_cache_dir() -> Path:
    env = os.environ.get("CATALEJO_CACHE_DIR")
    if env:
        return Path(env)
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "catalejo"


class HttpClient:
    def __init__(
        self,
        *,
        cache_dir: Path | None = None,
        cache_ttl: float = 3600.0,
        min_interval: float = 1.0,
        max_retries: int = 3,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cache_dir = cache_dir if cache_dir is not None else default_cache_dir()
        self.cache_ttl = cache_ttl
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )

    # -- public -----------------------------------------------------------

    def get(
        self,
        url: str,
        params: Mapping[str, str | int] | None = None,
        *,
        use_cache: bool = True,
    ) -> Response:
        _check_host(url)
        key = _cache_key(url, params)

        if use_cache and self.cache_ttl > 0:
            cached = self._read_cache(key)
            if cached is not None:
                return cached

        response = self._fetch(url, params)
        if use_cache and self.cache_ttl > 0:
            self._write_cache(key, response)
        return response

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- internals --------------------------------------------------------

    def _throttle(self) -> None:
        if self._last_request is not None:
            wait = self.min_interval - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._clock()

    def _fetch(self, url: str, params: Mapping[str, str | int] | None) -> Response:
        last_error: str = ""
        for attempt in range(self.max_retries + 1):
            if attempt:
                self._sleep(min(2**attempt, 30))
            self._throttle()
            try:
                r = self._client.get(url, params=dict(params) if params else None)
            except httpx.TransportError as e:
                last_error = f"{type(e).__name__}: {e}"
                continue

            if r.status_code in RETRY_STATUSES:
                last_error = f"HTTP {r.status_code}"
                retry_after = r.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    self._sleep(min(int(retry_after), 60))
                continue
            if r.status_code >= 400:
                raise CatalejoHTTPError(f"HTTP {r.status_code} for {r.url}")

            return Response(
                url=str(r.url),
                status_code=r.status_code,
                content=r.content,
                content_type=r.headers.get("Content-Type", ""),
            )

        raise CatalejoHTTPError(
            f"giving up on {url} after {self.max_retries + 1} attempts ({last_error})"
        )

    def _read_cache(self, key: str) -> Response | None:
        meta_path = self.cache_dir / f"{key}.json"
        body_path = self.cache_dir / f"{key}.bin"
        try:
            meta = json.loads(meta_path.read_text())
            if time.time() - meta["fetched_at"] > self.cache_ttl:
                return None
            content = body_path.read_bytes()
        except (OSError, ValueError, KeyError):
            return None
        return Response(
            url=meta["url"],
            status_code=meta["status_code"],
            content=content,
            content_type=meta["content_type"],
            from_cache=True,
        )

    def _write_cache(self, key: str, response: Response) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / f"{key}.bin").write_bytes(response.content)
            meta = {
                "url": response.url,
                "status_code": response.status_code,
                "content_type": response.content_type,
                "fetched_at": time.time(),
            }
            (self.cache_dir / f"{key}.json").write_text(json.dumps(meta))
        except OSError:
            pass  # a broken cache shouldn't break the request


def _check_host(url: str) -> None:
    host = (urlsplit(url).hostname or "").lower()
    if host != ALLOWED_HOST_SUFFIX and not host.endswith("." + ALLOWED_HOST_SUFFIX):
        raise ValueError(f"catalejo only talks to cnmv.es, got {host!r}")


def _cache_key(url: str, params: Mapping[str, str | int] | None) -> str:
    items = sorted((k, str(v)) for k, v in (params or {}).items())
    raw = url + "?" + "&".join(f"{k}={v}" for k, v in items)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
