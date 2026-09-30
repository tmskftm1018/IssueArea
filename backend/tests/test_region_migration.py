from datetime import UTC, datetime

from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from alembic import command
from app import db
from app.models import Article, ArticleRegion, Region, Source


def test_merge_gwangju_jeonnam_is_reversible(tmp_path, monkeypatch):
    database = tmp_path / "region-migration.sqlite"
    migration_engine = create_engine(f"sqlite:///{database}")
    monkeypatch.setattr(db, "engine", migration_engine)
    config = Config("alembic.ini")

    command.upgrade(config, "a712e938c0d4")
    with Session(migration_engine) as session:
        gwangju = Region(
            code="KR-29",
            name="광주광역시",
            short_name="광주",
            latitude=35.1595,
            longitude=126.8526,
            aliases=["광주광역시"],
        )
        jeonnam = Region(
            code="KR-46",
            name="전라남도",
            short_name="전남",
            latitude=34.8161,
            longitude=126.4629,
            aliases=["전남", "전라남도"],
        )
        source = Source(
            name="migration test",
            adapter_type="rss",
            enabled=False,
            rights_status="unreviewed",
        )
        session.add_all([gwangju, jeonnam, source])
        session.flush()
        both = Article(
            source_id=source.id,
            title="통합 지역 기사",
            original_url="https://example.test/both",
            canonical_url="https://example.test/both",
            title_hash="both",
            published_at=datetime(2026, 9, 30, tzinfo=UTC),
            geo_scope="regional",
        )
        jeonnam_only = Article(
            source_id=source.id,
            title="전남 기사",
            original_url="https://example.test/jeonnam",
            canonical_url="https://example.test/jeonnam",
            title_hash="jeonnam",
            published_at=datetime(2026, 9, 30, tzinfo=UTC),
            geo_scope="regional",
        )
        session.add_all([both, jeonnam_only])
        session.flush()
        session.add_all(
            [
                ArticleRegion(
                    article_id=both.id,
                    region_id=gwangju.id,
                    confidence=0.8,
                    method="title_alias",
                    classifier_version="rules-v1",
                    is_primary=True,
                ),
                ArticleRegion(
                    article_id=both.id,
                    region_id=jeonnam.id,
                    confidence=0.9,
                    method="title_alias",
                    classifier_version="rules-v1",
                    is_primary=False,
                ),
                ArticleRegion(
                    article_id=jeonnam_only.id,
                    region_id=jeonnam.id,
                    confidence=0.7,
                    method="title_alias",
                    classifier_version="rules-v1",
                    is_primary=True,
                ),
            ]
        )
        session.commit()
        both_id, jeonnam_id = both.id, jeonnam_only.id
        gwangju_id, old_jeonnam_id = gwangju.id, jeonnam.id

    command.upgrade(config, "head")
    with Session(migration_engine) as session:
        merged = session.scalar(select(Region).where(Region.code == "KR-29"))
        assert merged.name == "전남광주통합특별시"
        assert session.scalar(select(Region).where(Region.code == "KR-46")) is None
        both_tags = list(
            session.scalars(
                select(ArticleRegion).where(ArticleRegion.article_id == both_id)
            )
        )
        assert len(both_tags) == 1
        assert both_tags[0].region_id == merged.id
        assert both_tags[0].confidence == 0.9
        assert both_tags[0].is_primary is True
        jeonnam_tag = session.scalar(
            select(ArticleRegion).where(ArticleRegion.article_id == jeonnam_id)
        )
        assert jeonnam_tag.region_id == merged.id

    command.downgrade(config, "a712e938c0d4")
    with Session(migration_engine) as session:
        assert session.scalar(select(Region).where(Region.code == "KR-29")).name == "광주광역시"
        assert session.scalar(select(Region).where(Region.code == "KR-46")).name == "전라남도"
        restored = {
            row.region_id
            for row in session.scalars(
                select(ArticleRegion).where(ArticleRegion.article_id == both_id)
            )
        }
        assert restored == {gwangju_id, old_jeonnam_id}
        restored_jeonnam = session.scalar(
            select(ArticleRegion).where(ArticleRegion.article_id == jeonnam_id)
        )
        assert restored_jeonnam.region_id == old_jeonnam_id

    migration_engine.dispose()
