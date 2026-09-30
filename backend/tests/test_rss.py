import httpx
import pytest

from app.models import Source
from app.sources import RSSSourceAdapter


def test_rss_conditional_headers(monkeypatch):
    source = Source(feed_url="https://example.com/feed", etag='"v1"', last_modified="yesterday")
    real_client = httpx.Client

    def handler(request):
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
