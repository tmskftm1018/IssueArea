from datetime import timedelta

from sqlalchemy import select

from app.collector import collect_source
from app.db import utcnow
from app.models import Article, Source
from app.sources import Entry, FetchResult


class Adapter:
    def __init__(self, entries):
        self.entries = entries

    def fetch(self, source):
        return FetchResult(self.entries)


def partner(session):
    source = Source(
        name="뉴스와이어 테스트",
        adapter_type="newswire",
        enabled=True,
        rights_status="allowed",
        title_display_allowed=True,
        metadata_storage_allowed=True,
    )
    session.add(source)
    session.commit()
    return source


def entry(title="서울 교육 발표", key="1", action="insert", stamp=None):
    return Entry(
        title,
        f"https://www.newswire.co.kr/newsRead.php?no={key}",
        key,
        stamp or utcnow(),
        action=action,
    )


def test_update_reclassifies_and_delete_removes_aggregates(session, client):
    source = partner(session)
    assert collect_source(session, source, Adapter([entry()])).inserted_count == 1
    article_id = session.scalar(select(Article.id))
    assert client.get("/api/v1/news?region=KR-11").json()["total"] == 1
    run = collect_source(session, source, Adapter([entry("부산 태풍 안내", action="update")]))
    assert run.updated_count == 1 and run.inserted_count == 0
    data = client.get("/api/v1/news?region=KR-26&topics=weather").json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == article_id
    assert data["items"][0]["content_type"] == "press_release"
    assert client.get("/api/v1/news?region=KR-11").json()["total"] == 0
    run = collect_source(session, source, Adapter([Entry("", "", "1", action="delete")]))
    assert run.deleted_count == 1
    assert client.get("/api/v1/news").json()["total"] == 0
    assert all(r["count"] == 0 for r in client.get("/api/v1/map/regions").json()["regions"])


def test_missing_update_inserts_missing_delete_ignores(session):
    source = partner(session)
    run = collect_source(
        session,
        source,
        Adapter([entry(action="update"), Entry("", "", "missing", action="delete")]),
    )
    assert run.inserted_count == 1 and run.deleted_count == run.updated_count == 0


def test_future_release_hidden_from_list_and_map(session, client):
    source = partner(session)
    collect_source(session, source, Adapter([entry(stamp=utcnow() + timedelta(hours=1))]))
    assert session.scalar(select(Article.id)) is not None
    assert client.get("/api/v1/news").json()["total"] == 0
    assert all(r["count"] == 0 for r in client.get("/api/v1/map/regions").json()["regions"])


def test_failed_batch_rolls_back_prior_event(session):
    source = partner(session)
    collect_source(session, source, Adapter([entry()]))
    # Invalid action payload forces a failure after the first deletion was flushed.
    run = collect_source(session, source, Adapter([Entry("", "", "1", action="delete"), None]))
    assert run.status == "failed" and run.deleted_count == 0
    assert session.scalar(select(Article.external_id)) == "1"
