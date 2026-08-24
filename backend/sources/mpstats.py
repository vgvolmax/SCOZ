from urllib.parse import urlparse

import httpx
from pydantic import SecretStr

from backend.domain.benchmark_selection import (
    MPStatsAuthError,
    MPStatsConnectionResult,
    MPStatsConnectionStatus,
    MPStatsMalformedResponseError,
    MPStatsNetworkError,
    MPStatsPendingError,
    MPStatsProductPreview,
    MPStatsRateLimitError,
    MPStatsTimeoutError,
    MPStatsUpstreamError,
    PhotoStatus,
)


class MPStatsClient:
    def __init__(
        self,
        client: httpx.Client,
        *,
        base_url: str = "https://mpstats.io",
        timeout: httpx.Timeout = httpx.Timeout(15.0, connect=5.0),
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("MPStats base URL must be absolute HTTPS")
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def get_ozon_product_previews(
        self, token: SecretStr, ids: tuple[str, ...]
    ) -> tuple[MPStatsProductPreview, ...]:
        if len(ids) != len(set(ids)) or any(not _canonical_id(item) for item in ids):
            raise ValueError("ids must be unique canonical positive decimal strings")
        if not ids:
            return ()
        found: dict[str, str | None] = {}
        for index in range(0, len(ids), 100):
            chunk = ids[index : index + 100]
            response = self._request(token, chunk)
            for item_id, thumb in self._parse(response, frozenset(chunk)).items():
                if item_id in found:
                    raise MPStatsMalformedResponseError()
                found[item_id] = thumb
        return tuple(
            MPStatsProductPreview(
                ozon_product_id=item_id,
                photo_status=(PhotoStatus.AVAILABLE if found.get(item_id) else PhotoStatus.MISSING),
                photo_url=found.get(item_id),
            )
            for item_id in ids
        )

    def test_connection(
        self, token: SecretStr, ozon_product_id: str
    ) -> MPStatsConnectionResult:
        self.get_ozon_product_previews(token, (ozon_product_id,))
        return MPStatsConnectionResult(status=MPStatsConnectionStatus.AVAILABLE)

    def _request(self, token: SecretStr, ids: tuple[str, ...]) -> httpx.Response:
        try:
            response = self._client.post(
                f"{self._base_url}/api/analytics/v1/oz/items",
                params={"ids": ",".join(ids)},
                headers={"X-Mpstats-TOKEN": token.get_secret_value()},
                timeout=self._timeout,
                follow_redirects=False,
            )
        except httpx.TimeoutException:
            raise MPStatsTimeoutError() from None
        except httpx.RequestError:
            raise MPStatsNetworkError() from None
        if response.status_code == 202:
            raise MPStatsPendingError()
        if response.status_code == 401:
            raise MPStatsAuthError()
        if response.status_code == 429:
            raise MPStatsRateLimitError(_safe_retry_after(response.headers.get("Retry-After")))
        if response.status_code != 200:
            raise MPStatsUpstreamError()
        return response

    @staticmethod
    def _parse(response: httpx.Response, requested: frozenset[str]) -> dict[str, str | None]:
        try:
            payload = response.json()
        except (ValueError, TypeError):
            raise MPStatsMalformedResponseError() from None
        if not isinstance(payload, dict) or "data" not in payload or not isinstance(payload["data"], list):
            raise MPStatsMalformedResponseError()
        result: dict[str, str | None] = {}
        for item in payload["data"]:
            if not isinstance(item, dict) or "id" not in item:
                raise MPStatsMalformedResponseError()
            raw_id = item["id"]
            if isinstance(raw_id, bool) or not isinstance(raw_id, int) or raw_id <= 0:
                raise MPStatsMalformedResponseError()
            item_id = str(raw_id)
            if item_id not in requested:
                continue
            if "thumb" not in item:
                raise MPStatsMalformedResponseError()
            thumb = item["thumb"]
            if thumb is not None and not isinstance(thumb, str):
                raise MPStatsMalformedResponseError()
            if isinstance(thumb, str):
                if thumb == "":
                    thumb = None
                elif not _approved_photo_url(thumb):
                    raise MPStatsMalformedResponseError()
            if item_id in result:
                raise MPStatsMalformedResponseError()
            result[item_id] = thumb
        return result


def _canonical_id(value: str) -> bool:
    return value.isascii() and value.isdigit() and int(value) > 0 and str(int(value)) == value


def _approved_photo_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password


def _safe_retry_after(value: str | None) -> int | None:
    if value is None or not value.isascii() or not value.isdigit():
        return None
    parsed = int(value)
    return parsed if 0 <= parsed <= 86_400 else None
