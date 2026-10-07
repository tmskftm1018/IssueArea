from html import escape
from urllib.parse import urlencode

import httpx
import pytest

from app.db import utcnow
from app.models import Source
from app.source_registry import RightsReview, add_source, review_source, set_enabled
from app.sources import (
    MODS_PRESS_RELEASE_FEED,
    ModsPressReleaseAdapter,
    fetch_mods_kogl_type,
    parse_mods_kogl_type,
)


def article_url(number: int) -> str:
    return "https://mods.go.kr/board.es?" + urlencode(
        {"act": "view", "bid": "213", "list_no": str(number), "mid": "a10301040200"}
    )


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("공공누리 1유형(출처표시)", "1"),
        ("공공누리 제 1 유형", "1"),
        ("제1유형:출처표시", "1"),
        ("공공누리 4유형(출처표시+상업적 이용금지+변경금지)", "4"),
        ("이용조건을 확인할 수 없음", None),
    ],
)
def test_parse_mods_kogl_type_only_reads_explicit_license_link(label, expected):
    html = f'<p>본문에서 <a href="https://www.kogl.or.kr/info/license.do">{label}</a></p>'
    assert parse_mods_kogl_type(html) == expected


def test_parse_mods_kogl_type_rejects_ambiguous_or_unlinked_labels():
    assert (
        parse_mods_kogl_type(
            '<a href="https://kogl.or.kr">공공누리 1유형</a>'
            '<a href="https://kogl.or.kr">공공누리 4유형</a>'
        )
        is None
    )
    assert parse_mods_kogl_type("<p>공공누리 1유형</p>") is None


def test_fetch_mods_license_rejects_untrusted_article_urls(monkeypatch):
    real_client = httpx.Client
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, text='<a href="https://kogl.or.kr">공공누리 1유형</a>')

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    with real_client(transport=httpx.MockTransport(handler)) as client:
        assert fetch_mods_kogl_type(client, "https://example.com/board.es?bid=1") is None
    assert calls == []


def test_mods_adapter_filters_every_article_by_item_license(monkeypatch):
    feed = """<rss version="2.0"><channel><title>국가데이터처 보도자료</title>
      <link>https://mods.go.kr</link><description>press releases</description>
      <item><title>허용 보도자료</title><link>{one}</link><guid>1</guid></item>
      <item><title>비상업 보도자료</title><link>{four}</link><guid>2</guid></item>
      <item><title>표시 없는 보도자료</title><link>{none}</link><guid>3</guid></item>
      <item><title>외부 링크</title><link>https://attacker.example/item</link><guid>4</guid></item>
    </channel></rss>""".format(
        one=escape(article_url(1), quote=False),
        four=escape(article_url(2), quote=False),
        none=escape(article_url(3), quote=False),
    ).encode()
    license_one = "공공누리 1유형(출처표시)"
    pages = {
        article_url(1): f'<a href="https://www.kogl.or.kr/info/license.do">{license_one}</a>',
        article_url(2): '<a href="https://www.kogl.or.kr/info/license.do">공공누리 4유형</a>',
        article_url(3): "<p>저작권 및 이용안내</p>",
    }
    real_client = httpx.Client
    requested_articles = []

    def handler(request):
        if str(request.url) == MODS_PRESS_RELEASE_FEED:
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
    result = ModsPressReleaseAdapter().fetch(
        Source(adapter_type="mods_press_release", feed_url=MODS_PRESS_RELEASE_FEED)
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


def test_mods_adapter_rejects_other_feed_urls():
    source = Source(adapter_type="mods_press_release", feed_url="https://example.com/feed")
    with pytest.raises(ValueError):
        ModsPressReleaseAdapter().fetch(source)


def test_source_registry_locks_mods_to_official_feed_and_safe_polling(session):
    terms = "https://mods.go.kr/menu.es?mid=a10706000000"
    with pytest.raises(ValueError):
        add_source(session, "MODS", "https://example.com/feed", terms, 30, "mods_press_release")
    with pytest.raises(ValueError):
        add_source(session, "MODS", MODS_PRESS_RELEASE_FEED, terms, 10, "mods_press_release")
    source = add_source(
        session,
        "국가데이터처 보도자료",
        MODS_PRESS_RELEASE_FEED,
        terms,
        60,
        "mods_press_release",
    )
    review_source(
        session,
        source.id,
        RightsReview(
            rights_status="conditional",
            title_display_allowed=True,
            metadata_storage_allowed=True,
            commercial_use_allowed=True,
            terms_url=terms,
            terms_checked_at=utcnow(),
            notes="공식 게시물의 KOGL 1유형만 라이선스 링크로 검증해 수집합니다.",
        ),
    )
    assert set_enabled(session, source.id, True).enabled


def test_source_registry_upgrades_only_empty_unreviewed_mods_placeholder(session):
    terms = "https://mods.go.kr/menu.es?mid=a10706000000"
    placeholder = add_source(
        session,
        "국가데이터처 보도자료 (권리 검토 전)",
        MODS_PRESS_RELEASE_FEED,
        terms,
        60,
        "rss_press_release",
    )
    configured = add_source(
        session,
        "국가데이터처 보도자료",
        MODS_PRESS_RELEASE_FEED,
        terms,
        60,
        "mods_press_release",
    )
    assert configured.id == placeholder.id
    assert configured.adapter_type == "mods_press_release"
    assert configured.rights_status == "unreviewed" and not configured.enabled

    configured.enabled = True
    session.commit()
    with pytest.raises(ValueError):
        add_source(session, "MODS", MODS_PRESS_RELEASE_FEED, terms, 60, "mods_press_release")


def test_mods_adapter_redirects_are_rejected_and_html_size_is_bounded(monkeypatch):
    real_client = httpx.Client
    escaped_article_url = escape(article_url(1), quote=False)
    feed = (
        '<rss version="2.0"><channel><title>MODS</title><link>https://mods.go.kr</link>'
        "<description>RSS</description><item><title>허용 후보</title>"
        f"<link>{escaped_article_url}</link><guid>1</guid></item></channel></rss>"
    ).encode()
    requested = []

    def handler(request):
        if str(request.url) == MODS_PRESS_RELEASE_FEED:
            return httpx.Response(200, content=feed)
        requested.append(request)
        return httpx.Response(302, headers={"location": "https://attacker.example/"})

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = ModsPressReleaseAdapter().fetch(
        Source(adapter_type="mods_press_release", feed_url=MODS_PRESS_RELEASE_FEED)
    )
    assert result.entries == []
    assert len(requested) == 1
