from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.catalog import REGIONS, TOPICS
from app.classifiers import RuleBasedRegionClassifier
from app.config import settings
from app.db import SessionLocal, utcnow
from app.models import Article, ArticleRegion, Region, Source, Topic
from app.sources import MOIS_PRESS_RELEASE_FEED


def seed(session):
    for code, name, short, lat, lon, aliases in REGIONS:
        region = session.scalar(select(Region).where(Region.code == code))
        if region is None:
            session.add(
                Region(
                    code=code,
                    name=name,
                    short_name=short,
                    latitude=lat,
                    longitude=lon,
                    aliases=aliases,
                )
            )
        else:
            # Keep existing databases aligned with catalog fixes as well as new installs.
            region.name = name
            region.short_name = short
            region.latitude = lat
            region.longitude = lon
            region.aliases = aliases
    for slug, (name, _) in TOPICS.items():
        if not session.scalar(select(Topic).where(Topic.slug == slug)):
            session.add(Topic(slug=slug, name=name))
    demo = session.scalar(select(Source).where(Source.adapter_type == "demo"))
    if settings.demo_mode and not demo:
        session.add(
            Source(
                name="IssueArea 개발용 예시",
                adapter_type="demo",
                enabled=True,
                rights_status="allowed",
                commercial_use_allowed=True,
                title_display_allowed=True,
                metadata_storage_allowed=True,
                terms_checked_at=utcnow(),
                notes="가상 개발용 제목. 실제 뉴스가 아닙니다.",
            )
        )
    if demo:
        demo.name = "IssueArea 개발용 예시"
        demo.enabled = settings.demo_mode
    region_rows = list(session.scalars(select(Region)))
    classifier = RuleBasedRegionClassifier()
    for article in session.scalars(
        select(Article).options(selectinload(Article.regions), selectinload(Article.source))
    ):
        region_ids = classifier.classify(
            f"{article.title} {article.source.name}", region_rows
        )
        existing_ids = {tag.region_id for tag in article.regions}
        existing_versions = {tag.classifier_version for tag in article.regions}
        if (
            existing_ids != set(region_ids)
            or existing_versions != ({classifier.version} if region_ids else set())
        ):
            article.regions = [
                ArticleRegion(
                    region_id=region_id,
                    confidence=1.0,
                    method="title_alias",
                    classifier_version=classifier.version,
                    is_primary=index == 0,
                )
                for index, region_id in enumerate(region_ids)
            ]
        article.geo_scope = (
            "regional"
            if region_ids
            else "national"
            if article.source.feed_url == MOIS_PRESS_RELEASE_FEED or "전국" in article.title
            else "unknown"
        )
    session.commit()


if __name__ == "__main__":
    with SessionLocal() as session:
        seed(session)
