<div align="center">

<img src="docs/assets/issuearea-hero.svg" alt="IssueArea — 지역의 이슈를 한눈에 보는 뉴스 탐색 지도" width="100%">

<h1>IssueArea</h1>

**지역에서 발견하는 뉴스**

전국의 최신 이슈를 지역 지도와 함께 탐색하고, 관심 지역의 맥락을 원문 기사로 이어주는 뉴스 플랫폼입니다.

[빠른 시작](#-빠른-시작) · [주요 기능](#-주요-기능) · [기술 구성](#-기술-구성) · [로드맵](docs/ROADMAP.md)

</div>

<p align="center">
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js-웹-111827?style=flat-square&logo=nextdotjs&logoColor=white">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-프론트엔드-3178C6?style=flat-square&logo=typescript&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-API-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-저장소-4169E1?style=flat-square&logo=postgresql&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-로컬_실행-2496ED?style=flat-square&logo=docker&logoColor=white">
  <img alt="Playwright" src="https://img.shields.io/badge/Playwright-E2E-2EAD33?style=flat-square&logo=playwright&logoColor=white">
</p>

## ✨ 주요 기능

<p align="center">
  <img src="docs/assets/issuearea-flow.svg" alt="출처 수집, 지역과 주제 분류, 지도와 뉴스 목록 탐색, 원문 확인으로 이어지는 IssueArea 흐름" width="100%">
</p>

| 🗺️ 지역 뉴스 탐색 | 🧭 주제와 검색 | 📰 원문으로 연결 |
| --- | --- | --- |
| Leaflet 지도에서 지역별 기사 수를 보고 가까운 지역 클러스터를 확대합니다. | 제목 검색, 기간, 주제, 지역을 조합해 관심 이슈를 찾습니다. | 제목을 누르면 출처의 원문으로 이동하며 보도자료는 별도 구분합니다. |

- **전국 16개 지역** — 지역별 관련 뉴스 집계와 다중 지역 분류를 지원합니다.
- **RSS 및 무료 뉴스 API 준비** — 출처 권리 검토와 수집 제한을 적용하고, 뉴스 본문이나 이미지는 저장하지 않습니다.
- **재현 가능한 개발 환경** — Docker Compose로 웹, API, 수집기, PostgreSQL을 실행합니다.
- **브라우저 흐름 검증** — Playwright로 검색·필터, 지도 확대, 오류 재시도 흐름을 확인합니다.

> 현재는 개발용 Demo와 출처 연결 준비 단계입니다. 상용 뉴스 수집이나 운영 배포가 완료된 서비스는 아닙니다. 구현 및 제한 사항은 [로드맵](docs/ROADMAP.md)을 참고하세요.

## 🧱 기술 구성

`Next.js` · `React` · `TypeScript` · `Leaflet` · `FastAPI` · `SQLAlchemy` · `PostgreSQL` · `Alembic` · `Docker Compose` · `Playwright`

## 🗂️ 프로젝트 구조

```text
web/                    Next.js · React · TypeScript · Tailwind · Leaflet
backend/app/            FastAPI · SQLAlchemy · 분류기 · 수집기 · 출처 등록 CLI
backend/alembic/         실제 DB migration
backend/tests/           분류·중복·수집·API 테스트
docs/SOURCE_POLICY.md    출처 권리 검토 정책
docs/ROADMAP.md          다음 구현 단계
docker-compose.yml      PostgreSQL / API / Collector / Web
```

API와 Collector는 같은 모델을 공유하는 별도 프로세스입니다. 기사 본문이나 이미지는 저장하지 않습니다. 시각은 DB에서 UTC로 관리하고 화면에는 Asia/Seoul로 표시합니다.

## 🚀 빠른 시작

### Docker 실행

필요 프로그램: Docker Desktop(Linux containers), Docker Compose v2. 먼저 Docker Desktop을 실행합니다.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

- 화면: http://localhost:3000
- API 문서: http://localhost:8000/docs
- DB 상태: http://localhost:8000/health

API 시작 시 `alembic upgrade head`와 idempotent seed가 실행되고, Collector가 준비된 API/DB 뒤에 시작합니다. 첫 수집 전에는 빈 목록이 표시될 수 있으며 화면은 60초마다 다시 조회합니다. PostgreSQL은 영속 볼륨을 사용합니다. 기본 DB 계정은 로컬 개발용입니다.

## Demo Mode

기본 `DEMO_MODE=true`입니다. 뉴스 API 키가 필요 없습니다. 가상 제목 19건을 매시간 새 edition으로 생성하고, 같은 edition의 반복 수집은 중복을 제거합니다. 16개 지역, 다중 지역, 전국, 미분류 예시가 실제 수집 파이프라인을 통과합니다. 링크는 `example.com` 예시 주소이며 실제 기사로 연결되지 않습니다. 웹 패키지·컨테이너 이미지 다운로드와 OSM 배경 타일에는 인터넷이 필요합니다.

## 환경변수

| 변수 | 용도 |
| --- | --- |
| APP_ENV | development / test / production |
| APP_USAGE_MODE | development / noncommercial / commercial |
| DEMO_MODE | 개발용 출처 활성화 |
| DATABASE_URL | SQLAlchemy DB 연결 주소 |
| CORS_ORIGINS | 허용 웹 origin, 쉼표 구분 |
| COLLECTOR_POLL_SECONDS | due source 확인 주기, 기본 60초 |
| ARTICLE_RETENTION_DAYS | 기사 보관 기간, 기본 30일 |
| NEWSWIRE_PARTNER_ID | 제휴 승인 후 발급받는 서버용 숫자 ID |
| NEWSWIRE_API_KEY | 서버 전용 비밀키, Git·브라우저에 노출 금지 |
| NEWSDATA_API_KEY | 무료 한국 뉴스 수집용 서버 전용 비밀키 |
| NEXT_PUBLIC_API_BASE_URL | 브라우저가 접근하는 API 주소 |
| NEXT_PUBLIC_MAP_PROVIDER | 현재 지원: leaflet_osm |
| NEXT_PUBLIC_APP_NAME | 표시 서비스명 |

`NEXT_PUBLIC_*`와 지도 안전 설정은 빌드 시 반영되므로 변경 후 `docker compose up --build`로 재빌드합니다. 다른 기기에서 접속할 때는 API 주소와 CORS를 해당 호스트 주소로 바꿉니다.

## Migration / Seed / 수집기

```powershell
docker compose exec api alembic upgrade head
docker compose exec api alembic check
docker compose exec api python -m app.seed
docker compose exec api python -m app.collector --once
```

수동 수집도 `next_fetch_at`를 지킵니다. 수집 직후 실행하면 해당 출처는 다음 예정 시각까지 건너뜁니다. 출처별 PostgreSQL 행 잠금으로 중복 실행을 방지합니다. 실패는 출처 단위로 격리되고 최대 6시간의 지수 backoff를 적용합니다. RSS는 15초 timeout, 3회 redirect, 2 MiB 응답 한도, 500개 entry 한도와 ETag/Last-Modified를 지원합니다.

## 실제 RSS 연결

먼저 [출처 정책](docs/SOURCE_POLICY.md)과 [실제 출처 조사](docs/NEWS_SOURCES.md)를 확인합니다. 기본 언론사 RSS는 등록하지 않습니다.

```powershell
docker compose exec api python -m app.source_registry add --name "검토할 출처" --feed-url "https://publisher.example/feed" --terms-url "https://publisher.example/terms" --interval 5
docker compose exec api python -m app.source_registry list
```

출처는 항상 **비활성 / 미검토** 상태로 등록됩니다. `docs/source-review.example.json`을 복사하고 실제 검토 결과로 수정합니다. 아래 ID는 `add` 출력 ID로 교체합니다.

```powershell
Copy-Item docs/source-review.example.json source-review.json
# source-review.json을 실제 권리 검토 내용으로 편집한 뒤:
docker compose cp source-review.json api:/tmp/source-review.json
docker compose exec api python -m app.source_registry review 2 --file /tmp/source-review.json
docker compose exec api python -m app.source_registry enable 2
docker compose exec api python -m app.collector --once --source-id 2
docker compose exec api python -m app.source_registry list
# 수집 중단 및 해당 출처 기사 조회 제외:
docker compose exec api python -m app.source_registry disable 2
```

예시 JSON은 미검토 상태이므로 그대로 사용하면 활성화가 거부됩니다. `commercial_use_allowed`와 기타 권한은 실제 검토 결과로 설정합니다. 확인 시각은 시간대를 포함하고 미래가 아니어야 합니다. 상업 운영은 `APP_USAGE_MODE=commercial`이 필수입니다. 검토되지 않았거나 금지된 출처는 어떤 모드에서도 수집하지 않습니다. 조건부 허용은 운영자가 모든 조건을 충족한 뒤 활성화합니다. 권리 검토를 수정하면 다시 비활성화되므로 `enable`을 별도로 실행합니다. 출처 등록과 변경에 공개 API나 웹 관리자 화면은 사용하지 않습니다. 실제 출처 연결 전까지 Demo만 활성화됩니다.

뉴스와이어 보도자료 API 어댑터와 카드 구분 표시를 추가했습니다. 신청·비용 확인·환경변수·출처 활성화 절차는 [연결 안내](docs/NEWSWIRE_SETUP.md)를 참고합니다. 실제 인증은 승인 및 키 발급 후 검증해야 합니다.

국가데이터처 보도자료는 게시물마다 이용조건이 달라 전용 어댑터가 원문 페이지의 KOGL 유형을 확인합니다. 제1유형만 수집하고, 그 외 유형과 라이선스 확인 실패 항목은 제외합니다. 등록·심사·활성화 명령은 [국가데이터처 연결 안내](docs/MODS_SETUP.md)를 참고합니다.

경기도·대구광역시·전남광주통합특별시 피드도 원문별 KOGL 1유형을 확인하는 전용 필터를 사용합니다. 대구는 활성화했고, 전남광주 피드는 현재 RSS에 2026년 6~7월 기사만 있어 비활성화했습니다. 세부 내용은 [지역 보도자료 연결 안내](docs/REGIONAL_SOURCES_SETUP.md)를 참고하세요.

현재 개인 프로젝트의 우선 연결 경로는 **NewsData.io Free 플랜**입니다. 기본 10분 간격·한 번에 10건·추가 페이지 없음으로 크레딧을 절약합니다. 고정된 무료 플랜 지연 배지는 표시하지 않고 기사 게시 시각을 제공합니다. [무료 API 비교와 키 설정](docs/FREE_NEWS_SETUP.md)을 확인합니다.

## 지도

현재 개발·테스트·Demo에 Leaflet/OSM 공용 타일을 사용합니다. 마우스 휠로 확대·축소할 수 있고 가까운 지역은 묶음 숫자로 표시해 지도를 확대하면 개별 지역으로 펼쳐집니다. attribution을 표시하며 타일 사전 수집은 하지 않습니다. 운영 모드에서 OSM 공용 타일을 자동 사용하지 않으며 지도 설정 안내와 뉴스 목록을 표시합니다.

## Docker 없이 개발

필요 프로그램: Python 3.12+, uv, Node.js 22.18+, pnpm 11.19.0. 기본 운영 DB는 PostgreSQL입니다. SQLite는 로컬 구조 검증용으로만 지원하며 PostgreSQL 잠금 동작을 대체하지 않습니다.

백엔드(아래는 PowerShell):

```powershell
cd backend
uv sync --locked
$env:DATABASE_URL='sqlite:///local.db'
uv run alembic upgrade head
uv run python -m app.seed
uv run python -m app.collector --once
uv run uvicorn app.main:app --reload --port 8000
```

별도 터미널에서 수집기를 계속 실행하려면 같은 DB 환경변수를 설정한 뒤 `uv run python -m app.collector`를 실행합니다.

프런트엔드(별도 터미널):

```powershell
cd web
pnpm install --frozen-lockfile
pnpm dev
```

Docker에서는 standalone 서버를 사용합니다. 로컬 프로덕션 미리보기는 `pnpm build` 후 `pnpm start`를 실행합니다.

## 테스트

```powershell
cd backend
uv run ruff check .
uv run pytest -q
uv run alembic check
```

`alembic check`는 migration이 반영된 DB 환경변수를 먼저 설정합니다. 테스트 fixture는 격리된 메모리 SQLite를 사용하며 런타임 DB 생성은 Alembic만 사용합니다.

```powershell
cd web
pnpm lint
pnpm typecheck
pnpm test
pnpm run e2e:install  # 최초 1회
pnpm run e2e
```

브라우저 E2E는 테스트용 프로덕션 빌드를 만든 뒤 포트 3100에서 실행합니다. 뉴스/API 응답을 테스트 fixture로 가로채므로 Docker·API 키·외부 뉴스 연결이 필요 없습니다. Leaflet 지도 조작은 확인하되 OSM 타일 서버 연결은 테스트에서 차단합니다. Chromium 설치 경로를 프로젝트 폴더로 지정하려면 PowerShell에서 `$env:PLAYWRIGHT_BROWSERS_PATH='..\.playwright-browsers'`를 설정한 뒤, 같은 터미널에서 설치와 테스트를 실행하세요.

루트에서 `docker compose config --quiet`로 Compose를 검증합니다.

PostgreSQL 통합 테스트는 **테스트 전용 DB `issuearea_test`**에서 실행합니다. DB 생성은 처음 한 번만 실행합니다. 이 검증 스크립트는 해당 테스트 DB의 기사·출처·수집 이력을 초기화하고 매번 가상 데이터를 생성합니다. 일반 개발 DB `newsmap`에서는 실행을 거부합니다.

```powershell
docker compose exec postgres createdb -U newsmap issuearea_test
docker compose exec -e DATABASE_URL=postgresql+psycopg://newsmap:newsmap@postgres:5432/issuearea_test api alembic upgrade head
docker compose exec -e DATABASE_URL=postgresql+psycopg://newsmap:newsmap@postgres:5432/issuearea_test api python -m scripts.integration_check
```

실제 HTTP 테스트 RSS → PostgreSQL 저장 → API 필터·집계, ETag 304, Demo 중복 제거, 두 DB 연결 사이의 출처 잠금을 검증합니다. 테스트 RSS 서버는 컨테이너 loopback에서 잠시 실행되며 외부 언론사 콘텐츠를 사용하지 않습니다.

## 현재 검증과 제한

- 백엔드 73개 테스트: 수집·API, 보도자료, 무료 뉴스 요청 제한·429 중단, RSS 경계, 안전한 수집 실패 로그, 출처 권리와 지역 migration을 검증합니다.
- 프런트엔드 단위 테스트 9개: 필터 URL 상태 4개와 뉴스 카드·로딩·오류·빈 결과 컴포넌트 5개.
- 타입 검사·린트·Next.js 빌드, 로컬 SQLite migration·schema check·seed·Collector와 Compose 설정 검사 수행.
- Docker에서 PostgreSQL·API·수집기·웹 기동, migration schema check, 실제 HTTP RSS와 행 잠금 통합 테스트가 통과했습니다. 테스트용 기사는 별도 DB에만 저장됩니다.
- 브라우저 E2E 7개: 뉴스 필터·원문 링크 보안, 지도 클러스터 확대, 시군구 선택·중심 이동·포커스 테두리, API 재시도, 빈 결과·필터 초기화, 로딩 상태, 보도자료 카드 표시를 fixture 기반으로 검증합니다. 백엔드 RSS는 3회 리다이렉트, 2 MiB 경계, 500개 entry 제한과 조건부 요청 헤더를 테스트합니다. 국가데이터처·경기도·대구·전남광주 어댑터는 공식 KOGL 링크와 유형 필터, URL 제한을 테스트합니다. 수집 실패는 URL·예외 문구를 노출하지 않고 경고 수준 JSON 로그로 기록하며 오류 유형·HTTP 상태·연속 실패 횟수·재시도 시각을 포함합니다.
- 로컬 브라우저에서 Demo 기사·지역 집계, 서울 선택과 주제 필터를 확인했습니다. 마지막 확인 시 브라우저 error/warn 로그는 없었습니다.
- 제목 alias로만 지역을 분류합니다. `중구`와 단독 `광주` 등 모호한 표현을 임의 지역에 배치하지 않습니다. `서울대`, `경기침체`와 같은 부분 문자열 오분류를 피하기 위해 단어 경계를 사용하며 이에 따라 일부 지역 조사형 표현은 미분류될 수 있습니다.
- freshness는 출처별 `max(15분, 수집 간격 × 3)`을 기준으로 계산합니다. 일부만 정상인 경우 degraded, 정상 출처가 없으면 stale입니다.

## 문제 해결

- Docker 연결 오류: Docker Desktop과 Linux 엔진을 시작합니다.
- 빈 뉴스: `docker compose logs collector`에서 첫 수집 여부와 출처 권리를 확인합니다.
- API 오류: `docker compose logs api`, `/health`, 브라우저가 접근 가능한 API URL과 CORS를 확인합니다.
- 지도 배경 실패: 네트워크를 확인합니다. 지역 버튼과 뉴스 목록은 계속 사용할 수 있습니다.
- 포트 충돌: 3000/8000 사용 프로세스를 확인하거나 Compose 포트를 변경하고 API/CORS도 함께 수정합니다.
- 운영 시작 오류: Demo가 꺼져 있고 활성 출처의 권리가 검토되어 있는지 확인합니다.

## 운영 전 확인

Docker/PostgreSQL 통합 검증, 실제 출처 권리 검토, Demo 비활성, usage mode 설정, 운영 지도 공급자 구현, DB 계정 교체, HTTPS/CORS·외부 요청 네트워크 제한, 백업 및 로그 정책, 브라우저 E2E를 완료해야 합니다. 현재 단계는 운영 배포 완료본이 아닙니다.

기술 구성 참고: [Next.js 설치 문서](https://nextjs.org/docs/app/getting-started/installation), [FastAPI Docker 문서](https://fastapi.tiangolo.com/deployment/docker/).
