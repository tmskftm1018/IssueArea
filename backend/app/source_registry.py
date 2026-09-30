"""Operator-only source registry commands; no public mutation API is exposed."""

import argparse
import ipaddress
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal, utcnow
from app.models import CollectionRun, Source
from app.services import can_collect, canonical_url


def validate_registry_url(url: str) -> str:
    # Validate, but preserve feed parameters (they can identify the feed or authorize access).
    canonical_url(url)
    host = urlsplit(url.strip()).hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith((".localhost", ".local")):
        raise ValueError("Registry URLs must target public hosts")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and not address.is_global:
        raise ValueError("Registry URLs must not target private or reserved IP addresses")
    if len(url) > 2048:
        raise ValueError("URL exceeds 2048 characters")
    return url.strip()


class RightsReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    rights_status: Literal["unreviewed", "allowed", "conditional", "prohibited"]
    title_display_allowed: bool
    metadata_storage_allowed: bool
    commercial_use_allowed: bool
    terms_url: str
    terms_checked_at: datetime
    notes: str = Field(min_length=10, max_length=2000)

    @field_validator("terms_url")
    @classmethod
    def terms_url_is_public(cls, value):
        return validate_registry_url(value)

    @field_validator("terms_checked_at")
    @classmethod
    def valid_review_time(cls, value):
        if value.tzinfo is None or value > utcnow():
            raise ValueError("Review time must include a timezone and must not be in the future")
        return value.astimezone(UTC)


def add_source(
    session, name: str, feed_url: str, terms_url: str, interval: int = 5, adapter: str = "rss"
):
    name = name.strip()
    if not name or len(name) > 200:
        raise ValueError("Source name must contain 1–200 characters")
    if not 1 <= interval <= 1440:
        raise ValueError("Collection interval must be between 1 and 1440 minutes")
    feed_url = validate_registry_url(feed_url)
    terms_url = validate_registry_url(terms_url)
    if adapter not in {"rss", "rss_press_release", "newswire", "newsdata"}:
        raise ValueError("Unsupported source adapter")
    if adapter == "newsdata":
        if feed_url != "https://newsdata.io/api/1/latest" or interval < 10:
            raise ValueError("NewsData requires the official endpoint and at least 10 minutes")
        if session.scalar(select(Source.id).where(Source.adapter_type == "newsdata")):
            raise ValueError("Only one NewsData source can use this free account")
    if adapter == "newswire":
        if feed_url != "https://www.newswire.co.kr/api/v1/request" or interval < 5:
            raise ValueError(
                "Newswire requires the official endpoint and a minimum 5-minute interval"
            )
        if session.scalar(select(Source.id).where(Source.adapter_type == "newswire")):
            raise ValueError("Only one Newswire partner source can use this account")
    if session.scalar(select(Source.id).where(Source.feed_url == feed_url)):
        raise ValueError("This feed URL is already registered")
    source = Source(
        name=name,
        adapter_type=adapter,
        feed_url=feed_url,
        terms_url=terms_url,
        collection_interval_minutes=interval,
        enabled=False,
        rights_status="unreviewed",
    )
    session.add(source)
    session.commit()
    return source


def find_source(session, source_id: int):
    source = session.get(Source, source_id)
    if source is None:
        raise ValueError(f"Source {source_id} does not exist")
    return source


def review_source(session, source_id: int, review: RightsReview):
    source = find_source(session, source_id)
    if source.adapter_type == "demo":
        raise ValueError("Demo rights are managed by seed, not publisher review")
    for key, value in review.model_dump().items():
        setattr(source, key, value)
    # Editing rights requires a separate explicit enable command, even if previously enabled.
    source.enabled = False
    session.commit()
    return source


