from sqlalchemy import select

from app.catalog import REGIONS, TOPICS
from app.config import settings
from app.db import SessionLocal, utcnow
from app.models import Region, Source, Topic


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
    session.commit()


if __name__ == "__main__":
    with SessionLocal() as session:
        seed(session)
