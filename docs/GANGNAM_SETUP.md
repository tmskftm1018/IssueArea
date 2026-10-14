# 강남구 보도자료 후보

강남구청은 서울시 자치구 RSS 목록에서 보도자료 피드를 제공합니다. 공식 RSS URL은 다음과 같습니다.

`https://www.gangnam.go.kr/portal/rss/rssList.do?bbsId=B_000031&recordCountPerPage=10`

## 현재 상태

- 전용 `gangnam_press_release` 어댑터는 구현되어 있습니다.
- 수집기가 게시물 원문에서 공공누리 공식 링크의 유형을 확인합니다. 제1유형은 검토된 사용 조건에 따라 수집할 수 있고, 제2유형은 출처 심사에서 상업 이용을 불허하고 `APP_USAGE_MODE=noncommercial`일 때만 저장합니다. 상업 모드에서는 제2유형 저장 항목도 제거합니다. 제3·4유형은 수집하지 않으며, 표시가 없거나 확인 실패한 신규 항목은 보류합니다.
- 출처 ID 4에 전용 어댑터를 등록했으며 권리 미검토·비활성 상태입니다. 서울시의 자치구 RSS 목록은 RSS 주소를 제공하지만, RSS 제공만으로 제목과 메타데이터의 재사용 권한이 확인되지는 않습니다.
- 확인한 강남구 보도자료 표본은 2026-08-21 게시된 기사이며, 공공누리 제2유형입니다. 강남구 정책은 유형이 표시되지 않은 자료에 대해 사전 협의를 요구합니다. 따라서 전체 피드 권리를 일괄 허용으로 간주하지 않습니다.
- 2026-10-14 실제 RSS 응답은 HTTP 200, XML, 최신 10개 항목이었습니다. RSS는 날짜만 제공하며 URL에 메뉴값이 빠져 원문 요청 시 302가 발생했습니다. 어댑터는 공식 강남구 원문 경로만 허용하고 `mid=ID01_0313`을 붙여 직접 검사합니다.
- 최신 10건의 원문 라이선스는 제2유형 7건, 제4유형 3건이었습니다. 즉 현재 `development` 또는 `commercial` 모드에서는 신규 기사 0건이며, 비상업 모드와 출처의 상업 이용 불허 심사가 적용될 때 제2유형 7건만 대상이 됩니다. 제4유형은 계속 제외합니다.
- 원문 RSS에 포함된 제목·출처·원문 URL·날짜를 이용해 사용자에게 표시하는 조건은 RSS XML의 공식 제공만으로 확정되지 않습니다. 메타데이터 재사용 조건과 필요한 출처표시 방식을 담당 기관에 확인하기 전까지 출처는 등록 상태를 유지하되 비활성으로 둡니다.

## 공식 근거

- [서울시 자치구 RSS 목록](https://www.seoul.go.kr/news/rssboard/siteList.do)
- [강남구 저작권 정책](https://www.gangnam.go.kr/contents/copyright/1/view.do?mid=ID06_040905)
- [제2유형으로 표시된 강남구 보도자료 표본](https://www.gangnam.go.kr/board/B_000031/1075298/view.do?mid=ID01_0313)
- [2026-10-13 민선 9기 공약 보도자료 표본](https://gangnam.go.kr/board/B_000031/1075466/view.do?mid=ID01_0313)
- [2026-10-13 개포주공 재건축 보도자료 표본](https://www.gangnam.go.kr/board/B_000031/1075464/view.do?mid=ID01_0)
- [강남구 보도자료 목록](https://www.gangnam.go.kr/board/B_000031/list.do?mid=ID01_0313)

출처 ID 4는 기존 미검토 placeholder를 전용 어댑터로 안전하게 전환한 항목입니다. 추가 중복 등록을 시도하지 마세요. 권리 검토가 끝나기 전에는 `enable`을 실행하지 않습니다. 신규 후보에는 최소 30분 간격과 `gangnam_press_release` 어댑터를 지정합니다.

```powershell
docker compose exec api python -m app.source_registry add --name "강남구청 보도자료" --feed-url "https://www.gangnam.go.kr/portal/rss/rssList.do?bbsId=B_000031&recordCountPerPage=10" --terms-url "https://www.gangnam.go.kr/contents/copyright/1/view.do?mid=ID06_040905" --interval 60 --adapter gangnam_press_release
```

이 명령은 기본적으로 출처를 비활성·미검토 상태로 등록합니다. 실제 권리 검토 기록을 작성하고 제1유형만 저장하는 조건과 RSS 메타데이터 재사용 근거를 확인한 뒤 별도 절차로 검토·활성화해야 합니다.