def set_enabled(session, source_id: int, enabled: bool):
    source = find_source(session, source_id)
    if source.adapter_type == "demo":
        raise ValueError("Demo activation is controlled by DEMO_MODE")
    if enabled:
        if (
            source.adapter_type not in {"rss", "rss_press_release", "newswire", "newsdata"}
            or not source.terms_checked_at
            or not source.notes
        ):
            raise ValueError("Source requires a recorded rights review and supported adapter")
        validate_registry_url(source.feed_url)
        validate_registry_url(source.terms_url)
        if source.adapter_type == "newsdata":
            if (
                source.feed_url != "https://newsdata.io/api/1/latest"
                or source.collection_interval_minutes < 10
            ):
                raise ValueError("Invalid free NewsData source configuration")
            if not settings.newsdata_api_key:
                raise ValueError("NewsData API key must be configured before activation")
        if source.adapter_type == "newswire":
            if source.feed_url != "https://www.newswire.co.kr/api/v1/request":
                raise ValueError("Newswire requires the official endpoint")
            if source.collection_interval_minutes < 5:
                raise ValueError("Newswire requires a minimum 5-minute interval")
            if not settings.newswire_partner_id or not settings.newswire_api_key:
                raise ValueError(
                    "Newswire partner credentials must be configured before activation"
                )
        source.enabled = True
        if not can_collect(source, settings.app_usage_mode):
            source.enabled = False
            raise ValueError("Source rights do not permit collection in the current usage mode")
        source.next_fetch_at = utcnow()
    else:
        source.enabled = False
    session.commit()
    return source


def source_status(session):
    rows = []
    for source in session.scalars(select(Source).order_by(Source.id)):
        last_run = session.scalar(
            select(CollectionRun)
            .where(CollectionRun.source_id == source.id)
            .order_by(CollectionRun.id.desc())
            .limit(1)
        )
        # Feed URLs are omitted because a registry URL may contain an access token.
        rows.append(
            {
                "id": source.id,
                "name": source.name,
                "adapter": source.adapter_type,
                "enabled": source.enabled,
                "rights_status": source.rights_status,
                "collectable": can_collect(source, settings.app_usage_mode)
                and (source.adapter_type != "demo" or settings.demo_mode),
                "interval_minutes": source.collection_interval_minutes,
                "consecutive_failures": source.consecutive_failures,
                "next_fetch_at": str(source.next_fetch_at) if source.next_fetch_at else None,
                "last_run": {
                    "status": last_run.status,
                    "inserted": last_run.inserted_count,
                    "duplicates": last_run.duplicate_count,
                    "updated": last_run.updated_count,
                    "deleted": last_run.deleted_count,
                    "http_status": last_run.http_status,
                    "error_type": last_run.error_type,
                }
                if last_run
                else None,
            }
        )
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    add = sub.add_parser("add")
    add.add_argument("--name", required=True)
    add.add_argument("--feed-url", required=True)
    add.add_argument("--terms-url", required=True)
    add.add_argument("--interval", type=int, default=5)
    add.add_argument(
        "--adapter",
        choices=["rss", "rss_press_release", "newswire", "newsdata"],
        default="rss",
    )
    review = sub.add_parser("review")
    review.add_argument("source_id", type=int)
    review.add_argument("--file", type=Path, required=True)
    for command in ("enable", "disable"):
        sub.add_parser(command).add_argument("source_id", type=int)
    args = parser.parse_args(argv)
    try:
        with SessionLocal() as session:
            if args.command == "list":
                print(json.dumps(source_status(session), ensure_ascii=False, indent=2))
                return
            if args.command == "add":
                source = add_source(
                    session, args.name, args.feed_url, args.terms_url, args.interval, args.adapter
                )
            elif args.command == "review":
                data = RightsReview.model_validate_json(args.file.read_text(encoding="utf-8"))
                source = review_source(session, args.source_id, data)
            else:
                source = set_enabled(session, args.source_id, args.command == "enable")
            print(
                json.dumps(
                    {
                        "id": source.id,
                        "enabled": source.enabled,
                        "rights_status": source.rights_status,
                    },
                    ensure_ascii=False,
                )
            )
    except (ValueError, OSError):
        # Validation errors can include the submitted URL; do not echo possible feed secrets.
        parser.exit(2, "Source command rejected: check input, review fields, and usage rights.\n")


if __name__ == "__main__":
    main()
