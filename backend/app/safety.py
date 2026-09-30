from sqlalchemy import select

from app.config import settings
from app.models import Source
from app.services import can_collect


def check_startup(session):
    if settings.app_env != "production":
        return
    if settings.demo_mode:
        raise RuntimeError("Production requires DEMO_MODE=false")
    sources = session.scalars(select(Source).where(Source.enabled.is_(True)))
    if any(
        not can_collect(s, settings.app_usage_mode) or s.adapter_type == "demo" for s in sources
    ):
        raise RuntimeError("Production has an enabled source without permitted usage rights")
