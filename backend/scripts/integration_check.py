"""Run only against a disposable PostgreSQL database (see README).

Uses real HTTP RSS, PostgreSQL row locks, and FastAPI's actual DB-backed routes.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.collector import collect_source
from app.config import settings
from app.db import SessionLocal, utcnow
from app.main import app
from app.models import Article, CollectionRun, Source
from app.seed import seed


def main():
    database = settings.database_url.rsplit("/", 1)[-1]
    if database != "issuearea_test":
        raise RuntimeError("Integration check requires the isolated issuearea_test database")
    with SessionLocal() as session:
        # This dedicated test database is disposable; keep reruns independent of prior fixtures.
        session.execute(delete(CollectionRun))
        session.execute(delete(Article))
        session.execute(delete(Source))
        session.commit()
        seed(session)
        demo = session.scalar(select(Source).where(Source.adapter_type == "demo"))
        assert collect_source(session, demo).inserted_count == 19
        assert collect_source(session, demo).duplicate_count == 19

    class FeedHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.headers.get("If-None-Match") == '"integration-v1"':
                self.send_response(304)
                self.end_headers()
                return
            date = format_datetime(utcnow(), usegmt=True)
            body = f"""<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>
            <title>IssueArea integration feed</title><link>https://example.com</link>
            <description>Synthetic integration fixture</description>
            <item><guid>integration-1</guid><title>서울·경기 호우 대비 훈련</title>
            <link>https://example.com/integration/1</link><pubDate>{date}</pubDate></item>
            <item><guid>integration-2</guid><title>중구 교통 훈련</title>
            <link>https://example.com/integration/2</link></item></channel></rss>""".encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
            self.send_header("ETag", '"integration-v1"')
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), FeedHandler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with SessionLocal() as session:
            source = Source(
                name="통합 테스트용 가상 RSS",
                adapter_type="rss",
                enabled=True,
                rights_status="allowed",
                title_display_allowed=True,
                metadata_storage_allowed=True,
                commercial_use_allowed=True,
                feed_url=f"http://127.0.0.1:{server.server_port}/rss",
            )
            session.add(source)
            session.commit()
            assert collect_source(session, source).inserted_count == 2
            assert collect_source(session, source).status == "not_modified"
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            assert client.get("/api/v1/news?hours=24").json()["total"] == 21
            assert client.get("/api/v1/news?region=KR-11").json()["total"] == 3
            mapping = client.get("/api/v1/map/regions?q=호우").json()
            assert next(r["count"] for r in mapping["regions"] if r["code"] == "KR-11") == 2
            assert client.get("/api/v1/system/freshness").json()["status"] == "healthy"
        with SessionLocal() as owner:
            source = owner.scalar(
                select(Source).where(Source.adapter_type == "demo").with_for_update()
            )

            def contender():
                with SessionLocal() as other:
                    return other.scalar(
                        select(Source.id)
                        .where(Source.id == source.id)
                        .with_for_update(skip_locked=True)
                    )

            with ThreadPoolExecutor(max_workers=1) as executor:
                assert executor.submit(contender).result(timeout=5) is None
        print(
            json.dumps(
                {
                    "postgresql": "passed",
                    "rss_http_and_304": "passed",
                    "demo_dedup": "passed",
                    "api_filters": "passed",
                    "source_row_lock": "passed",
                }
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


if __name__ == "__main__":
    main()
