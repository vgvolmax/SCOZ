import json

import httpx
import pytest
from pydantic import SecretStr

from backend.domain.benchmark_selection import (
    MPStatsAuthError,
    MPStatsMalformedResponseError,
    MPStatsNetworkError,
    MPStatsPendingError,
    MPStatsRateLimitError,
    MPStatsTimeoutError,
    MPStatsUpstreamError,
    PhotoStatus,
)
from backend.sources.mpstats import MPStatsClient


def client(handler):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return http, MPStatsClient(http)


def test_mpstats_request_contract_and_ignored_fields():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"data": [
            {"id": 123, "thumb": "https://img.example/1.jpg", "sales": "SECRET"},
            {"id": 456, "thumb": None, "brand": "ignored"},
            {"id": 999, "thumb": "https://img.example/x.jpg"},
        ]})
    http, source = client(handler)
    with http:
        result = source.get_ozon_product_previews(SecretStr("sentinel"), ("123", "456"))
    assert [(x.ozon_product_id, x.photo_status, x.photo_url) for x in result] == [
        ("123", PhotoStatus.AVAILABLE, "https://img.example/1.jpg"),
        ("456", PhotoStatus.MISSING, None),
    ]
    request = requests[0]
    assert request.method == "POST"
    assert request.url.path == "/api/analytics/v1/oz/items"
    assert request.url.params["ids"] == "123,456"
    assert request.headers["X-Mpstats-TOKEN"] == "sentinel"
    assert request.content == b""
    assert "sentinel" not in str(request.url)


def test_mpstats_chunks_at_100_and_preserves_caller_order():
    calls = []
    ids = tuple(str(i) for i in range(205, 0, -1))
    def handler(request):
        chunk = request.url.params["ids"].split(",")
        calls.append(chunk)
        return httpx.Response(200, json={"data": [{"id": int(i), "thumb": None} for i in reversed(chunk)]})
    http, source = client(handler)
    with http:
        result = source.get_ozon_product_previews(SecretStr("x"), ids)
    assert [x.ozon_product_id for x in result] == list(ids)
    assert [len(x) for x in calls] == [100, 100, 5]


def test_mpstats_empty_ids_make_no_request():
    http, source = client(lambda request: pytest.fail("unexpected request"))
    with http:
        assert source.get_ozon_product_previews(SecretStr("x"), ()) == ()


def test_mpstats_missing_thumb_and_id_are_missing():
    http, source = client(lambda request: httpx.Response(200, json={"data": [{"id": 1, "thumb": ""}]}))
    with http:
        result = source.get_ozon_product_previews(SecretStr("x"), ("1", "2"))
    assert [x.photo_status for x in result] == [PhotoStatus.MISSING, PhotoStatus.MISSING]


def test_mpstats_ignores_unrequested_rows_before_thumb_validation():
    http, source = client(lambda request: httpx.Response(200, json={"data": [
        {"id": 999}, {"id": 998, "thumb": {"malformed": True}}, {"id": 1, "thumb": None}
    ]}))
    with http:
        assert source.get_ozon_product_previews(SecretStr("x"), ("1",))[0].photo_status is PhotoStatus.MISSING


@pytest.mark.parametrize("payload", [[], {}, {"data": {}}, {"data": [None]}, {"data": [{"id": True, "thumb": None}]}, {"data": [{"id": 1, "thumb": "http://bad"}]}, {"data": [{"id": 1, "thumb": None}, {"id": 1, "thumb": None}]}])
def test_mpstats_rejects_malformed_response_shapes(payload):
    http, source = client(lambda request: httpx.Response(200, content=json.dumps(payload)))
    with http, pytest.raises(MPStatsMalformedResponseError):
        source.get_ozon_product_previews(SecretStr("x"), ("1",))


@pytest.mark.parametrize("status,error", [(202, MPStatsPendingError), (401, MPStatsAuthError), (403, MPStatsUpstreamError), (500, MPStatsUpstreamError)])
def test_mpstats_maps_every_http_status(status, error):
    http, source = client(lambda request: httpx.Response(status))
    with http, pytest.raises(error):
        source.get_ozon_product_previews(SecretStr("x"), ("1",))
    http, source = client(lambda request: httpx.Response(429, headers={"Retry-After": "42"}))
    with http, pytest.raises(MPStatsRateLimitError) as raised:
        source.get_ozon_product_previews(SecretStr("x"), ("1",))
    assert raised.value.retry_after_seconds == 42


@pytest.mark.parametrize("exc,error", [(httpx.ReadTimeout("x"), MPStatsTimeoutError), (httpx.ConnectError("x"), MPStatsNetworkError)])
def test_mpstats_maps_timeout_and_network_errors(exc, error):
    http, source = client(lambda request: (_ for _ in ()).throw(exc))
    with http, pytest.raises(error):
        source.get_ozon_product_previews(SecretStr("x"), ("1",))


def test_mpstats_probe_accepts_valid_empty_data():
    http, source = client(lambda request: httpx.Response(200, json={"data": []}))
    with http:
        assert source.test_connection(SecretStr("x"), "1").status.value == "AVAILABLE"
