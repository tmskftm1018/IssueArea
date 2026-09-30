import hashlib
import hmac
import json
from datetime import timedelta

import httpx
import pytest

from app.db import utcnow
from app.newswire import NewswireSourceAdapter, parse_events, signature


def event(action="insert", pid=1, newsid=10, **extra):
    return {
        "pid": pid,
        "newsid": newsid,
        "action": action,
        "title": "서울 기술 행사",
        "url": "https://www.newswire.co.kr/newsRead.php?no=10",
        "press_time": utcnow().isoformat(),
        "content": "DISCARD BODY",
        "photo": [{"url": "x"}],
        **extra,
    }


def test_official_hmac_algorithm():
    import base64

    expected = base64.b64encode(
        hmac.new(b"key", b"/api/v1/request123", hashlib.sha256).digest()
    ).decode()
    assert signature("key", "/api/v1/request", "123") == expected


def test_metadata_only_and_order():
    entries = parse_events({"news": [event(), event("update", 2), event("delete", 3)]})
    assert [e.action for e in entries] == ["insert", "update", "delete"]
    assert "DISCARD BODY" not in str(entries)
    assert not hasattr(entries[0], "content") and not hasattr(entries[0], "photo")


@pytest.mark.parametrize(
    "rows",
    [
        [event(pid=2), event(pid=1)],
        [event(action="other")],
        [event(newsid="10")],
        [event(press_time="2026-09-30T09:00:00")],
        [event(url="javascript:alert(1)")],
    ],
)
def test_invalid_event_rejected(rows):
    with pytest.raises(ValueError):
        parse_events({"news": rows})


def test_future_press_time_preserved_for_embargo():
    future = utcnow() + timedelta(days=1)
    assert parse_events({"news": [event(press_time=future.isoformat())]})[0].published_at == future


def test_authenticated_two_step_api():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith("request"):
            assert json.loads(request.content) == {"partner_id": 123}
            stamp = request.headers["X-Timestamp"]
            assert len(stamp) == 13
            assert request.headers["X-HMAC"] == signature("test-only-key", request.url.path, stamp)
            return httpx.Response(
                200,
                json={
                    "statuscode": 200,
                    "status": "processing",
                    "matched_count": 1,
                    "request_id": "REQ-test",
                },
            )
        assert "X-HMAC" not in request.headers
        assert json.loads(request.content) == {"request_id": "REQ-test"}
        return httpx.Response(200, json={"statuscode": 200, "matched_count": 1, "news": [event()]})

    result = NewswireSourceAdapter(123, "test-only-key", httpx.MockTransport(handler)).fetch(None)
    assert len(result.entries) == 1 and paths == ["/api/v1/request", "/api/v1/send"]


def test_missing_key(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "newswire_partner_id", None)
    monkeypatch.setattr(settings, "newswire_api_key", None)
    with pytest.raises(ValueError):
        NewswireSourceAdapter().fetch(None)


def test_empty_api_does_not_send():
    def handler(request):
        assert request.url.path.endswith("request")
        return httpx.Response(
            200, json={"statuscode": 200, "matched_count": 0, "status": "completed"}
        )

    result = NewswireSourceAdapter(123, "key", httpx.MockTransport(handler)).fetch(None)
    assert result.entries == []


@pytest.mark.parametrize("status", [401, 403, 500, 302])
def test_partner_http_errors(status):
    adapter = NewswireSourceAdapter(
        123,
        "key",
        httpx.MockTransport(
            lambda request: httpx.Response(status, headers={"Location": "https://other.example"})
        ),
    )
    with pytest.raises(httpx.HTTPStatusError):
        adapter.fetch(None)
