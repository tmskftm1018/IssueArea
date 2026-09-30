from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.classifiers import RuleBasedRegionClassifier, RuleBasedTopicClassifier
from app.collector import collect_source
from app.db import utcnow
from app.models import Article, CollectionRun, Region, Source
from app.services import can_collect, canonical_url, clean_title
from app.sources import Entry, FetchResult


def demo(session):
    return session.scalar(select(Source).where(Source.adapter_type == "demo"))


@pytest.mark.parametrize(
    "title, expected",
    [
        ("서울 도심 교통 안내", {"KR-11"}),
        ("서울·경기 집중호우", {"KR-11", "KR-41"}),
        ("부산 강풍", {"KR-26"}),
        ("중구 교통사고", set()),
        ("경기침체 우려", set()),
        ("광주 행사", set()),
        ("광주광역시 행사", {"KR-29"}),
        ("광산구 행사", {"KR-29"}),
        ("목포 축제", {"KR-29"}),
        ("전남광주통합특별시 출범", {"KR-29"}),
    ],
)
def test_regions(session, title, expected):
    regions = list(session.scalars(select(Region)))
    ids = RuleBasedRegionClassifier().classify(title, regions)
    assert {r.code for r in regions if r.id in ids} == expected


def test_topics():
    classifier = RuleBasedTopicClassifier()
    assert classifier.classify("반도체 투자 기술", [])[0] == ["economy", "technology"]
    assert classifier.classify("태풍", ["교육"]) == (["education"], "source_category")


def test_url_and_title():
    assert (
        canonical_url("https://EXAMPLE.com/a?id=9&utm_source=x#part")
        == "https://example.com/a?id=9"
    )
    assert clean_title(" <b>서울</b> &amp;  경기\x00 ") == "서울 & 경기"
    for url in ["javascript:alert(1)", "data:text/html,a", "file:///x", "//example.com"]:
        with pytest.raises(ValueError):
            canonical_url(url)


def test_rights(session):
    source = demo(session)
    source.commercial_use_allowed = False
    assert not can_collect(source, "commercial")
    assert can_collect(source, "noncommercial")
    source.rights_status = "unreviewed"
    assert not can_collect(source, "development")


def test_demo_idempotent(session):
    source = demo(session)
    first = collect_source(session, source)
    second = collect_source(session, source)
    assert first.inserted_count == 19
    assert second.inserted_count == 0 and second.duplicate_count == 19
    assert session.scalar(select(func.count()).select_from(Article)) == 19
    assert session.scalar(select(func.count()).select_from(CollectionRun)) == 2


class Adapter:
    def __init__(self, entries):
        self.entries = entries

    def fetch(self, source):
        return FetchResult(self.entries)


def test_deduplication(session):
    now = utcnow()
    source = demo(session)
    entries = [
        Entry("서울 행사", "https://example.com/a?id=1", "one", now),
        Entry("서울 행사 변경", "https://example.com/b", "one", now),
        Entry("서울 행사 변경", "https://example.com/a?id=1&utm_source=x", "two", now),
        Entry("서울 행사", "https://example.com/c", "three", now + timedelta(hours=1)),
        Entry("서울 행사", "https://example.com/d", "four", now + timedelta(days=2)),
    ]
    result = collect_source(session, source, Adapter(entries))
    assert result.inserted_count == 2 and result.duplicate_count == 3
    other = Source(
        name="다른 출처",
        adapter_type="rss",
        enabled=True,
        rights_status="allowed",
        title_display_allowed=True,
        metadata_storage_allowed=True,
    )
    session.add(other)
    session.commit()
    assert collect_source(session, other, Adapter(entries[:1])).inserted_count == 1


def test_failure_isolation(session):
    class Broken:
        def fetch(self, source):
            raise TimeoutError("timeout")

    source = demo(session)
    assert collect_source(session, source, Broken()).status == "failed"
    assert source.consecutive_failures == 1
    assert collect_source(session, source).status == "success"
    assert source.consecutive_failures == 0


def test_304(session):
    class NotModified:
        def fetch(self, source):
            return FetchResult([], 304)

    run = collect_source(session, demo(session), NotModified())
    assert run.status == "not_modified" and run.inserted_count == 0
