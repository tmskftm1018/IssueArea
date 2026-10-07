import json
import logging
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from app.collector import collect_source
from app.db import utcnow
from app.models import CollectionRun
from app.newsdata import ENDPOINT, LOCAL_TITLE_QUERY, NewsDataSourceAdapter
from app.source_registry import add_source, review_source, set_enabled
from tests.test_registry import review


def source(session):
    return add_source(
        session, "NewsData.io 무료", ENDPOINT, "https://newsdata.io/terms", 10, "newsdata"
    )


def payload():
    return {
        "status": "success",
        "nextPage": "DO_NOT_FETCH",
        "results": [
            {
                "article_id": "korean-1",
                "title": "<b>서울</b> 교통 안내",
                "link": "https://publisher.example/news/1",
                "source_name": "테스트 언론사",
                "pubDate": (utcnow() - timedelta(hours=13)).strftime("%Y-%m-%d %H:%M:%S"),
                "pubDateTZ": "UTC",
                "category": ["politics"],
                "content": "DO_NOT_STORE",
                "image_url": "DO_NOT_FETCH",
            }
        ],
    }


def test_single_request_metadata_and_api_attribution(session, client):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["X-ACCESS-KEY"] == "secret"
        assert "secret" not in str(request.url)
        assert dict(request.url.params) == {
            "country": "kr",
            "language": "ko",
            "qInTitle": LOCAL_TITLE_QUERY,
            "category": "politics,business,crime,domestic,technology",
            "size": "10",
        }
        return httpx.Response(200, json=payload())

    s = source(session)
    review_source(session, s.id, review())
    s.enabled = True
    session.commit()
    adapter = NewsDataSourceAdapter("secret", httpx.MockTransport(handler))
    run = collect_source(session, s, adapter)
    assert run.inserted_count == 1 and len(calls) == 1
    item = client.get("/api/v1/news").json()["items"][0]
    assert item["source"] == "테스트 언론사"
    assert "delivery_delay_hours" not in item
    assert "DO_NOT_STORE" not in str(item)
    assert collect_source(session, s, adapter).duplicate_count == 1


@pytest.mark.parametrize("status", [401, 403, 429, 500, 302])
def test_http_failure_no_retry_or_key_logging(session, status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"status": "error", "results": {"message": "secret"}})

    s = source(session)
    s.enabled = s.title_display_allowed = s.metadata_storage_allowed = True
    s.rights_status = "allowed"
    session.commit()
    run = collect_source(session, s, NewsDataSourceAdapter("secret", httpx.MockTransport(handler)))
    assert run.status == "failed" and len(calls) == 1
    assert "secret" not in run.error_message
    if status == 429:
        stamp = s.next_fetch_at.replace(tzinfo=utcnow().tzinfo)
        assert stamp >= utcnow() + timedelta(hours=23)


def test_free_quota_guard_and_registry(session, caplog):
    s = source(session)
    review_source(session, s.id, review())
    with pytest.raises(ValueError):
        set_enabled(session, s.id, True)
    with pytest.raises(ValueError):
        source(session)
    s.enabled = True
    session.add_all([CollectionRun(source_id=s.id, status="failed") for _ in range(180)])
    session.commit()

    class NeverCall:
        def fetch(self, source):
            pytest.fail("Local budget should prevent network calls")

    with caplog.at_level(logging.WARNING, logger="collector"):
        assert collect_source(session, s, NeverCall()) is None
    assert len(list(session.scalars(select(CollectionRun)))) == 180
    message = next(record.message for record in caplog.records if record.name == "collector")
    event = json.loads(message)
    assert event["event"] == "quota_deferred"
    assert event["reason"] == "daily_request_limit"
    assert event["retry_delay_seconds"] == 86400
    assert event["source"] == s.id


def test_bad_response_rejected():
    for data in [
        {"status": "error"},
        {"status": "success", "results": [{}]},
        {"status": "success", "results": [payload()["results"][0]] * 11},
    ]:
        adapter = NewsDataSourceAdapter(
            "secret", httpx.MockTransport(lambda r: httpx.Response(200, json=data))
        )
        with pytest.raises((ValueError, KeyError)):
            adapter.fetch(None)
