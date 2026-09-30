from sqlalchemy import select

from app.collector import collect_source
from app.models import Source


def populate(session):
    collect_source(session, session.scalar(select(Source).where(Source.adapter_type == "demo")))


def test_api_flow(session, client):
    populate(session)
    all_news = client.get("/api/v1/news").json()
    assert client.get("/api/v1/news?hours=24").status_code == 200
    assert client.get("/api/v1/map/regions?hours=24").status_code == 200
    assert all_news["total"] == 19
    assert len(client.get("/api/v1/regions").json()) == 16
    assert len(client.get("/api/v1/topics").json()) == 12
    regional = client.get("/api/v1/news?region=KR-11").json()
    assert regional["total"] == 2
    assert all("KR-11" in {r["code"] for r in a["regions"]} for a in regional["items"])
    assert client.get("/api/v1/news?region=KR-46").json()["total"] == client.get(
        "/api/v1/news?region=KR-29"
    ).json()["total"]
    mapping = client.get("/api/v1/map/regions").json()
    assert mapping["unmapped_count"] == 2
    assert next(r for r in mapping["regions"] if r["code"] == "KR-11")["count"] == 2
    assert sum(r["count"] for r in mapping["regions"]) == 18
    assert client.get("/api/v1/news?q=호우&topics=weather,society").json()["total"] == 1
    assert client.get("/api/v1/news?page=2&page_size=3").json()["page"] == 2
    assert len(client.get("/api/v1/news?page=2&page_size=3").json()["items"]) == 3
    assert client.get("/api/v1/system/freshness").json()["status"] == "healthy"


def test_invalid_filters(client):
    for params in ["hours=2", "page=0", "page_size=101", "region=bad", "topics=bad"]:
        assert client.get(f"/api/v1/news?{params}").status_code == 422


def test_empty(client):
    assert client.get("/api/v1/news").json()["items"] == []
    assert client.get("/api/v1/system/freshness").json()["status"] == "stale"
