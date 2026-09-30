from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow


class Source(Base):
    __tablename__ = "news_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    adapter_type: Mapped[str] = mapped_column(String(30))
    feed_url: Mapped[str | None] = mapped_column(String(2048))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    rights_status: Mapped[str] = mapped_column(String(30), default="unreviewed")
    commercial_use_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    title_display_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    terms_url: Mapped[str | None] = mapped_column(String(2048))
    terms_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(String(2000))
    collection_interval_minutes: Mapped[int] = mapped_column(Integer, default=5)
    etag: Mapped[str | None] = mapped_column(String(500))
    last_modified: Mapped[str | None] = mapped_column(String(500))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_fetch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Region(Base):
    __tablename__ = "regions"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    short_name: Mapped[str] = mapped_column(String(20))
    level: Mapped[int] = mapped_column(default=1)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    aliases: Mapped[list[str]] = mapped_column(JSON)


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(50))


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id"),
        UniqueConstraint("source_id", "canonical_url"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("news_sources.id"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(1024))
    title: Mapped[str] = mapped_column(String(1000))
    publisher_name: Mapped[str | None] = mapped_column(String(200))
    original_url: Mapped[str] = mapped_column(String(2048))
    canonical_url: Mapped[str] = mapped_column(String(2048), index=True)
    title_hash: Mapped[str] = mapped_column(String(64), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    geo_scope: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    source: Mapped[Source] = relationship()
    regions: Mapped[list["ArticleRegion"]] = relationship(cascade="all, delete-orphan")
    topics: Mapped[list["ArticleTopic"]] = relationship(cascade="all, delete-orphan")


class ArticleRegion(Base):
    __tablename__ = "article_regions"
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), primary_key=True, index=True)
    confidence: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(50))
    classifier_version: Mapped[str] = mapped_column(String(30))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    region: Mapped[Region] = relationship()


class ArticleTopic(Base):
    __tablename__ = "article_topics"
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), primary_key=True, index=True)
    confidence: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(50))
    classifier_version: Mapped[str] = mapped_column(String(30))
    topic: Mapped[Topic] = relationship()


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("news_sources.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30))
    http_status: Mapped[int | None] = mapped_column(Integer)
    fetched_count: Mapped[int] = mapped_column(default=0)
    inserted_count: Mapped[int] = mapped_column(default=0)
    duplicate_count: Mapped[int] = mapped_column(default=0)
    updated_count: Mapped[int] = mapped_column(default=0)
    deleted_count: Mapped[int] = mapped_column(default=0)
    error_type: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(1000))
