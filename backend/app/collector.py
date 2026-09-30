import argparse
import json
import logging
import time
from datetime import timedelta

import httpx
from sqlalchemy import delete, func, or_, select

from app.classifiers import RuleBasedRegionClassifier, RuleBasedTopicClassifier
from app.config import settings
from app.db import SessionLocal, utcnow
from app.models import Article, ArticleRegion, ArticleTopic, CollectionRun, Region, Source, Topic
from app.newsdata import FreeQuotaExceeded, NewsDataSourceAdapter
from app.newswire import NewswireSourceAdapter
from app.services import can_collect, canonical_url, clean_title, title_hash
from app.sources import DemoSourceAdapter, RSSSourceAdapter

log = logging.getLogger("collector")


def collect_source(session, source, adapter=None):
    if not can_collect(source, settings.app_usage_mode):
        raise PermissionError("Source is disabled or does not have permitted usage rights")
    if source.adapter_type == "demo" and not settings.demo_mode:
        raise PermissionError("Demo mode is disabled")
    if source.adapter_type not in {"demo", "rss", "rss_press_release", "newswire", "newsdata"}:
        raise ValueError("Unsupported source adapter")
    if source.adapter_type == "newsdata":
        attempts = session.scalar(
            select(func.count())
            .select_from(CollectionRun)
            .where(
                CollectionRun.source_id == source.id,
                CollectionRun.started_at >= utcnow() - timedelta(hours=24),
            )
        )
        if attempts >= 180:
            source.next_fetch_at = utcnow() + timedelta(hours=24)
            session.commit()
            return None
    run = CollectionRun(source_id=source.id, status="running")
    session.add(run)
    session.flush()
    try:
        adapters = {
            "demo": DemoSourceAdapter,
            "rss": RSSSourceAdapter,
            "rss_press_release": RSSSourceAdapter,
            "newswire": NewswireSourceAdapter,
            "newsdata": NewsDataSourceAdapter,
        }
        adapter = adapter or adapters[source.adapter_type]()
        # A savepoint makes failed imports atomic while keeping the failure run observable.
        with session.begin_nested():
            result = adapter.fetch(source)
            run.http_status = result.status
            run.fetched_count = len(result.entries)
            regions = list(session.scalars(select(Region)))
            topics = {t.slug: t.id for t in session.scalars(select(Topic))}
            for entry in result.entries:
                existing = (
                    session.scalar(
                        select(Article).where(
                            Article.source_id == source.id, Article.external_id == entry.external_id
                        )
                    )
                    if entry.external_id
                    else None
                )
                if entry.action != "insert" and source.adapter_type != "newswire":
                    raise ValueError("Update/delete events require a supported partner source")
                if entry.action == "delete":
                    if existing:
                        session.delete(existing)
                        session.flush()
                        run.deleted_count += 1
                    continue
                title = clean_title(entry.title)
                try:
                    url = canonical_url(entry.url)
                except ValueError:
                    continue
                if not title:
                    continue
                stamp = entry.published_at or utcnow()
                digest = title_hash(title)
                conditions = [Article.canonical_url == url]
                if entry.external_id:
                    conditions.append(Article.external_id == entry.external_id)
                conditions.append(
                    (Article.title_hash == digest)
                    & (
                        func.coalesce(Article.published_at, Article.collected_at)
                        >= stamp - timedelta(hours=24)
                    )
                    & (
                        func.coalesce(Article.published_at, Article.collected_at)
                        <= stamp + timedelta(hours=24)
                    )
                )
                updating = existing is not None and entry.action == "update"
                if not updating and session.scalar(
                    select(Article.id).where(Article.source_id == source.id, or_(*conditions))
                ):
                    run.duplicate_count += 1
                    continue
                region_ids = RuleBasedRegionClassifier().classify(
                    f"{title} {source.name}", regions
                )
                # NewsData's broad national feed is useful only when the headline
                # itself identifies a place; otherwise it pollutes the local issue map.
                if source.adapter_type == "newsdata" and not region_ids:
                    continue
                slugs, method = RuleBasedTopicClassifier().classify(title, entry.categories)
                article = existing if updating else Article(source_id=source.id)
                values = dict(
                    source_id=source.id,
                    external_id=entry.external_id,
                    title=title,
                    original_url=entry.url.strip(),
                    canonical_url=url,
                    title_hash=digest,
                    publisher_name=entry.publisher_name or source.name,
                    published_at=entry.published_at,
                    geo_scope="regional"
                    if region_ids
                    else ("national" if "전국" in title else "unknown"),
                )
                for key, value in values.items():
                    setattr(article, key, value)
                if updating:
                    article.regions.clear()
                    article.topics.clear()
                    session.flush()
                article.regions = [
                    ArticleRegion(
                        region_id=rid,
                        confidence=1.0,
                        method="title_alias",
                        classifier_version="rules-v1",
                        is_primary=i == 0,
                    )
                    for i, rid in enumerate(region_ids)
                ]
                article.topics = [
                    ArticleTopic(
                        topic_id=topics[slug],
                        confidence=1.0 if method == "source_category" else 0.7,
                        method=method,
                        classifier_version="rules-v1",
                    )
                    for slug in slugs
                ]
                session.add(article)
                session.flush()
                if updating:
                    run.updated_count += 1
                else:
                    run.inserted_count += 1
            if result.etag:
                source.etag = result.etag
            if result.last_modified:
                source.last_modified = result.last_modified
        run.status = "not_modified" if result.status == 304 else "success"
        source.last_success_at = utcnow()
        source.consecutive_failures = 0
        source.next_fetch_at = utcnow() + timedelta(minutes=source.collection_interval_minutes)
    except Exception as exc:
        run.status = "failed"
        run.inserted_count = 0
        run.duplicate_count = 0
        run.updated_count = 0
        run.deleted_count = 0
        run.error_type = type(exc).__name__
        if isinstance(exc, httpx.HTTPStatusError):
            run.http_status = exc.response.status_code
        # Avoid logging request URLs, which may carry registry credentials.
        run.error_message = "Source collection failed; inspect adapter and source configuration."
        source.consecutive_failures += 1
        source.next_fetch_at = utcnow() + timedelta(
            minutes=min(
                source.collection_interval_minutes * 2 ** min(source.consecutive_failures, 6), 360
            )
        )
        if isinstance(exc, FreeQuotaExceeded):
            run.http_status = 429
            source.next_fetch_at = utcnow() + timedelta(hours=24)
    run.finished_at = utcnow()
    session.commit()
    log.info(
        json.dumps(
            {
                "timestamp": utcnow().isoformat(),
                "level": "INFO",
                "component": "collector",
                "source": source.id,
                "event": run.status,
                "message": f"inserted={run.inserted_count}, duplicate={run.duplicate_count}, "
                f"updated={run.updated_count}, deleted={run.deleted_count}",
            }
        )
    )
    return run


def collect_due(source_id=None):
    from app.safety import check_startup

    with SessionLocal() as session:
        check_startup(session)
        query = select(Source.id).where(Source.enabled.is_(True))
        if source_id is not None:
            query = query.where(Source.id == source_id)
        source_ids = list(session.scalars(query))
    for source_id in source_ids:
        with SessionLocal() as session:
            # PostgreSQL row lock prevents concurrent collectors claiming the same source.
            source = session.scalar(
                select(Source)
                .where(
                    Source.id == source_id,
                    or_(Source.next_fetch_at.is_(None), Source.next_fetch_at <= utcnow()),
                )
                .with_for_update(skip_locked=True)
            )
            if source and can_collect(source, settings.app_usage_mode):
                if source.adapter_type != "demo" or settings.demo_mode:
                    collect_source(session, source)
    with SessionLocal() as session:
        session.execute(
            delete(Article).where(
                Article.collected_at < utcnow() - timedelta(days=settings.article_retention_days)
            )
        )
        session.commit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--source-id", type=int)
    args = parser.parse_args()
    while True:
        collect_due(args.source_id)
        if args.once:
            break
        time.sleep(settings.collector_poll_seconds)
