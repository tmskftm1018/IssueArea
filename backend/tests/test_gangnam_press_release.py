from html import escape

import httpx
import pytest

from app.config import settings
from app.db import utcnow
from app.models import Source
from app.source_registry import RightsReview, add_source, review_source
from app.sources import GANGNAM_PRESS_RELEASE_FEED, GangnamPressReleaseAdapter

TERMS_URL = "https://www.gangnam.go.kr/contents/copyright/1/view.do?mid=ID06_040905"


def article_url(number: int) -> str:
    return f"https://www.gangnam.go.kr/board/B_000031/{number}/view.do?mid=ID01_0313"


def test_gangnam_adapter_keeps_only_explicit_type_one(monkeypatch):
    monkeypatch.setattr(settings, "app_usage_mode", "development")
    feed = """<rss version="2.0"><channel><title>강남구청 보도자료</title>
      <link>https://www.gangnam.go.kr</link><description>press releases</description>
      <item><title>허용 보도자료</title><link>{one}</link><guid>1</guid>
        <pubDate>2026-10-14</pubDate></item>
      <item><title>제한 보도자료</title><link>{two}</link><guid>2</guid></item>
      <item><title>유형 미표시 보도자료</title><link>{none}</link><guid>3</guid></item>
      <item><title>외부 링크</title><link>https://attacker.example/item</link><guid>4</guid></item>
    </channel></rss>""".format(
        one=escape(article_url(1), quote=False),
        two=escape(article_url(2), quote=False),
        none=escape(article_url(3), quote=False),
    ).encode()
    pages = {
        article_url(1): '<a href="https://www.kogl.or.kr/info/licenseType1.do">제1유형</a>',
        article_url(2): '<a href="https://www.kogl.or.kr/info/licenseType2.do">제2유형</a>',
        article_url(3): "<p>이용조건을 확인할 수 없음</p>",
    }
    real_client = httpx.Client
    requests = []

    def handler(request):
        if str(request.url) == GANGNAM_PRESS_RELEASE_FEED:
            return httpx.Response(200, content=feed)
        requests.append(str(request.url))
        return httpx.Response(200, text=pages[str(request.url)])

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = GangnamPressReleaseAdapter().fetch(
        Source(adapter_type="gangnam_press_release", feed_url=GANGNAM_PRESS_RELEASE_FEED)
    )

    assert [(entry.external_id, entry.action) for entry in result.entries] == [
        ("1", "insert"),
        ("2", "delete"),
    ]
    assert result.entries[0].published_precision == "date"
    assert article_url(1) in requests
    assert article_url(2) in requests
    assert article_url(3) in requests
    assert "https://attacker.example/item" not in requests


def test_gangnam_adapter_rejects_untrusted_article_urls(monkeypatch):
    calls = []
    real_client = httpx.Client

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, text='<a href="https://kogl.or.kr">제1유형</a>')

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    assert (
        GangnamPressReleaseAdapter().secure_article_url(
            "https://www.gangnam.go.kr/board/B_000031/not-a-number/view.do"
        )
        is None
    )
    assert (
        GangnamPressReleaseAdapter().secure_article_url(
            "https://attacker.example/board/B_000031/12/view.do"
        )
        is None
    )
    assert calls == []


def test_gangnam_adapter_normalizes_official_host_aliases():
    assert GangnamPressReleaseAdapter().secure_article_url(
        "https://gangnam.go.kr/board/B_000031/1075466/view.do"
    ) == article_url(1075466)


def test_gangnam_adapter_rejects_unexpected_menu_query():
    assert (
        GangnamPressReleaseAdapter().secure_article_url(
            "https://www.gangnam.go.kr/board/B_000031/1075466/view.do?mid=ID03_0101"
        )
        is None
    )


def test_gangnam_allows_type_two_only_in_noncommercial_mode(monkeypatch):
    monkeypatch.setattr(settings, "app_usage_mode", "noncommercial")
    feed = """<rss version="2.0"><channel><title>강남구청 보도자료</title>
      <link>https://www.gangnam.go.kr</link><description>press releases</description>
      <item><title>제1유형</title><link>{one}</link><guid>1</guid></item>
      <item><title>제2유형</title><link>{two}</link><guid>2</guid></item>
      <item><title>제4유형</title><link>{four}</link><guid>4</guid></item>
    </channel></rss>""".format(
        one=escape(article_url(1), quote=False),
        two=escape(article_url(2), quote=False),
        four=escape(article_url(4), quote=False),
    ).encode()
    pages = {
        article_url(1): '<a href="https://www.kogl.or.kr/info/licenseType1.do">제1유형</a>',
        article_url(2): '<a href="https://www.kogl.or.kr/info/licenseType2.do">제2유형</a>',
        article_url(4): '<a href="https://www.kogl.or.kr/info/licenseType4.do">제4유형</a>',
    }
    real_client = httpx.Client

    def handler(request):
        if str(request.url) == GANGNAM_PRESS_RELEASE_FEED:
            return httpx.Response(200, content=feed)
        return httpx.Response(200, text=pages[str(request.url)])

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = GangnamPressReleaseAdapter().fetch(
        Source(
            adapter_type="gangnam_press_release",
            feed_url=GANGNAM_PRESS_RELEASE_FEED,
            commercial_use_allowed=False,
        )
    )

    assert [(entry.external_id, entry.action) for entry in result.entries] == [
        ("1", "insert"),
        ("2", "insert"),
        ("4", "delete"),
    ]


def test_registry_locks_gangnam_adapter_to_official_feed_and_interval(session):
    with pytest.raises(ValueError):
        add_source(
            session,
            "강남구",
            "https://example.com/feed",
            TERMS_URL,
            60,
            "gangnam_press_release",
        )
    with pytest.raises(ValueError):
        add_source(
            session,
            "강남구청 보도자료",
            GANGNAM_PRESS_RELEASE_FEED,
            TERMS_URL,
            10,
            "gangnam_press_release",
        )
    source = add_source(
        session,
        "강남구청 보도자료 (검토 전)",
        GANGNAM_PRESS_RELEASE_FEED,
        TERMS_URL,
        60,
        "gangnam_press_release",
    )
    assert not source.enabled and source.rights_status == "unreviewed"

    reviewed = review_source(
        session,
        source.id,
        RightsReview(
            rights_status="conditional",
            title_display_allowed=True,
            metadata_storage_allowed=True,
            commercial_use_allowed=True,
            terms_url=TERMS_URL,
            terms_checked_at=utcnow(),
            notes="실제 수집은 개별 원문에서 KOGL 제1유형 링크가 확인된 보도자료에만 허용합니다.",
        ),
    )
    assert not reviewed.enabled
