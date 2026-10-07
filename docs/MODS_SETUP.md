# 국가데이터처 보도자료 연결

국가데이터처는 보도자료 RSS를 제공하지만 게시물별 공공누리 유형이 다릅니다. IssueArea의 `mods_press_release` 어댑터는 보도자료 원문 페이지의 KOGL 링크를 확인해 **제1유형만** 수집합니다. 제2~4유형은 수집하지 않고, 유형 표기가 없거나 원문 페이지를 확인하지 못한 새 항목도 보류합니다. 제2~4유형으로 바뀐 항목은 기존 저장본에서 삭제합니다. 제목·출처·원문 링크·게시 시각만 저장하고 본문·이미지·첨부파일은 가져오지 않습니다.

현재 확인한 공식 안내와 표본:

- [국가데이터처 저작권 정책](https://mods.go.kr/menu.es?mid=a10706000000)은 제1유형의 상업 이용을 허용하고 출처 표시를 요구합니다. 제2유형은 상업 이용 금지, 제3유형은 변경 금지, 제4유형은 둘 다 금지한다고 설명합니다.
- [2026년 9월 소비자물가동향](https://mods.go.kr/board.es?act=view&bid=213&list_no=447322&mid=a10301010000)은 제1유형입니다.
- [2026년 8월 온라인쇼핑동향](https://mods.go.kr/board.es?act=view&bid=241&list_no=447300&mid=a10301010000)은 제4유형입니다.
- 확인일: 2026-10-07. 목록의 자세한 출처 조사 결과는 [NEWS_SOURCES.md](NEWS_SOURCES.md)에 있습니다.

처음 한 번 공식 피드를 등록합니다. 간격은 30분보다 짧을 수 없습니다.

```powershell
docker compose exec api python -m app.source_registry add --name "국가데이터처 보도자료" --adapter mods_press_release --feed-url "https://mods.go.kr/board.es?mid=a10301010000&bid=a103010100&act=rss" --terms-url "https://mods.go.kr/menu.es?mid=a10706000000" --interval 60
```

등록 명령이 출력한 ID를 사용합니다. 현재 로컬 DB의 기존 후보 ID 7은 이 명령으로 전용 어댑터로 전환됩니다. 검토 파일의 확인 시각은 2026-10-07이고, 실제 사용 범위는 제1유형 항목만 표시한다는 조건입니다.

```powershell
docker compose cp docs/source-review-mods.json api:/tmp/source-review-mods.json
docker compose exec api python -m app.source_registry review <ID> --file /tmp/source-review-mods.json
docker compose exec api python -m app.source_registry enable <ID>
docker compose exec api python -m app.collector --once --source-id <ID>
docker compose exec api python -m app.source_registry list
```

`add`는 빈 미검토 MODS 후보만 안전하게 전환하며, 활성화되었거나 이미 수집 이력이 있는 출처는 수정하지 않습니다. 기존 출처를 먼저 `list`로 확인하세요. 실제 로컬 연결에서는 공식 RSS 10건 가운데 제1유형 3건만 저장되고, 명시적인 다른 유형 2건은 제외됐으며, 나머지 5건은 명확한 제1유형 표시가 확인되지 않아 보류됐습니다. HTML 구조가 바뀌거나 라이선스가 제1유형 이외로 바뀌면 새 기사를 수집하지 않으며, 표시 범위를 바꾸기 전에 출처 권리를 다시 검토해야 합니다.
