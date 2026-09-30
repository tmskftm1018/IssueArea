"""Merge Gwangju and Jeollanam-do into Jeonnam-Gwangju Special City."""

import sqlalchemy as sa

from alembic import op

revision = "b3d0f190d2a1"
down_revision = "a712e938c0d4"
branch_labels = None
depends_on = None

REGION_BACKUP = "ia_region_merge_region_backup"
ARTICLE_BACKUP = "ia_region_merge_article_backup"

regions = sa.table(
    "regions",
    sa.column("id", sa.Integer()),
    sa.column("code", sa.String()),
    sa.column("name", sa.String()),
    sa.column("short_name", sa.String()),
    sa.column("level", sa.Integer()),
    sa.column("parent_id", sa.Integer()),
    sa.column("latitude", sa.Float()),
    sa.column("longitude", sa.Float()),
    sa.column("aliases", sa.JSON()),
)
article_regions = sa.table(
    "article_regions",
    sa.column("article_id", sa.Integer()),
    sa.column("region_id", sa.Integer()),
    sa.column("confidence", sa.Float()),
    sa.column("method", sa.String()),
    sa.column("classifier_version", sa.String()),
    sa.column("is_primary", sa.Boolean()),
)
region_backup = sa.table(
    REGION_BACKUP,
    sa.column("id", sa.Integer()),
    sa.column("code", sa.String()),
    sa.column("name", sa.String()),
    sa.column("short_name", sa.String()),
    sa.column("level", sa.Integer()),
    sa.column("parent_id", sa.Integer()),
    sa.column("latitude", sa.Float()),
    sa.column("longitude", sa.Float()),
    sa.column("aliases", sa.JSON()),
)
article_backup = sa.table(
    ARTICLE_BACKUP,
    sa.column("article_id", sa.Integer()),
    sa.column("region_id", sa.Integer()),
    sa.column("confidence", sa.Float()),
    sa.column("method", sa.String()),
    sa.column("classifier_version", sa.String()),
    sa.column("is_primary", sa.Boolean()),
)

SPECIAL_CITY = {
    "code": "KR-29",
    "name": "전남광주통합특별시",
    "short_name": "전남광주",
    "level": 1,
    "parent_id": None,
    "latitude": 35.0760,
    "longitude": 126.6400,
    "aliases": [
        "전남광주통합특별시",
        "전남광주",
        "광주전남",
        "광주광역시",
        "광산구",
        "전남",
        "전라남도",
        "목포",
        "여수",
        "순천",
        "광양",
        "나주",
        "담양",
        "곡성",
        "구례",
        "고흥",
        "보성",
        "화순",
        "장흥",
        "강진",
        "해남",
        "영암",
        "무안",
        "함평",
        "영광",
        "장성",
        "완도",
        "진도",
        "신안",
    ],
}
OLD_GWANGJU = {
    "id": None,
    "code": "KR-29",
    "name": "광주광역시",
    "short_name": "광주",
    "level": 1,
    "parent_id": None,
    "latitude": 35.1595,
    "longitude": 126.8526,
    "aliases": ["광주광역시"],
}
OLD_JEOLLANAM = {
    "id": None,
    "code": "KR-46",
    "name": "전라남도",
    "short_name": "전남",
    "level": 1,
    "parent_id": None,
    "latitude": 34.8161,
    "longitude": 126.4629,
    "aliases": ["전남", "전라남도", "목포", "여수", "순천", "광양", "나주"],
}


