"""One free-plan request per scheduled run; never fetch paid endpoints or article pages."""

import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx

from app.config import settings
from app.services import canonical_url, clean_title
from app.sources import Entry, FetchResult

ENDPOINT = "https://newsdata.io/api/1/latest"
# Provider allows at most five categories on the free plan. Excluding lifestyle,
# entertainment, sports and tourism keeps the map focused on public-interest issues.
ISSUE_CATEGORIES = ("politics", "business", "crime", "domestic", "technology")
# NewsData's free tier has no region filter. Search only for titles mentioning a
# Korean city/province; the collector applies the stricter region classifier too.
LOCAL_TITLE_TERMS = (
    # Keep the OR expression within NewsData's effective 100-character query cap.
    # Ambiguous broad terms are screened again by RuleBasedRegionClassifier.
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기",
    "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
)
LOCAL_TITLE_QUERY = " OR ".join(LOCAL_TITLE_TERMS)
TOPIC_CATEGORY_MAP = {
    "politics": "politics",
    "business": "economy",
    "crime": "incident",
    "domestic": "society",
    "technology": "technology",
}


class FreeQuotaExceeded(Exception):
    pass


class NewsDataSourceAdapter:
    def __init__(self, api_key=None, transport=None):
        self.api_key = api_key or (
            settings.newsdata_api_key.get_secret_value() if settings.newsdata_api_key else None
        )
        self.transport = transport

    def fetch(self, source):
        if not self.api_key:
            raise ValueError("NewsData.io free API key is required")
        with httpx.Client(timeout=20, follow_redirects=False, transport=self.transport) as client:
            with client.stream(
                "GET",
                ENDPOINT,
                params={
                    "country": "kr",
                    "language": "ko",
                    "qInTitle": LOCAL_TITLE_QUERY,
                    "category": ",".join(ISSUE_CATEGORIES),
                    "size": 10,
                },
                headers={"X-ACCESS-KEY": self.api_key, "User-Agent": "IssueAreaCollector/0.1"},
            ) as response:
                if response.status_code == 429:
                    raise FreeQuotaExceeded("Provider quota reached")
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 2 * 1024 * 1024:
                        raise ValueError("News API response exceeds limit")
        payload = json.loads(data)
        if not isinstance(payload, dict) or payload.get("status") != "success":
            raise ValueError("News API returned an unsuccessful response")
        rows = payload.get("results")
        if not isinstance(rows, list) or len(rows) > 10:
            raise ValueError("Invalid free-plan article list")
        entries = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Invalid news metadata")
            title, url = clean_title(row.get("title") or ""), row.get("link")
            key = row.get("article_id")
            if not title or not isinstance(key, str) or not 0 < len(key) <= 1024:
                raise ValueError("News metadata lacks title or identity")
            canonical_url(url)
            stamp = datetime.fromisoformat(row["pubDate"].replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=ZoneInfo(row.get("pubDateTZ") or "UTC"))
            publisher = clean_title(row.get("source_name") or row.get("source_id") or "")[:200]
            if not publisher:
                raise ValueError("News metadata lacks publisher attribution")
            categories = row.get("category") or []
            if not isinstance(categories, list):
                raise ValueError("Invalid provider categories")
            # Keep the downstream classifier aligned with IssueArea's topic catalog.
            mapped = [
                TOPIC_CATEGORY_MAP[category]
                for category in categories
                if category in TOPIC_CATEGORY_MAP
            ]
            if not mapped:
                continue
            # No description, article body, photos, or inferred publisher location is retained.
            entries.append(
                Entry(
                    title,
                    url,
                    key,
                    stamp.astimezone(UTC),
                    categories=mapped,
                    publisher_name=publisher,
                )
            )
        # Ignore nextPage: pagination consumes another credit and is deliberately disabled.
        return FetchResult(entries)
