# 무료 뉴스 연결: NewsData.io

2026-09-30 공식 문서와 요금 안내를 비교했습니다. 현재 개인 개발용 IssueArea는 NewsData.io Free 플랜을 우선 사용합니다. 같은 날 사용자가 로컬에 설정한 키로 한국·한국어 요청이 HTTP 200에 성공했고, 10건 중 중복 1건을 제외한 9건을 저장했습니다. 이후 정치·경제·사건·국내 시사·기술 카테고리 필터를 추가했습니다. 초기 결과는 제목만으로 시·도를 특정할 수 없었습니다. 새 필터 적용 후 지역 커버리지는 다음 수집에서 확인해야 합니다.

로컬 출처 ID는 3이며 개인 개발 범위의 조건부 검토로 활성화했습니다. `.env`는 `APP_USAGE_MODE=noncommercial`, `DEMO_MODE=false`로 설정했습니다. 뉴스와이어는 계속 비활성 상태입니다. 인증정보는 저장소나 문서에 기록하지 않습니다.

| 서비스 | 무료 한도 | 주요 제약 / 판단 |
| --- | --- | --- |
| NewsData.io | 200크레딧/일, 최대 10건/크레딧 | 12시간 지연. 국가·언어 필터를 한국/한국어로 설정하여 우선 연결 |
| GNews | 100회/일, 최대 10건/회 | 12시간 지연, 개발·테스트 용도. 공식 API 지원 목록에 한국어·한국이 없어 제외 |
| TheNewsAPI | 100회/일, 최대 3건/회 | 한국어 지원, 실시간 데이터 안내. 요청당 기사 수가 적어 보조 후보 |
| NewsAPI.org | 100회/일 | 24시간 지연, 개발 환경에서만 이용 가능한 플랜이라 제외 |

공식 자료: [NewsData 무료 요금](https://newsdata.io/blog/pricing-plan-in-newsdata-io/), [크레딧 계산](https://newsdata.io/blog/newsdata-credit-consumption/), [API 규격](https://newsdata.io/openapi.json), [GNews 요금](https://gnews.io/pricing), [GNews 지원 목록](https://docs.gnews.io/endpoints/search-endpoint), [TheNewsAPI 요금](https://www.thenewsapi.com/pricing), [한국어 목록](https://www.thenewsapi.com/documentation), [NewsAPI.org 요금](https://newsapi.org/pricing).

## 준비할 것

1. [NewsData.io](https://newsdata.io/)에서 **Free 플랜** 계정을 만들고 이메일을 인증합니다. 유료 플랜을 선택할 필요가 없습니다.
2. 발급 키를 루트 `.env`의 `NEWSDATA_API_KEY=...`에 넣습니다. `.env`가 없으면 `.env.example`을 복사합니다. 비밀키는 채팅·Git·브라우저 변수에 올리지 않습니다.
3. 아래 명령으로 서버와 수집기를 갱신합니다.

```powershell
docker compose up -d --build api collector
docker compose exec api python -m app.source_registry list
```

출처가 없으면 한 번만 등록합니다. 출력 ID를 이후 명령에 사용합니다.

```powershell
docker compose exec api python -m app.source_registry add --name "NewsData.io 무료 한국 뉴스" --adapter newsdata --feed-url "https://newsdata.io/api/1/latest" --terms-url "https://newsdata.io/terms" --interval 10
```

기존 README의 source-review JSON 절차로 실제 이용조건을 기록하고 `review`와 `enable`을 실행합니다. 키만 추가해도 미검토 출처가 자동 활성화되지는 않습니다. 이번 사용 범위는 개인 개발 프로젝트입니다. [약관](https://newsdata.io/terms)은 원래 언론사 콘텐츠 권리를 별도로 유지하므로 API 무료 이용을 모든 뉴스의 자유로운 재배포 허락으로 해석하지 않습니다. 본문·이미지는 수집하거나 노출하지 않습니다.

## 무료 한도에 맞춘 동작

- `country=kr`, `language=ko`, 광역 지역 검색어(`qInTitle`), 정치·경제·사건·국내 시사·기술 5개 카테고리, `size=10`으로 한 번 조회합니다. NewsData는 현재 100자보다 긴 검색식을 거부하므로 시·도 단서만 요청하고, 제공자 필터 뒤에도 제목에서 실제 지역을 확인한 기사만 저장합니다. 지역 단서가 없는 예전 NewsData 기사는 목록과 지도에서 제외합니다. 서울 자치구와 주요 시·군 이름도 해당 광역 지역에 연결합니다. 지역·주제 분류, 검색과 지도 집계는 저장된 DB 메타데이터를 사용합니다.
- 기본 10분 간격은 정상 스케줄에서 하루 약 144요청입니다. 요청당 최대 10건이며 중복·결과 부족 때문에 실제 신규 기사 수는 이보다 적습니다. 전체 한국 뉴스나 모든 지역의 균등한 커버리지를 보장하지 않습니다. 지역명이 제목에 나타나지 않는 기사와 목록에 없는 소도시명은 제외되거나 미분류될 수 있습니다. 특정 시·군 RSS를 추가하면 커버리지를 보완할 수 있습니다.
- `nextPage`를 무시하고 추가 크레딧을 소모하지 않습니다. HTTP 자동 재시도도 없습니다. 계정별 출처는 한 개만 등록할 수 있습니다.
- 최근 24시간 수집 이력 180회에 이르면 다음 수집을 24시간 뒤로 미룹니다. 429 응답도 24시간 중단합니다. 다른 프로그램·대시보드에서 같은 키를 사용한 요청은 로컬 집계에 포함되지 않으므로 별도로 한도를 확인합니다. 수집 프로세스가 강제 종료되어 이력이 commit되지 않은 요청은 로컬 집계에서 빠질 수 있습니다.
- `X-ACCESS-KEY` 헤더를 사용해 키를 URL에 넣지 않습니다. 고정 HTTPS 주소, redirect 차단, timeout, 2MiB 응답 한도를 적용합니다.
- 원래 언론사명과 작성 시각을 저장합니다. 고정된 12시간 지연 배지는 표시하지 않으며 기사별 게시 시각을 제공합니다. 수집 성공 상태는 연결 상태이며 실시간 기사 제공을 의미하지 않습니다. 최근 6시간 필터는 무료 플랜에서 비어 있을 수 있으므로 24시간 범위를 권장합니다.
- 본문·사진·설명은 저장하지 않고 원문 페이지도 추가 요청하지 않습니다.

## RSS / 직접 크롤링

기존 RSS 어댑터는 별도 API 키 없이 사용할 수 있습니다. 이용조건이 허용하는 지역 언론 RSS를 등록하면 무료 API의 지역 커버리지를 보충할 수 있습니다. 공개된 RSS라는 사실만으로 저장·표시 권한까지 보장되지는 않습니다.

웹페이지 HTML 수집은 사이트별 selector와 페이지 구조, robots 정책, 이용조건, 호출 간격을 관리해야 합니다. 이를 피해서 접근하거나 차단을 우회하지 않습니다. 현재는 RSS와 무료 API를 우선 사용하며 범용 HTML 크롤러는 구현하지 않았습니다.
