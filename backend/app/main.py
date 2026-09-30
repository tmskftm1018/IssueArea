from contextlib import asynccontextmanager
from datetime import UTC, timedelta
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db import SessionLocal, get_session, utcnow
from app.models import Article, ArticleRegion, ArticleTopic, CollectionRun, Region, Source, Topic
from app.safety import check_startup
from app.services import can_collect


@asynccontextmanager
async def lifespan(app):
    with SessionLocal() as session:
        check_startup(session)
    yield


app = FastAPI(title="IssueArea API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)
DB = Annotated[Session, Depends(get_session)]


def filtered(session, hours, topics, q, region=None):
    if hours not in {1, 6, 24, 168}:
        raise HTTPException(422, "hours must be one of 1, 6, 24, 168")
    query = select(Article).where(
        func.coalesce(Article.published_at, Article.collected_at)
        >= utcnow() - timedelta(hours=hours),
        func.coalesce(Article.published_at, Article.collected_at) <= utcnow(),
    )
    # Apply registry visibility rules to historical records as well as new collections.
    visible = select(Source.id).where(
        Source.enabled.is_(True),
        Source.rights_status.in_(["allowed", "conditional"]),
        Source.title_display_allowed.is_(True),
        Source.metadata_storage_allowed.is_(True),
    )
    if settings.app_usage_mode == "commercial":
        visible = visible.where(Source.commercial_use_allowed.is_(True))
    if not settings.demo_mode:
        visible = visible.where(Source.adapter_type != "demo")
    query = query.where(Article.source_id.in_(visible))
    # Hide previously collected, non-local NewsData headlines after tightening its
    # collection rules. This leaves other RSS and press-release sources unaffected.
    newsdata_sources = select(Source.id).where(Source.adapter_type == "newsdata")
    query = query.where(
        (Article.source_id.not_in(newsdata_sources)) | (Article.geo_scope == "regional")
    )
    if topics:
        slugs = set(topics.split(","))
        known = set(session.scalars(select(Topic.slug)))
        if not slugs <= known:
            raise HTTPException(422, "Unknown topic")
        query = query.where(
            Article.id.in_(select(ArticleTopic.article_id).join(Topic).where(Topic.slug.in_(slugs)))
        )
    if q:
        query = query.where(Article.title.contains(q, autoescape=True))
    if region:
        # Keep previously shared Jeollanam-do filter URLs useful after the 2026 merger.
        if region == "KR-46":
            region = "KR-29"
        region_id = session.scalar(select(Region.id).where(Region.code == region))
        if region_id is None:
            raise HTTPException(422, "Unknown region")
        query = query.where(
            Article.id.in_(
                select(ArticleRegion.article_id).where(ArticleRegion.region_id == region_id)
            )
        )
    return query


def iso(value):
    if value is None:
        return None
    return value.replace(tzinfo=UTC).isoformat() if value.tzinfo is None else value.isoformat()


@app.get("/health")
def health(session: DB):
    session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/v1/regions")
def regions(session: DB):
    return [
        {
            "code": r.code,
            "name": r.name,
            "short_name": r.short_name,
            "latitude": r.latitude,
            "longitude": r.longitude,
        }
        for r in session.scalars(select(Region).order_by(Region.id))
    ]


@app.get("/api/v1/topics")
def topics(session: DB):
    return [{"slug": t.slug, "name": t.name} for t in session.scalars(select(Topic))]


@app.get("/api/v1/news")
def news(
    session: DB,
    hours: int = 24,
    topics: str = Query(default="", max_length=300),
    q: str = Query(default="", max_length=200),
    region: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    query = filtered(session, hours, topics, q, region)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    articles = session.scalars(
        query.options(
            selectinload(Article.source),
            selectinload(Article.regions).selectinload(ArticleRegion.region),
            selectinload(Article.topics).selectinload(ArticleTopic.topic),
        )
        .order_by(
            func.coalesce(Article.published_at, Article.collected_at).desc(), Article.id.desc()
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": a.id,
                "title": a.title,
                "source": a.publisher_name or a.source.name,
                "content_type": "press_release"
                if a.source.adapter_type in {"newswire", "rss_press_release"}
                else "news",
                "url": a.original_url,
                "published_at": iso(a.published_at),
                "collected_at": iso(a.collected_at),
                "geo_scope": a.geo_scope,
                "regions": [{"code": ar.region.code, "name": ar.region.name} for ar in a.regions],
                "topics": [{"slug": at.topic.slug, "name": at.topic.name} for at in a.topics],
            }
            for a in articles
        ],
    }


@app.get("/api/v1/map/regions")
def map_regions(
    session: DB,
    hours: int = 24,
    topics: str = Query(default="", max_length=300),
    q: str = Query(default="", max_length=200),
):
    matched = filtered(session, hours, topics, q).subquery()
    counts = dict(
        session.execute(
            select(ArticleRegion.region_id, func.count(func.distinct(ArticleRegion.article_id)))
            .join(matched, matched.c.id == ArticleRegion.article_id)
            .group_by(ArticleRegion.region_id)
        ).all()
    )
    unmapped = session.scalar(
        select(func.count()).select_from(matched).where(matched.c.geo_scope != "regional")
    )
    return {
        "regions": [
            {
                "code": r.code,
                "name": r.name,
                "short_name": r.short_name,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "count": counts.get(r.id, 0),
            }
            for r in session.scalars(select(Region))
        ],
        "unmapped_count": unmapped,
    }


@app.get("/api/v1/system/freshness")
def freshness(session: DB):
    sources = [
        s
        for s in session.scalars(select(Source))
        if can_collect(s, settings.app_usage_mode)
        and (s.adapter_type != "demo" or settings.demo_mode)
    ]

    def source_is_healthy(source):
        stamp = source.last_success_at
        if stamp and stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
        threshold = timedelta(minutes=max(15, source.collection_interval_minutes * 3))
        return bool(stamp and not source.consecutive_failures and stamp >= utcnow() - threshold)

    healthy = [s for s in sources if source_is_healthy(s)]
    last = session.scalar(
        select(func.max(CollectionRun.finished_at)).where(
            CollectionRun.status.in_(["success", "not_modified"]),
            CollectionRun.source_id.in_([s.id for s in sources]),
        )
    )
    return {
        "last_successful_collection_at": iso(last),
        "status": "stale"
        if not healthy
        else ("healthy" if len(healthy) == len(sources) else "degraded"),
        "enabled_sources": len(sources),
        "healthy_sources": len(healthy),
        "demo_mode": settings.demo_mode,
    }
