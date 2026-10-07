from contextlib import asynccontextmanager
from datetime import UTC, timedelta
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db import SessionLocal, get_session, utcnow
from app.models import Article, ArticleRegion, ArticleTopic, CollectionRun, Region, Source, Topic
from app.safety import check_startup
from app.services import can_collect
from app.sources import MOIS_PRESS_RELEASE_FEED
from app.vworld import VWorldError, get_sigungu_boundaries


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


def filtered(session, hours, topics, q, region=None, locality=None):
    if hours not in {1, 6, 24, 168}:
        raise HTTPException(422, "hours must be one of 1, 6, 24, 168")
    now = utcnow()
    since = now - timedelta(hours=hours)
    date_only_published = (
        (Article.published_precision == "date")
        & (Article.published_at > since - timedelta(days=1))
        & (Article.published_at <= now)
    )
    exact_or_unknown_published = (
        Article.published_precision.is_distinct_from("date")
        & (func.coalesce(Article.published_at, Article.collected_at) >= since)
        & (func.coalesce(Article.published_at, Article.collected_at) <= now)
    )
    query = select(Article).where(date_only_published | exact_or_unknown_published)
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
    # Don't treat newly imported MOIS headlines as recent when their page date
    # could not be read; retries can fill the date on the next collection run.
    mois_sources = select(Source.id).where(Source.feed_url == MOIS_PRESS_RELEASE_FEED)
    query = query.where(
        (Article.source_id.not_in(mois_sources)) | Article.published_at.is_not(None)
    )
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
    if locality:
        if not region or len(locality) < 2 or len(locality) > 40:
            raise HTTPException(422, "locality requires a valid region and a 2–40 character name")
        query = query.where(locality_title_match(Article.title, locality, region))
    return query


def iso(value):
    if value is None:
        return None
    return value.replace(tzinfo=UTC).isoformat() if value.tzinfo is None else value.isoformat()


LOCALITY_TITLE_ALIASES = {"KR-11": {"용산구": ("이태원", "이태원참사")}}


def locality_title_terms(locality: str, region: str | None = None) -> tuple[str, ...]:
    """Return full and commonly shortened names used in Korean headlines."""
    parts = locality.split()
    leaf = parts[-1]
    terms = {locality, leaf}
    for suffix in ("시", "군", "구"):
        if leaf.endswith(suffix) and len(leaf) > 1:
            terms.add(leaf[:-1])
    terms.update(LOCALITY_TITLE_ALIASES.get(region or "", {}).get(locality, ()))
    return tuple(sorted(terms))


def locality_title_match(column, locality: str, region: str | None = None):
    return or_(
        *(column.contains(term, autoescape=True) for term in locality_title_terms(locality, region))
    )


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
    locality: str | None = Query(default=None, max_length=40),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    query = filtered(session, hours, topics, q, region, locality)
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
                if a.source.adapter_type
                in {
                    "newswire",
                    "rss_press_release",
                    "mods_press_release",
                    "gyeonggi_press_release",
                    "daegu_press_release",
                    "jeonnam_press_release",
                }
                else "news",
                "url": a.original_url,
                "published_at": iso(a.published_at),
                "published_precision": a.published_precision,
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


REGION_SIGUNGU_PREFIXES = {
    # VWorld's current SIG_CD values reflect the latest special self-governing
    # province and integrated city codes (51, 52, and 12 respectively).
    "KR-11": ("11",),
    "KR-26": ("26",),
    "KR-27": ("27",),
    "KR-28": ("28",),
    "KR-29": ("12",),  # Gwangju–Jeonnam integrated area
    "KR-30": ("30",),
    "KR-31": ("31",),
    "KR-50": ("36",),
    "KR-41": ("41",),
    "KR-51": ("51",),
    "KR-43": ("43",),
    "KR-44": ("44",),
    "KR-52": ("52",),
    "KR-47": ("47",),
    "KR-48": ("48",),
    "KR-49": ("50",),
}


@app.get("/api/v1/map/subregions")
def map_subregions(
    session: DB,
    region: str,
    hours: int = 24,
    topics: str = Query(default="", max_length=300),
    q: str = Query(default="", max_length=200),
):
    prefixes = REGION_SIGUNGU_PREFIXES.get(region)
    if not prefixes:
        raise HTTPException(422, "Unknown region")
    try:
        collection = get_sigungu_boundaries()
    except VWorldError as exc:
        detail = "시군구 경계를 불러오지 못했습니다. API 키와 도메인 설정을 확인해 주세요."
        raise HTTPException(502, detail) from exc

    features = []
    matched = filtered(session, hours, topics, q, region).subquery()
    for feature in collection["features"]:
        props = feature.get("properties") or {}
        code = str(props.get("sig_cd") or "")
        name = str(props.get("sig_kor_nm") or "").strip()
        if not name or not any(code.startswith(prefix) for prefix in prefixes):
            continue
        count = session.scalar(
            select(func.count(func.distinct(matched.c.id))).where(
                locality_title_match(matched.c.title, name, region)
            )
        ) or 0
        features.append({
            "type": "Feature",
            "geometry": feature.get("geometry"),
            "properties": {"code": code, "name": name, "count": count},
        })
    if not features:
        raise HTTPException(502, "시군구 경계 응답이 비어 있습니다.")
    return {"type": "FeatureCollection", "features": features}


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
