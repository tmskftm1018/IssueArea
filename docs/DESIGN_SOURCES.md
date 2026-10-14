# IssueArea 디자인 스킬과 오픈 소스

2026-10-14에 검토한 GitHub 소스입니다. 설치와 다운로드는 아래 커밋으로 고정했습니다.

## 설치한 Codex 스킬

| 스킬 | 용도 | 라이선스 | 소스 |
| --- | --- | --- | --- |
| frontend-design | 지도·기사 탐색에 맞는 색상, 서체, 정보 위계와 레이아웃 설계 | Apache-2.0 | [anthropics/skills](https://github.com/anthropics/skills/tree/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/frontend-design) |
| web-design-guidelines | 키보드 접근성, 초점 표시, 폼, 반응형 UI와 사용성 점검 | MIT (상위 저장소 README 명시) | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/tree/063bee94c3f4df8453406c830b0a7df0f2860278/skills/web-design-guidelines) |

스킬은 이 컴퓨터의 `~/.codex/skills/`에 설치되어 다음 대화 턴부터 사용할 수 있습니다. 프로젝트의 npm 의존성이 아니며 다른 컴퓨터에는 별도로 설치해야 합니다. frontend-design의 LICENSE.txt와 web-design-guidelines의 상위 저장소 README를 설치 폴더에 보관했습니다.

web-design-guidelines는 점검할 때 Vercel의 최신 공개 가이드라인을 읽습니다. 두 스킬에 실행 스크립트나 유료 API 의존성은 없습니다. 사용자 지시와 저장소의 작업 지침을 우선합니다.

## 가져온 UI 소스

[Lucide](https://github.com/lucide-icons/lucide/tree/dab294f313897bacaa968b725b3259fa37c17bd1)에서 다음 SVG를 가져왔습니다.

| 파일 | 적용할 위치 |
| --- | --- |
| search.svg | 기사 검색 |
| map-pin.svg | 지역 선택과 지도 안내 |
| clock.svg | 기사 게시 시각과 업데이트 상태 |
| arrow-up-right.svg | 원문으로 연결되는 기사 제목 |

파일은 `web/public/icons/lucide/`에 있으며, 원본 `LICENSE`도 함께 보관합니다. Lucide는 ISC 라이선스이고 일부 Feather 유래 아이콘에는 MIT 라이선스도 적용됩니다. 가져온 아이콘은 원본 SVG 그대로이며 사용 시 저작권·라이선스 고지를 유지해야 합니다.

네 아이콘의 SVG 도형을 `web/src/components/icon.tsx`에 적용했습니다. 검색창·브랜드·지역 표시·수집 시각·기사 원문 연결에 사용하며, 장식용 아이콘은 접근성 트리에서 숨깁니다. 일부 색상과 크기는 IssueArea에 맞게 조정했습니다. 별도의 아이콘 패키지나 애니메이션 라이브러리는 추가하지 않았습니다.
