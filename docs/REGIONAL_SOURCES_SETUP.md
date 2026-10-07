# 대구·전남광주 보도자료 연결

두 공식 피드는 원문 기사마다 공공누리 유형이 달라질 수 있어 일반 RSS 어댑터로 수집하지 않습니다. 전용 어댑터가 원문 페이지의 공식 `kogl.or.kr` 링크와 제1유형 표시를 모두 확인한 기사만 제목·출처·원문 링크·게시 시각으로 저장합니다. 제2~4유형으로 바뀐 기사는 저장본에서 삭제하고, 표시가 없거나 원문 확인에 실패한 기사는 보류합니다. 본문·사진·첨부파일은 수집하지 않습니다.

2026-10-07에 대구 시정뉴스 RSS 최근 20건을 확인했으며 10건은 제1유형, 나머지 10건은 제4유형이었습니다. 전남광주 보도자료 RSS 최근 10건은 모두 제1유형이었습니다. 따라서 두 출처 모두 게시물별 제1유형 검증을 적용해 조건부로 사용합니다. 대구 RSS가 안내하는 시정뉴스에는 보도자료 외에 핫이슈·해명자료 등도 포함될 수 있습니다. [대구 RSS 안내](https://info.daegu.go.kr/newshome/mtnmain.php?mtnkey=rss), [대구 공공저작물 이용안내](https://www.daegu.go.kr/index.do?menu_id=00050251), [대구 제1유형 기사 예시](https://info.daegu.go.kr/newshome/mtnmain.php?aid=275767&mkey=1&mtnkey=articleview), [대구 제4유형 기사 예시](https://info.daegu.go.kr/newshome/mtnmain.php?aid=275470&mkey=26&mtnkey=articleview).

전남 RSS의 일부 원문 링크는 HTTP로 제공되어, 수집기는 공식 `jeonnam.go.kr` 호스트의 지정된 보도자료 경로와 식별자를 검증한 뒤 HTTPS 주소로 바꿔 요청·표시합니다. 다만 현재 피드의 10개 기사는 2026-06-29~07-01 게시분이라 최신 뉴스 기준을 벗어나 현재 source ID 11을 비활성화했습니다. 피드에 최근 7일 이내 게시물이 나타나면 아래 순서대로 권리 검토를 적용하고 다시 활성화하세요. [전남광주 보도자료 RSS 안내](https://www.jeonnam.go.kr/contentsView.do?menuId=jeonnam0803000000), [전남광주 저작권 정책](https://www.jeonnam.go.kr/contentsView.do?menuId=jeonnam0816000000), [전남 제1유형 기사 예시](https://www.jeonnam.go.kr/M7116/boardView.do?boardId=M7116&menuId=jeonnam0202000000&seq=1961851).

기존에 등록된 비활성 후보는 아래 명령이 비어 있는 항목만 전용 어댑터로 바꿉니다. 이미 활성화되었거나 수집 이력이 있는 출처는 자동 변경하지 않습니다.

```powershell
docker compose exec api python -m app.source_registry add --name "대구광역시 뉴스룸 시정뉴스" --adapter daegu_press_release --feed-url "https://info.daegu.go.kr/rss/rss.php?sgidx=1" --terms-url "https://www.daegu.go.kr/index.do?menu_id=00050251" --interval 60
docker compose cp docs/source-review-daegu.json api:/tmp/source-review-daegu.json
docker compose exec api python -m app.source_registry review <ID> --file /tmp/source-review-daegu.json
docker compose exec api python -m app.source_registry enable <ID>
docker compose exec api python -m app.collector --once --source-id <ID>

docker compose exec api python -m app.source_registry add --name "전남광주통합특별시 보도자료" --adapter jeonnam_press_release --feed-url "https://www.jeonnam.go.kr/M7116/boardRss.do" --terms-url "https://www.jeonnam.go.kr/contentsView.do?menuId=jeonnam0816000000" --interval 60
docker compose cp docs/source-review-jeonnam.json api:/tmp/source-review-jeonnam.json
docker compose exec api python -m app.source_registry review <ID> --file /tmp/source-review-jeonnam.json
docker compose exec api python -m app.source_registry enable <ID>
docker compose exec api python -m app.collector --once --source-id <ID>
```

두 출처 모두 30분보다 짧은 수집 간격을 허용하지 않습니다. 기사 페이지 확인은 피드당 최대 50건이며, 외부 도메인·다른 경로의 링크는 요청하지 않습니다.
