import calendar
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from html.parser import HTMLParser
from typing import Literal
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import feedparser
import httpx

from app.catalog import REGIONS, TOPICS
from app.db import utcnow
from app.models import Source

MOIS_PRESS_RELEASE_FEED = "https://www.mois.go.kr/gpms/view/jsp/rss/rss.jsp?ctxCd=1012"


@dataclass
class Entry:
    title: str
    url: str
    external_id: str | None = None
    published_at: datetime | None = None
    categories: list[str] = field(default_factory=list)
    action: Literal["insert", "update", "delete"] = "insert"
    publisher_name: str | None = None
    published_precision: Literal["date", "datetime"] | None = None


@dataclass
class FetchResult:
    entries: list[Entry]
    status: int = 200
    etag: str | None = None
    last_modified: str | None = None


class _MoisArticleInfoParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        classes = dict(attrs).get("class", "").split()
        if tag == "div" and "table_info" in classes:
            self.depth += 1
        elif self.depth and tag == "div":
            self.depth += 1

    def handle_endtag(self, tag):
        if self.depth and tag == "div":
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def parse_mois_published_date(html: str) -> datetime | None:
    parser = _MoisArticleInfoParser()
    parser.feed(html)
    table_text = " ".join(parser.parts)
    match = re.search(
        r"등록일\s*:\s*(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})",
        table_text,
    )
    if not match:
        return None
    try:
        published_day = date(*(int(part) for part in match.groups()))
    except ValueError:
        return None
    return datetime.combine(published_day, time.min, ZoneInfo("Asia/Seoul")).astimezone(UTC)


def fetch_mois_published_date(article_url: str) -> datetime | None:
    parts = urlsplit(article_url)
    query = parse_qs(parts.query)
    if (
        parts.scheme != "https"
        or parts.hostname not in {"www.mois.go.kr", "mois.go.kr"}
        or parts.path != "/frt/bbs/type010/commonSelectBoardArticle.do"
        or query.get("bbsId") != ["BBSMSTR_000000000008"]
        or not query.get("nttId", [""])[0].isdigit()
    ):
        return None

    try:
        with httpx.Client(
            timeout=10,
            follow_redirects=False,
            headers={"User-Agent": "IssueAreaCollector/0.1 (metadata only)"},
        ) as client:
            with client.stream("GET", article_url) as response:
                if response.status_code != 200:
                    return None
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > 512 * 1024:
                        return None
        return parse_mois_published_date(content.decode("utf-8", errors="replace"))
    except httpx.HTTPError:
        return None


class DemoSourceAdapter:
    def fetch(self, source: Source) -> FetchResult:
        # Stable IDs per hour: re-fetching one edition is idempotent; later editions are fresh.
        edition = utcnow().replace(minute=0, second=0, microsecond=0)
        phrases = [
            "의회 정책 토론 개최",
            "기업 기술 투자 행사 개최",
            "도로 교통 안내 발표",
            "소방 화재 구조 훈련 실시",
            "강풍 기상 대비 훈련 실시",
            "학교 교육 행사 개최",
            "보건 건강 상담 행사 개최",
            "생태 환경 전시 개최",
            "연구 기술 행사 개최",
            "문화 공연 행사 개최",
            "축구 체육 행사 개최",
            "국제 교류 행사 개최",
        ]
        entries = []
        for i, (code, name, _, _, _, _) in enumerate(REGIONS):
            slug = list(TOPICS)[i % len(TOPICS)]
            key = f"{edition:%Y%m%d%H}-{code}"
            entries.append(
                Entry(
                    f"[개발용] {name} {phrases[i % len(phrases)]}",
                    f"https://example.com/news/demo-{key}",
                    key,
                    edition - timedelta(minutes=i * 2),
                    [slug],
                )
            )
        entries.extend(
            [
                Entry(
                    "[개발용] 서울·경기 호우 대비 교통 안내",
                    f"https://example.com/news/{edition:%Y%m%d%H}-multi",
                    f"{edition:%Y%m%d%H}-multi",
                    edition,
                    ["weather", "society"],
                ),
                Entry(
                    "[개발용] 전국 학교 교육 정책 안내",
                    f"https://example.com/news/{edition:%Y%m%d%H}-national",
                    f"{edition:%Y%m%d%H}-national",
                    edition,
                    ["education"],
                ),
                Entry(
                    "[개발용] 중구 교통사고 대응 훈련",
                    f"https://example.com/news/{edition:%Y%m%d%H}-unknown",
                    f"{edition:%Y%m%d%H}-unknown",
                    None,
                    ["incident"],
                ),
            ]
        )
        return FetchResult(entries)


class RSSSourceAdapter:
    max_bytes = 2 * 1024 * 1024

    def fetch(self, source: Source) -> FetchResult:
        headers = {"User-Agent": "IssueAreaCollector/0.1 (metadata only)"}
        if source.etag:
            headers["If-None-Match"] = source.etag
        if source.last_modified:
            headers["If-Modified-Since"] = source.last_modified
        with httpx.Client(timeout=15, follow_redirects=True, max_redirects=3) as client:
            with client.stream("GET", source.feed_url, headers=headers) as response:
                if response.status_code == 304:
                    return FetchResult([], 304)
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > self.max_bytes:
                        raise ValueError("Feed exceeds 2 MiB limit")
                parsed = feedparser.parse(bytes(content))
                if parsed.bozo or not parsed.version:
                    raise ValueError("Malformed or unsupported RSS/Atom feed")
                entries = []
                for item in parsed.entries[:500]:
                    published = item.get("published_parsed")
                    entries.append(
                        Entry(
                            title=item.get("title", ""),
                            url=item.get("link", ""),
                            external_id=item.get("id"),
                            published_at=datetime.fromtimestamp(calendar.timegm(published), UTC)
                            if published
                            else None,
                            categories=[t.get("term", "") for t in item.get("tags", [])],
                            published_precision="datetime" if published else None,
                        )
                    )
                return FetchResult(
                    entries,
                    response.status_code,
                    response.headers.get("etag"),
                    response.headers.get("last-modified"),
                )
