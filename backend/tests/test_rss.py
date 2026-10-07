import httpx
import pytest

from app.models import Source
from app.sources import RSSSourceAdapter


def test_rss_conditional_headers(monkeypatch):
    source = Source(feed_url="https://example.com/feed", etag='"v1"', last_modified="yesterday")
    real_client = httpx.Client

    def handler(request):
        assert str(request.url) == "https://example.com/feed"
        assert request.headers["user-agent"].startswith("IssueAreaCollector/")
        assert request.headers["if-none-match"] == '"v1"'
        assert request.headers["if-modified-since"] == "yesterday"
        return httpx.Response(304)

    monkeypatch.setattr(
        httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )
    result = RSSSourceAdapter().fetch(source)
    assert result.status == 304 and result.entries == []


@pytest.mark.parametrize("kind", ["rss", "500", "malformed", "oversized", "timeout"])
def test_rss_responses(monkeypatch, kind):
    real_client = httpx.Client

    def handler(request):
        if kind == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        if kind == "500":
            return httpx.Response(500)
        if kind == "malformed":
            return httpx.Response(200, content=b"<html>oops</html>")
        if kind == "oversized":
            return httpx.Response(200, content=b"x" * (RSSSourceAdapter.max_bytes + 1))
        return httpx.Response(
            200,
            content=b"""<?xml version="1.0"?><rss version="2.0">
        <channel><title>Example</title><link>https://example.com</link><description>Demo</description>
        <item><title>Seoul news</title><link>https://example.com/1</link><guid>one</guid>
        <pubDate>Wed, 30 Sep 2026 00:00:00 GMT</pubDate></item></channel></rss>""",
        )

    monkeypatch.setattr(
        httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )
    source = Source(feed_url="https://example.com/feed")
    if kind == "rss":
        result = RSSSourceAdapter().fetch(source)
        assert result.entries[0].external_id == "one"
        assert result.entries[0].published_at.isoformat() == "2026-09-30T00:00:00+00:00"
    else:
        with pytest.raises((ValueError, httpx.HTTPError)):
            RSSSourceAdapter().fetch(source)


@pytest.mark.parametrize(("redirects", "succeeds"), [(3, True), (4, False)])
def test_rss_redirect_limit(monkeypatch, redirects, succeeds):
    real_client = httpx.Client
    remaining = redirects
    feed = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Example</title>
    <link>https://example.com</link><description>Demo</description></channel></rss>"""

    def handler(request):
        nonlocal remaining
        if remaining:
            remaining -= 1
            return httpx.Response(302, headers={"Location": f"/redirect/{remaining}"})
        if redirects == 4:
            return httpx.Response(302, headers={"Location": "/redirect/extra"})
        return httpx.Response(200, content=feed)

    monkeypatch.setattr(
        httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )
    source = Source(feed_url="https://example.com/feed")
    if succeeds:
        assert RSSSourceAdapter().fetch(source).entries == []
    else:
        with pytest.raises(httpx.TooManyRedirects):
            RSSSourceAdapter().fetch(source)


def test_rss_accepts_response_at_exact_size_limit(monkeypatch):
    real_client = httpx.Client
    body = """<?xml version="1.0"?><rss version="2.0"><channel><title>Example</title>
    <link>https://example.com</link><description>Demo</description>
    <item><title>서울 교통 안내</title><link>https://example.com/1</link>
    <guid>one</guid></item>""".encode()
    body += b" " * (RSSSourceAdapter.max_bytes - len(body) - len(b"</channel></rss>"))
    body += b"</channel></rss>"
    assert len(body) == RSSSourceAdapter.max_bytes

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kw: real_client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body)),
            **kw,
        ),
    )
    result = RSSSourceAdapter().fetch(Source(feed_url="https://example.com/feed"))
    assert [entry.external_id for entry in result.entries] == ["one"]


def test_rss_caps_entries_at_500(monkeypatch):
    real_client = httpx.Client
    items = "".join(
        f"<item><title>서울 공지 {i}</title><link>https://example.com/{i}</link>"
        f"<guid>{i}</guid></item>"
        for i in range(501)
    )
    body = (
        '<rss version="2.0"><channel><title>Example</title><link>https://example.com</link>'
        f"<description>Demo</description>{items}</channel></rss>"
    ).encode()
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kw: real_client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body)),
            **kw,
        ),
    )
    result = RSSSourceAdapter().fetch(Source(feed_url="https://example.com/feed"))
    assert len(result.entries) == 500
    assert result.entries[0].external_id == "0"
    assert result.entries[-1].external_id == "499"
