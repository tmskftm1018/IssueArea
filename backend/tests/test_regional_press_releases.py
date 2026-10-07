from html import escape
from urllib.parse import urlencode

import httpx
import pytest

from app.db import utcnow
from app.models import Source
from app.source_registry import RightsReview, add_source, review_source, set_enabled
from app.sources import (
    DAEGU_NEWS_FEED,
    JEONNAM_PRESS_RELEASE_FEED,
    DaeguPressReleaseAdapter,
    JeonnamPressReleaseAdapter,
)


DAEGU_TERMS = "https://www.daegu.go.kr/index.do?menu_id=00050251"
JEONNAM_TERMS = "https://www.jeonnam.go.kr/contentsView.do?menuId=jeonnam0816000000"


def daegu_url(aid: int) -> str:
    return "https://info.daegu.go.kr/newshome/mtnmain.php?" + urlencode(
        {"mtnkey": "articleview", "mkey": "scatelist", "mkey2": "2", "aid": str(aid)}
    )


def jeonnam_url(seq: int, scheme="https") -> str:
    return f"{scheme}://www.jeonnam.go.kr/M7116/boardView.do?" + urlencode(
        {"seq": str(seq), "menuId": "jeonnam0202000000"}
    )


@pytest.mark.parametrize(
    (
        "adapter_type",
        "feed_url",
        "article_one",
        "article_four",
        "article_none",
        "terms_url",
        "adapter",
    ),
    [
        (
            "daegu_press_release",
            DAEGU_NEWS_FEED,
            daegu_url(1),
            daegu_url(2),
            daegu_url(3),
            DAEGU_TERMS,
            DaeguPressReleaseAdapter,
        ),
        (
            "jeonnam_press_release",
            JEONNAM_PRESS_RELEASE_FEED,
            jeonnam_url(1, "http"),
            jeonnam_url(2, "http"),
            jeonnam_url(3, "http"),
            JEONNAM_TERMS,
            JeonnamPressReleaseAdapter,
        ),
    ],
)
def test_regional_adapter_filters_each_item_and_publishes_https_urls(
    monkeypatch,
    adapter_type,
    feed_url,
    article_one,
    article_four,
    article_none,
    terms_url,
    adapter,
):
    page_one_url = article_one.replace("http://", "https://", 1)
    page_four_url = article_four.replace("http://", "https://", 1)
    page_none_url = article_none.replace("http://", "https://", 1)
    feed = """<rss version="2.0"><channel><title>regional releases</title>
      <link>https://example.invalid</link><description>press releases</description>
      <item><title>허용 기사</title><link>{one}</link><guid>1</guid></item>
      <item><title>제한 기사</title><link>{four}</link><guid>2</guid></item>
      <item><title>표시 없는 기사</title><link>{none}</link><guid>3</guid></item>
      <item><title>외부 주소</title><link>https://attacker.example/item</link><guid>4</guid></item>
    </channel></rss>""".format(
        one=escape(article_one, quote=False),
        four=escape(article_four, quote=False),
        none=escape(article_none, quote=False),
    ).encode()
    pages = {
        page_one_url: '<a href="http://www.kogl.or.kr/info/licenseType1.do">제1유형:출처표시</a>',
        page_four_url: '<a href="http://www.kogl.or.kr/info/licenseType4.do">제4유형</a>',
        page_none_url: "<p>이용조건 미표시</p>",
    }
    real_client = httpx.Client
    requested = []

    def handler(request):
        if str(request.url) == feed_url:
            return httpx.Response(200, content=feed, headers={"etag": '"regional-v1"'})
        requested.append(str(request.url))
        if str(request.url) in pages:
            return httpx.Response(200, text=pages[str(request.url)])
        return httpx.Response(404)

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = adapter().fetch(Source(adapter_type=adapter_type, feed_url=feed_url))

    assert [(entry.external_id, entry.action) for entry in result.entries] == [
        ("1", "insert"),
        ("2", "delete"),
    ]
    assert result.etag == '"regional-v1"'
    assert all(url.startswith("https://") for url in requested)
    assert "https://attacker.example/item" not in requested
    if adapter_type == "jeonnam_press_release":
        assert result.entries[0].url.startswith("https://www.jeonnam.go.kr/")


@pytest.mark.parametrize(
    ("adapter", "adapter_type", "feed_url", "terms_url", "name"),
    [
        (
            DaeguPressReleaseAdapter,
            "daegu_press_release",
            DAEGU_NEWS_FEED,
            DAEGU_TERMS,
            "대구광역시 뉴스룸 시정뉴스",
        ),
        (
            JeonnamPressReleaseAdapter,
            "jeonnam_press_release",
            JEONNAM_PRESS_RELEASE_FEED,
            JEONNAM_TERMS,
            "전남광주통합특별시 보도자료",
        ),
    ],
)
def test_registry_upgrades_only_unreviewed_regional_placeholder(
    session, adapter, adapter_type, feed_url, terms_url, name
):
    placeholder = add_source(
        session, f"{name} (권리 검토 전)", feed_url, terms_url, 60, "rss_press_release"
    )
    configured = add_source(session, name, feed_url, terms_url, 60, adapter_type)
    assert configured.id == placeholder.id
    assert configured.adapter_type == adapter_type

    review_source(
        session,
        configured.id,
        RightsReview(
            rights_status="conditional",
            title_display_allowed=True,
            metadata_storage_allowed=True,
            commercial_use_allowed=True,
            terms_url=terms_url,
            terms_checked_at=utcnow(),
            notes="각 기사 원문의 공식 KOGL 1유형 표시를 확인한 경우만 표시합니다.",
        ),
    )
    assert set_enabled(session, configured.id, True).enabled
    configured.enabled = True
    session.commit()
    with pytest.raises(ValueError):
        add_source(session, name, feed_url, terms_url, 60, adapter_type)
