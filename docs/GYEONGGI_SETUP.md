# 경기도뉴스포털 보도자료 연결

경기도뉴스포털의 공식 보도자료 RSS는 개별 기사마다 공공누리 이용조건을 표시합니다. IssueArea는 기사 원문 페이지의 공식 KOGL 링크와 **제1유형** 표기를 모두 확인한 항목만 제목·출처·원문 URL·게시 시각을 저장하고 표시합니다. 제2~4유형으로 바뀐 기사는 기존 저장본에서 삭제하고, 표시가 없거나 페이지를 확인할 수 없는 새 항목은 보류합니다. 본문·사진·첨부파일은 수집하지 않습니다.

2026-10-07 확인 결과 RSS는 HTTP 200, 최근 10개 항목을 반환했습니다. 최근 10개 원문 모두 `kogl.or.kr` 라이선스 링크와 “제1유형:출처표시”를 표시했습니다. 출처 이용정책은 [경기도 저작권 정책](https://www.gg.go.kr/contents/contents.do?ciIdx=1066&menuId=2772), 피드 목록은 [경기도뉴스포털 RSS 안내](https://gnews.gg.go.kr/rss/gnews_rss_main.do)에서 확인할 수 있습니다. 검토 기록은 [source-review-gyeonggi.json](source-review-gyeonggi.json)에 있습니다.

기존에 비활성 미검토 후보가 있으면 아래 `add` 명령이 비어 있는 후보만 전용 어댑터로 전환합니다. 이미 활성화되었거나 수집한 출처는 자동 변경하지 않습니다.

```powershell
docker compose exec api python -m app.source_registry add --name "경기도뉴스포털 보도자료" --adapter gyeonggi_press_release --feed-url "https://gnews.gg.go.kr/rss/gnewsRssBodo.do" --terms-url "https://www.gg.go.kr/contents/contents.do?ciIdx=1066&menuId=2772" --interval 60
docker compose cp docs/source-review-gyeonggi.json api:/tmp/source-review-gyeonggi.json
docker compose exec api python -m app.source_registry review <ID> --file /tmp/source-review-gyeonggi.json
docker compose exec api python -m app.source_registry enable <ID>
docker compose exec api python -m app.collector --once --source-id <ID>
docker compose exec api python -m app.source_registry list
```

수집기는 30분보다 짧은 간격을 허용하지 않으며, 원문 페이지 라이선스 확인을 최대 50건까지만 수행합니다. HTML 구조가 바뀌거나 라이선스 링크를 읽을 수 없으면 신규 기사는 수집하지 않습니다.
