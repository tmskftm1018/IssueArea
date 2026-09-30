import hashlib
import html
import re
import unicodedata
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.models import Source


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def clean_title(raw: str) -> str:
    parser = TextParser()
    parser.feed(html.unescape(raw))
    text = unicodedata.normalize("NFKC", " ".join(parser.parts))
    text = "".join(c for c in text if not unicodedata.category(c).startswith("C"))
    return re.sub(r"\s+", " ", text).strip()[:1000]


def canonical_url(raw: str) -> str:
    parts = urlsplit(raw.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("Only absolute HTTP(S) article URLs are allowed")
    if parts.username or parts.password:
        raise ValueError("URL credentials are forbidden")
    host = parts.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    if parts.port and (parts.scheme, parts.port) not in {("http", 80), ("https", 443)}:
        host += f":{parts.port}"
    tracking = {"fbclid", "gclid"}
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in tracking
    ]
    return urlunsplit((parts.scheme.lower(), host, parts.path or "/", urlencode(query), ""))


def title_hash(title: str) -> str:
    return hashlib.sha256(title.casefold().encode()).hexdigest()


def can_collect(source: Source, usage_mode: str) -> bool:
    return bool(
        source.enabled
        and source.rights_status in {"allowed", "conditional"}
        and source.title_display_allowed
        and source.metadata_storage_allowed
        and (usage_mode != "commercial" or source.commercial_use_allowed)
    )
