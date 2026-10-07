from datetime import UTC, datetime

import httpx

from app import collector
from app.models import Article, Source
from app.services import title_hash
from app.sources import (
    MOIS_PRESS_RELEASE_FEED,
    Entry,
    FetchResult,
    fetch_mois_published_date,
    parse_mois_published_date,
)

ARTICLE_URL = (
    "https://www.mois.go.kr/frt/bbs/type010/commonSelectBoardArticle.do"
    "?bbsId=BBSMSTR_000000000008&nttId=129939"
)


def test_parse_mois_registration_date_from_article_metadata():
    page = """<div class="table_info"><span>등록일</span> : 2026.10.07.
    <span>작성자</span> : 과</div><div>다른 날짜 2025.01.01.</div>"""
    assert parse_mois_published_date(page) == datetime(2026, 10, 6, 15, tzinfo=UTC)
    assert parse_mois_published_date("<div class='table_info'>작성자: 부서</div>") is None


def test_mois_page_fetch_is_limited_to_press_release_article(monkeypatch):
    requested = []
    real_client = httpx.Client

    def handler(request):
        requested.append(str(request.url))
        return httpx.Response(
            200,
            text='<div class="table_info"><span>등록일</span> : 2026.10.07.</div>',
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    assert fetch_mois_published_date(ARTICLE_URL) == datetime(2026, 10, 6, 15, tzinfo=UTC)
    assert requested == [ARTICLE_URL]
    untrusted_url = "https://attacker.example/" + ARTICLE_URL.split("/", 3)[-1]
    assert fetch_mois_published_date(untrusted_url) is None


def test_mois_collector_backfills_existing_dates_once(session, monkeypatch):
    source = Source(
        name="행정안전부 보도자료",
        adapter_type="rss_press_release",
        feed_url=MOIS_PRESS_RELEASE_FEED,
        enabled=True,
        rights_status="allowed",
        title_display_allowed=True,
        metadata_storage_allowed=True,
    )
    session.add(source)
    session.flush()
    article = Article(
        source_id=source.id,
        external_id="old-guid-value",
        title="행정안전부 보도자료 제목",
        original_url=ARTICLE_URL,
        canonical_url=ARTICLE_URL,
        title_hash=title_hash("행정안전부 보도자료 제목"),
        published_at=None,
        published_precision=None,
        geo_scope="unknown",
    )
    session.add(article)
    session.commit()
    expected = datetime(2026, 10, 6, 15, tzinfo=UTC)
    calls = []
    monkeypatch.setattr(
        collector,
        "fetch_mois_published_date",
        lambda url: calls.append(url) or expected,
    )

    class Feed:
        def fetch(self, _source):
            return FetchResult([Entry(article.title, ARTICLE_URL, "129939")])

    run = collector.collect_source(session, source, Feed())
    assert run.updated_count == 1 and run.inserted_count == 0
    assert article.published_at.replace(tzinfo=UTC) == expected
    assert article.published_precision == "date"
    assert article.geo_scope == "national"
    assert calls == [ARTICLE_URL]

    collector.collect_source(session, source, Feed())
    assert calls == [ARTICLE_URL]
