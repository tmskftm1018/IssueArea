import calendar
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

import feedparser
import httpx

from app.catalog import REGIONS, TOPICS
from app.db import utcnow
from app.models import Source


@dataclass
class Entry:
    title: str
    url: str
    external_id: str | None = None
    published_at: datetime | None = None
    categories: list[str] = field(default_factory=list)
    action: Literal["insert", "update", "delete"] = "insert"
    publisher_name: str | None = None


@dataclass
class FetchResult:
    entries: list[Entry]
    status: int = 200
    etag: str | None = None
    last_modified: str | None = None


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
                        )
                    )
                return FetchResult(
                    entries,
                    response.status_code,
                    response.headers.get("etag"),
                    response.headers.get("last-modified"),
                )