def upgrade():
    op.create_table(
        REGION_BACKUP,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("short_name", sa.String(20), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
    )
    op.create_table(
        ARTICLE_BACKUP,
        sa.Column("article_id", sa.Integer(), primary_key=True),
        sa.Column("region_id", sa.Integer(), primary_key=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("method", sa.String(50), nullable=False),
        sa.Column("classifier_version", sa.String(30), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
    )

    connection = op.get_bind()
    old_regions = connection.execute(
        sa.select(regions).where(regions.c.code.in_(["KR-29", "KR-46"]))
    ).mappings().all()
    if old_regions:
        connection.execute(sa.insert(region_backup), [dict(row) for row in old_regions])

    old_region_ids = {row["id"] for row in old_regions}
    old_article_links = []
    if old_region_ids:
        old_article_links = connection.execute(
            sa.select(article_regions).where(article_regions.c.region_id.in_(old_region_ids))
        ).mappings().all()
        if old_article_links:
            connection.execute(sa.insert(article_backup), [dict(row) for row in old_article_links])

    city = next((row for row in old_regions if row["code"] == "KR-29"), None)
    province = next((row for row in old_regions if row["code"] == "KR-46"), None)
    target_id = city["id"] if city else (province["id"] if province else None)

    if target_id is not None:
        merged_by_article = {}
        for row in old_article_links:
            current = merged_by_article.get(row["article_id"])
            primary = bool(row["is_primary"]) or bool(
                current and current["is_primary"]
            )
            if current is None or row["confidence"] > current["confidence"]:
                current = {
                    "article_id": row["article_id"],
                    "region_id": target_id,
                    "confidence": row["confidence"],
                    "method": row["method"],
                    "classifier_version": row["classifier_version"],
                    "is_primary": primary,
                }
                merged_by_article[row["article_id"]] = current
            else:
                current["is_primary"] = primary

        if old_region_ids:
            connection.execute(
                sa.delete(article_regions).where(
                    article_regions.c.region_id.in_(old_region_ids)
                )
            )
        if merged_by_article:
            connection.execute(sa.insert(article_regions), list(merged_by_article.values()))
        if city and province:
            connection.execute(sa.delete(regions).where(regions.c.id == province["id"]))
        connection.execute(
            sa.update(regions)
            .where(regions.c.id == target_id)
            .values(**SPECIAL_CITY)
        )


def downgrade():
    connection = op.get_bind()
    saved_regions = connection.execute(sa.select(region_backup)).mappings().all()
    saved_links = connection.execute(sa.select(article_backup)).mappings().all()
    merged = connection.execute(
        sa.select(regions.c.id).where(regions.c.code == "KR-29")
    ).scalar_one_or_none()

    for saved in saved_regions:
        existing = connection.execute(
            sa.select(regions.c.id).where(regions.c.id == saved["id"])
        ).scalar_one_or_none()
        if existing:
            connection.execute(
                sa.update(regions).where(regions.c.id == saved["id"]).values(**dict(saved))
            )
        else:
            connection.execute(sa.insert(regions).values(**dict(saved)))

    saved_codes = {row["code"] for row in saved_regions}
    if "KR-29" not in saved_codes:
        current_city = connection.execute(
            sa.select(regions.c.id).where(regions.c.code == "KR-29")
        ).scalar_one_or_none()
        old_city_values = {key: value for key, value in OLD_GWANGJU.items() if key != "id"}
        if current_city:
            connection.execute(
                sa.update(regions)
                .where(regions.c.id == current_city)
                .values(**old_city_values)
            )
        else:
            connection.execute(sa.insert(regions).values(**old_city_values))
    if "KR-46" not in saved_codes:
        current_province = connection.execute(
            sa.select(regions.c.id).where(regions.c.code == "KR-46")
        ).scalar_one_or_none()
        if current_province is None:
            old_province_values = {
                key: value for key, value in OLD_JEOLLANAM.items() if key != "id"
            }
            connection.execute(sa.insert(regions).values(**old_province_values))

    if saved_links:
        article_ids = {row["article_id"] for row in saved_links}
        if merged is not None:
            connection.execute(
                sa.delete(article_regions).where(
                    article_regions.c.article_id.in_(article_ids),
                    article_regions.c.region_id == merged,
                )
            )
        connection.execute(sa.insert(article_regions), [dict(row) for row in saved_links])

    op.drop_table(ARTICLE_BACKUP)
    op.drop_table(REGION_BACKUP)
