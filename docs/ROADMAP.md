# 단계별 구현 범위

## 현재: 실행 가능한 기초 구조

Next.js/React/TypeScript/Tailwind, FastAPI/SQLAlchemy, PostgreSQL Compose, Alembic migrations, 16개 광역 지역·12개 주제, Demo/RSS 어댑터, 분류와 중복 방지, 수집 이력, 조회·집계 API, 개발용 Leaflet 지도와 필터 UI를 연결합니다. 지도는 휠 확대·축소와 근접 지역 클러스터를 지원합니다. 2026년 행정 통합에 맞춰 광주·전남 기사 지역 태그를 전남광주통합특별시로 합칩니다.

## 2단계: 출처 연결 준비와 PostgreSQL 검증

출처 등록·엄격한 JSON 권리 검토·활성화·비활성화·수집 상태 조회 CLI, 직접 수집 경로의 권리 guard, 비활성 출처 조회 제외, 출처별 freshness 기준을 추가했습니다. 실제 HTTP RSS와 PostgreSQL 기반 통합 검증은 `backend/scripts/integration_check.py`로 실행합니다. 공식 출처 조사 결과는 `docs/NEWS_SOURCES.md`에 기록합니다.

## 다음 단계

3단계로 뉴스와이어 제휴 API 어댑터, 보도자료 구분, 수정·삭제·발표시각 처리와 수집 이력 migration을 추가했습니다. 비용과 제휴 승인·키 발급을 확인한 뒤 실제 인증을 검증합니다. 상세 절차와 미구현 복구 범위는 `docs/NEWSWIRE_SETUP.md`에 있습니다.

개인 개발 프로젝트는 NewsData.io 무료 플랜을 우선 연결합니다. 어댑터·요청 제한·원래 언론사명 저장을 구현했습니다. 무료 키 발급 후 실제 한국어 결과를 검증하는 절차는 `docs/FREE_NEWS_SETUP.md`를 참고합니다. 지도는 마우스 휠 확대·축소를 지원합니다.

- Playwright 브라우저 E2E 6개: 뉴스 필터·원문 링크 보안, 지도 클러스터 확대, API 재시도, 빈 결과·필터 초기화, 로딩 상태, 보도자료 카드 표시. 실행법은 README 테스트 항목 참조.
- 뉴스 카드·에러·로딩 상태의 컴포넌트 단위 테스트 분리
- RSS 경계 테스트 완료: 3회 redirect 허용 및 4회 redirect 거부, 2 MiB 정확한 크기 허용 및 초과 거부, 500개 entry 상한, 조건부 요청 헤더, 304·500·malformed·timeout.
- 수집 실패 상세 관측과 운영 로그 정비
- 라이브 뉴스 출처 이용조건 검토 후 등록

첫 단계의 완료를 전체 명세의 7-PASS 인증으로 표현하지 않습니다. README의 검증 결과와 알려진 제한을 확인하세요.
