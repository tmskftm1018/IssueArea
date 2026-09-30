from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.collector import collect_source
from app.config import settings
from app.db import utcnow
from app.models import CollectionRun, Source
from app.source_registry import (
    RightsReview,
    add_source,
    review_source,
    set_enabled,
    source_status,
    validate_registry_url,
)


def review(**overrides):
    fields = dict(
        rights_status="allowed",
        title_display_allowed=True,
        metadata_storage_allowed=True,
        commercial_use_allowed=False,
        terms_url="https://publisher.example/terms",
        terms_checked_at=utcnow(),
        notes="운영자가 확인한 테스트용 이용허락 기록입니다.",
    )
    return RightsReview(**(fields | overrides))


def create(session):
    return add_source(
        session,
        "테스트 출처",
        "https://publisher.example/rss?id=1&utm_key=x",
        "https://publisher.example/terms",
    )


def test_registration_and_review(session):
    source = create(session)
    assert not source.enabled and source.rights_status == "unreviewed"
    assert source.feed_url.endswith("?id=1&utm_key=x")
    with pytest.raises(ValueError):
        set_enabled(session, source.id, True)
    review_source(session, source.id, review())
    assert not source.enabled
    set_enabled(session, source.id, True)
    assert source.enabled
    review_source(session, source.id, review(rights_status="prohibited"))
    assert not source.enabled
    with pytest.raises(ValueError):
        set_enabled(session, source.id, True)


def test_commercial_guard(session, monkeypatch):
    source = create(session)
    review_source(session, source.id, review())
    monkeypatch.setattr(settings, "app_usage_mode", "commercial")
    with pytest.raises(ValueError):
        set_enabled(session, source.id, True)
    review_source(session, source.id, review(commercial_use_allowed=True))
    assert set_enabled(session, source.id, True).enabled


def test_direct_collection_cannot_bypass_rights(session):
    source = create(session)
    with pytest.raises(PermissionError):
        collect_source(session, source)
    assert session.scalar(select(func.count()).select_from(CollectionRun)) == 0


def test_status_does_not_expose_feed_token(session):
    create(session)
    assert "utm_key" not in str(source_status(session))


def test_duplicate_registration(session):
    create(session)
    with pytest.raises(ValueError):
        create(session)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/rss",
        "http://127.0.0.1/rss",
        "http://10.0.0.1/rss",
        "http://[::1]/rss",
        "file:///rss",
        "https://user:password@publisher.example/rss",
    ],
)
def test_registry_rejects_unsafe_addresses(url):
    with pytest.raises(ValueError):
        validate_registry_url(url)


def test_review_time_validation():
    with pytest.raises(ValueError):
        review(terms_checked_at=utcnow() + timedelta(days=1))
    with pytest.raises(ValueError):
        review(terms_checked_at=utcnow().replace(tzinfo=None))


def test_disabled_demo_hidden(session, client, monkeypatch):
    source = session.scalar(select(Source).where(Source.adapter_type == "demo"))
    collect_source(session, source)
    monkeypatch.setattr(settings, "demo_mode", False)
    assert client.get("/api/v1/news").json()["total"] == 0
    assert all(r["count"] == 0 for r in client.get("/api/v1/map/regions").json()["regions"])


def test_disabled_source_hidden(session, client):
    source = session.scalar(select(Source).where(Source.adapter_type == "demo"))
    collect_source(session, source)
    source.enabled = False
    session.commit()
    assert client.get("/api/v1/news").json()["total"] == 0
