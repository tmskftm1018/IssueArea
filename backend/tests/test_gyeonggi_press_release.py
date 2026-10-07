from html import escape
from urllib.parse import urlencode

import httpx
import pytest

from app.db import utcnow
from app.models import Source
from app.source_registry import RightsReview, add_source, review_source, set_enabled
from app.sources import (
    GYEONGGI_PRESS_RELEASE_FEED,
    GyeonggiPressReleaseAdapter,
    fetch_gyeonggi_kogl_type,
    parse_mods_kogl_type,
)


TERMS_URL = "https://www.gg.go.kr/contents/contents.do?ciIdx=1066&menuId=2772"


def article_url(number: int) -> str:
    return "https://gnews.gg.go.kr/briefing/brief_gongbo_view.do?" + urlencode(
        {"BS_CODE": "S017", "number": str(number)}
    )


def test_parser_accepts_explicit_gyeonggi_kogl_anchor():
    html = '<a href="http://www.kogl.or.kr/info/licenseType1.do">제1유형:출처표시 조건</a>'
    assert parse_mods_kogl_type(html) == "1"
    assert parse_mods_kogl_type('<p>본문에 제1유형 언급</p>') is None


def test_fetch_gyeonggi_license_rejects_untrusted_article_url(monkeypatch):
    real_client = httpx.Client
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, text='<a href="https://kogl.or.kr">제1유형</a>')

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    with real_client(transport=httpx.MockTransport(handler)) as client:
        assert fetch_gyeonggi_kogl_type(client, "https://attacker.example/article") is None
    assert calls == []


def test_gyeonggi_adapter_filters_each_article_by_item_license(monkeypatch):
    feed = """<rss version="2.0"><channel><title>경기도뉴스포털</title>
      <link>https://gnews.gg.go.kr</link><description>press releases</description>
      <item><title>허용 보도자료</title><link>{one}</link><guid>1</guid></item>
      <item><title>제한 보도자료</title><link>{four}</link><guid>2</guid></item>
      <item><title>표시 없는 보도자료</title><link>{none}</link><guid>3</guid></item>
      <item><title>외부 링크</title><link>https://attacker.example/item</link><guid>4</guid></item>
    </channel></rss>""".format(
        one=escape(article_url(1), quote=False),
        four=escape(article_url(2), quote=False),
        none=escape(article_url(3), quote=False),
    ).encode()
    pages = {
        article_url(1): '<a href="http://www.kogl.or.kr/info/licenseType1.do">제1유형:출처표시</a>',
        article_url(2): '<a href="http://www.kogl.or.kr/info/licenseType4.do">제4유형</a>',
        article_url(3): "<p>저작권 및 이용안내</p>",
    }
    real_client = httpx.Client
    requested_articles = []

    def handler(request):
        if str(request.url) == GYEONGGI_PRESS_RELEASE_FEED:
            return httpx.Response(200, content=feed, headers={"etag": '"feed-v1"'})
        requested_articles.append(str(request.url))
        if str(request.url) not in pages:
            return httpx.Response(404)
        return httpx.Response(200, text=pages[str(request.url)])

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = GyeonggiPressReleaseAdapter().fetch(
        Source(adapter_type="gyeonggi_press_release", feed_url=GYEONGGI_PRESS_RELEASE_FEED)
    )
    assert [(entry.external_id, entry.action) for entry in result.entries] == [
        ("1", "insert"),
        ("2", "delete"),
    ]
    assert result.etag == '"feed-v1"'
    assert article_url(1) in requested_articles
    assert article_url(2) in requested_articles
    assert article_url(3) in requested_articles
    assert "https://attacker.example/item" not in requested_articles


def test_gyeonggi_adapter_rejects_other_feed_urls():
    source = Source(adapter_type="gyeonggi_press_release", feed_url="https://example.com/feed")
    with pytest.raises(ValueError):
        GyeonggiPressReleaseAdapter().fetch(source)


def test_source_registry_locks_gyeonggi_to_official_feed_and_safe_polling(session):
    with pytest.raises(ValueError):
        add_source(session, "Gyeonggi", "https://example.com/feed", TERMS_URL, 60, "gyeonggi_press_release")
    with pytest.raises(ValueError):
        add_source(
            session,
            "경기도뉴스포털 보도자료",
            GYEONGGI_PRESS_RELEASE_FEED,
            TERMS_URL,
            10,
            "gyeonggi_press_release",
        )
    source = add_source(
        session,
        "경기도뉴스포털 보도자료",
        GYEONGGI_PRESS_RELEASE_FEED,
        TERMS_URL,
        60,
        "gyeonggi_press_release",
    )
    review_source(
        session,
        source.id,
        RightsReview(
            rights_status="conditional",
            title_display_allowed=True,
            metadata_storage_allowed=True,
            commercial_use_allowed=True,
            terms_url=TERMS_URL,
            terms_checked_at=utcnow(),
            notes="개별 원문 페이지의 KOGL 1유형만 링크와 표기로 확인해 수집합니다.",
        ),
    )
    assert set_enabled(session, source.id, True).enabled


def test_source_registry_upgrades_only_empty_unreviewed_gyeonggi_placeholder(session):
    placeholder = add_source(
        session,
        "경기도뉴스포털 보도자료 (권리 검토 전)",
        GYEONGGI_PRESS_RELEASE_FEED,
        TERMS_URL,
        60,
        "rss_press_release",
    )
    configured = add_source(
        session,
        "경기도뉴스포털 보도자료",
        GYEONGGI_PRESS_RELEASE_FEED,
        TERMS_URL,
        60,
        "gyeonggi_press_release",
    )
    assert configured.id == placeholder.id
    assert configured.adapter_type == "gyeonggi_press_release"
    assert configured.rights_status == "unreviewed" and not configured.enabled

    configured.enabled = True
    session.commit()
    with pytest.raises(ValueError):
        add_source(
            session,
            "경기도뉴스포털",
            GYEONGGI_PRESS_RELEASE_FEED,
            TERMS_URL,
            60,
            "gyeonggi_press_release",
        )
