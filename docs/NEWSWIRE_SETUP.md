# 뉴스와이어 보도자료 API 연결 준비

IssueArea는 일반 뉴스와 별도로 보도자료를 포함하며 카드에 `보도자료`를 표시합니다. 뉴스와이어는 보도자료 공급 경로이므로 일반 언론사 뉴스 전체를 대체하지 않습니다.

## 신청과 비용 확인

2026-09-30 확인한 [공식 안내](https://www.newswire.co.kr/coalition)와 [API 이용약관](https://www.newswire.co.kr/coalition/policyterms)에는 무료 여부와 공개 요금표가 명시되어 있지 않습니다. 무료라고 가정하지 않습니다. 이용 신청을 심사한 뒤 승인되면 API 키가 발급됩니다.

신청 시 IssueArea의 운영 주체와 사이트 주소, 제목·발표시각·원문 링크 저장 및 지역·주제 분류, 보도자료 구분 표시, 예상 호출 간격 5분을 설명합니다. 키 발급비·월 이용료·호출 제한·상업 서비스 허용 범위도 확인합니다. 본문·사진은 저장하거나 표시하지 않습니다.

## 로컬 설정

승인받은 값은 저장소 루트 `.env`에 입력합니다. 채팅이나 Git에 키를 올리지 않습니다. `.env`는 Git ignore 대상입니다. 브라우저용 `NEXT_PUBLIC_*` 변수에는 키를 넣지 않습니다.

```dotenv
NEWSWIRE_PARTNER_ID=발급받은_숫자_ID
NEWSWIRE_API_KEY=발급받은_비밀키
```

API와 수집기에 반영합니다.

```powershell
docker compose up -d --build api collector
docker compose exec api python -m app.source_registry add --name "뉴스와이어 (보도자료)" --adapter newswire --feed-url "https://www.newswire.co.kr/api/v1/request" --terms-url "https://www.newswire.co.kr/coalition/policyterms" --interval 5
docker compose exec api python -m app.source_registry list
```

출처는 비활성·미검토 상태로 등록됩니다. 이미 등록한 경우 `add`는 생략합니다. 실제 승인 내용으로 `docs/source-review.example.json`을 복사·편집하고 README의 review / enable 절차를 진행합니다. 활성화는 권리 검토와 서버 인증값이 모두 있어야 가능합니다. 승인과 비용 확인 전에는 활성화하지 않습니다.

## 구현과 검증 범위

- 공식 request → send 흐름, HMAC 인증, 고정 HTTPS 주소, redirect 차단, timeout 및 응답 크기 제한을 구현했습니다.
- 이벤트 순서를 유지하여 신규·수정·삭제를 처리합니다. 수정 대상이 없으면 삽입하고, 삭제 대상이 없으면 건너뜁니다. 수정 시 지역·주제를 다시 분류하며 한 배치의 DB 변경은 실패 시 되돌립니다.
- 발표 예정 시각은 저장하되 해당 시각 전에는 목록과 지도 집계에서 제외합니다.
- 본문·사진·연락처는 어댑터에서 버립니다. 원문 링크와 제목 등 필요한 메타데이터만 저장하며 인증정보와 응답 본문을 로그로 남기지 않습니다.
- 공식 문서 헤더는 Timestamp를 밀리초로 안내하지만 PHP 예시는 초 단위여서 서로 다릅니다. 현재는 헤더 명세의 밀리초를 적용했습니다. 실제 발급 키로 인증 규격을 확인해야 합니다.
- Mock HTTP와 격리 DB 테스트가 통과했습니다. 실제 인증·공급 데이터는 아직 검증하지 않았습니다. request/send 도중 프로세스가 종료되는 경우의 공급자 재전송·이력 복구와 영속 체크포인트는 아직 구현하지 않았으며 누락 없는 전달을 보장하지 않습니다.
- 선택적인 URL 사용 통지 callback은 구현하지 않았습니다.

기술 규격: [뉴스와이어 공식 API 문서](https://www.newswire.co.kr/coalition/document).
