"""Newswire partner API client, based on the official coalition documentation.

Only article metadata crosses this adapter boundary. Body, photos and contact data are discarded.
"""

import base64
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime

import httpx

from app.config import settings
from app.services import canonical_url, clean_title
from app.sources import Entry, FetchResult

API_BASE = "https://www.newswire.co.kr"


def signature(key: str, path: str, timestamp: str) -> str:
    raw = hmac.new(key.encode(), (path + timestamp).encode(), hashlib.sha256).digest()
    return base64.b64encode(raw).decode()


def parse_events(payload: dict) -> list[Entry]:
    rows = payload.get("news", [])
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("Invalid partner API event list")
    # Preserve the provider event order and validate it; silently reordering is unsafe.
    previous_pid = -1
    entries = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid partner API event")
        pid, newsid, action = row.get("pid"), row.get("newsid"), row.get("action")
        if type(pid) is not int or pid < previous_pid or type(newsid) is not int or newsid <= 0:
            raise ValueError("Invalid partner API event identity or order")
        previous_pid = pid
        if action not in {"insert", "update", "delete"}:
            raise ValueError("Unknown partner API action")
        if action == "delete":
            entries.append(Entry("", "", str(newsid), action="delete"))
            continue
        title = clean_title(row.get("title", ""))
        url = row.get("url", "")
        canonical_url(url)
        if not title:
            raise ValueError("Partner metadata requires a title")
        stamp = row.get("press_time")
        if not isinstance(stamp, str):
            raise ValueError("Partner metadata requires press_time")
        published = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if published.tzinfo is None:
            raise ValueError("press_time requires an explicit timezone")
        # Source categories supplement title classification; no issuer location is assumed.
        categories = []
        category = row.get("category", row.get("catetory", {}))
        if isinstance(category, dict):
            for item in category.get("industry", []):
                if isinstance(item, dict) and isinstance(item.get("cat"), dict):
                    name = item["cat"].get("name")
                    if isinstance(name, str):
                        categories.append(clean_title(name))
        entries.append(
            Entry(title, url, str(newsid), published.astimezone(UTC), categories, action=action)
        )
    return entries


class NewswireSourceAdapter:
    max_bytes = 8 * 1024 * 1024

    def __init__(self, partner_id=None, api_key=None, transport=None):
        self.partner_id = partner_id or settings.newswire_partner_id
        self.api_key = api_key or (
            settings.newswire_api_key.get_secret_value() if settings.newswire_api_key else None
        )
        self.transport = transport

    def _post(self, client, path, body, authenticate=False):
        headers = {"Content-Type": "application/json", "User-Agent": "IssueAreaCollector/0.1"}
        if authenticate:
            # Mandatory header specifies milliseconds; use the same value in the HMAC input.
            timestamp = str(time.time_ns() // 1_000_000)
            headers.update(
                {"X-Timestamp": timestamp, "X-HMAC": signature(self.api_key, path, timestamp)}
            )
        with client.stream("POST", API_BASE + path, json=body, headers=headers) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > self.max_bytes:
                    raise ValueError("Partner API response exceeds size limit")
        payload = json.loads(data)
        if not isinstance(payload, dict) or str(payload.get("statuscode")) != "200":
            raise ValueError("Partner API returned an unsuccessful response")
        return payload

    def fetch(self, source) -> FetchResult:
        if not self.partner_id or not self.api_key:
            raise ValueError("Newswire partner ID and API key are required")
        # Fixed origin and no redirects prevent credentials being forwarded to another host.
        with httpx.Client(timeout=20, follow_redirects=False, transport=self.transport) as client:
            request = self._post(client, "/api/v1/request", {"partner_id": self.partner_id}, True)
            matched = request.get("matched_count")
            if type(matched) is not int or not 0 <= matched <= 100:
                raise ValueError("Invalid partner API matched_count")
            if matched == 0:
                if request.get("status") != "completed":
                    raise ValueError("Empty partner API request is not completed")
                return FetchResult([])
            request_id = request.get("request_id")
            if request.get("status") != "processing" or not isinstance(request_id, str):
                raise ValueError("Partner API request is not ready")
            payload = self._post(client, "/api/v1/send", {"request_id": request_id})
            entries = parse_events(payload)
            if payload.get("matched_count") != len(entries):
                raise ValueError("Partner API event count mismatch")
            return FetchResult(entries)
