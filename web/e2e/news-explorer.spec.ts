import { expect, test, type Page } from "@playwright/test";

const regions = [
  { code: "KR-11", name: "서울특별시", short_name: "서울", latitude: 37.5665, longitude: 126.978, count: 2 },
  { code: "KR-28", name: "인천광역시", short_name: "인천", latitude: 37.4563, longitude: 126.7052, count: 1 },
  { code: "KR-26", name: "부산광역시", short_name: "부산", latitude: 35.1796, longitude: 129.0756, count: 1 },
];
const topics = [{ slug: "politics", name: "정치" }, { slug: "economy", name: "경제" }];
const seoulSubregions = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { code: "11680", name: "강남구", count: 1 },
      geometry: { type: "Polygon", coordinates: [[[127.02, 37.49], [127.08, 37.49], [127.08, 37.54], [127.02, 37.54], [127.02, 37.49]]] },
    },
    {
      type: "Feature",
      properties: { code: "11110", name: "종로구", count: 0 },
      geometry: { type: "Polygon", coordinates: [[[126.96, 37.56], [127.00, 37.56], [127.00, 37.60], [126.96, 37.60], [126.96, 37.56]]] },
    },
  ],
};
const articles = [
  { id: 1, title: "서울 반도체 산업 지원 발표", source: "IssueArea 테스트 뉴스", content_type: "news", url: "https://news.example.test/seoul", published_at: "2026-09-30T02:00:00Z", collected_at: "2026-09-30T02:05:00Z", geo_scope: "regional", regions: [{ code: "KR-11", name: "서울특별시" }], topics: [{ slug: "economy", name: "경제" }] },
  { id: 2, title: "인천 교통 정책 발표", source: "IssueArea 테스트 뉴스", content_type: "press_release", url: "https://news.example.test/incheon", published_at: "2026-09-30T01:00:00Z", collected_at: "2026-09-30T01:05:00Z", geo_scope: "regional", regions: [{ code: "KR-28", name: "인천광역시" }], topics: [{ slug: "politics", name: "정치" }] },
  { id: 3, title: "부산 해양 산업 동향", source: "IssueArea 테스트 뉴스", content_type: "news", url: "https://news.example.test/busan", published_at: "2026-09-30T00:00:00Z", collected_at: "2026-09-30T00:05:00Z", geo_scope: "regional", regions: [{ code: "KR-26", name: "부산광역시" }], topics: [{ slug: "economy", name: "경제" }] },
];

async function mockApi(page: Page, options: { failNewsUntilRetry?: boolean; delayNewsMs?: number } = {}) {
  let shouldFailNews = Boolean(options.failNewsUntilRetry);
  page.on("requestfailed", request => {
    if (request.url().includes("/api/v1/")) console.log(`API request failed: ${request.url()}`);
  });
  await page.route("**/api/v1/**", async route => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/news") && shouldFailNews) {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "temporary failure" }) });
      return;
    }
    if (url.pathname.endsWith("/news")) {
      if (options.delayNewsMs) await new Promise(resolve => setTimeout(resolve, options.delayNewsMs));
      const items = articles.filter(article =>
        (!url.searchParams.get("region") || article.regions.some(region => region.code === url.searchParams.get("region"))) &&
        (!url.searchParams.get("topics") || article.topics.some(topic => url.searchParams.get("topics")?.split(",").includes(topic.slug))) &&
        (!url.searchParams.get("q") || article.title.includes(url.searchParams.get("q")!)),
      );
      const pageNumber = Number(url.searchParams.get("page") || 1);
      const pageSize = 10;
      await route.fulfill({ json: { items: items.slice((pageNumber - 1) * pageSize, pageNumber * pageSize), total: items.length, page: pageNumber, page_size: pageSize } });
    } else if (url.pathname.endsWith("/map/regions")) {
      await route.fulfill({ json: { regions, unmapped_count: 1 } });
    } else if (url.pathname.endsWith("/map/subregions")) {
      await route.fulfill({ json: seoulSubregions });
    } else if (url.pathname.endsWith("/topics")) {
      await route.fulfill({ json: topics });
    } else if (url.pathname.endsWith("/system/freshness")) {
      await route.fulfill({ json: { last_successful_collection_at: "2026-09-30T02:05:00Z", status: "healthy", demo_mode: false } });
    } else {
      await route.fulfill({ status: 404, json: { detail: "not found" } });
    }
  });
  // Map interactions are tested against Leaflet markers; external OSM availability is irrelevant.
  await page.route("https://tile.openstreetmap.org/**", route => route.abort());
  return { recoverNews: () => { shouldFailNews = false; } };
}

test("검색·지역·주제 필터가 뉴스 목록에 반영되고 제목은 안전한 원문 링크다", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /전국 최신 뉴스/ })).toBeVisible();
  await expect(page.getByRole("link", { name: "서울 반도체 산업 지원 발표" })).toHaveAttribute("href", "https://news.example.test/seoul");
  await expect(page.getByRole("link", { name: "서울 반도체 산업 지원 발표" })).toHaveAttribute("target", "_blank");
  await expect(page.getByRole("link", { name: "서울 반도체 산업 지원 발표" })).toHaveAttribute("rel", "noopener noreferrer");

  await page.locator('[aria-label="지역 선택"]').getByRole("button", { name: /서울\s*2/ }).click();
  await expect(page).toHaveURL(/region=KR-11/);
  await expect(page.getByRole("heading", { name: /서울 최신 뉴스/ })).toBeVisible();
  await expect(page.getByRole("link", { name: "서울 반도체 산업 지원 발표" })).toBeVisible();
  await expect(page.getByRole("link", { name: "인천 교통 정책 발표" })).toHaveCount(0);

  const search = page.getByRole("textbox", { name: "뉴스 제목 검색" });
  await search.fill("반도체");
  await expect(page).toHaveURL(/q=%EB%B0%98%EB%8F%84%EC%B2%B4/);
  await expect(page.getByRole("link", { name: "서울 반도체 산업 지원 발표" })).toBeVisible();

  await page.getByRole("button", { name: "경제" }).click();
  await expect(page).toHaveURL(/topics=economy/);
  await expect(page.getByRole("button", { name: "경제" })).toHaveAttribute("aria-pressed", "true");
});

test("지역 클러스터를 누르면 지도가 확대되어 개별 지역 마커로 펼쳐진다", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  const cluster = page.getByRole("button", { name: /개 지역 묶음, 눌러서 확대/ }).first();
  await expect(cluster).toBeVisible();
  await cluster.click();
  await expect(page.getByRole("button", { name: /서울특별시 2건 선택/ })).toBeVisible();
});

test("시군구 경계를 누르면 지역 필터가 적용되고 지도가 해당 지역 중심으로 이동한다", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("button", { name: /개 지역 묶음, 눌러서 확대/ }).first().click();
  const seoulMarker = page.getByRole("button", { name: "서울특별시 2건 선택" });
  await expect(seoulMarker).toBeVisible();
  await seoulMarker.click();
  await expect(page).toHaveURL(/region=KR-11/);
  await expect(page.getByRole("button", { name: "시도 지도 보기 ↑" })).toBeVisible();

  const neighborhood = page.locator("path.leaflet-interactive").first();
  await expect(neighborhood).toBeVisible();
  await neighborhood.click();
  await expect(page).toHaveURL(/locality=%EA%B0%95%EB%82%A8%EA%B5%AC/);

  await expect.poll(async () => neighborhood.evaluate(path => {
    const map = path.closest(".leaflet-container");
    if (!map) return Infinity;
    const shape = path.getBoundingClientRect();
    const viewport = map.getBoundingClientRect();
    return Math.hypot(
      (shape.left + shape.right) / 2 - (viewport.left + viewport.right) / 2,
      (shape.top + shape.bottom) / 2 - (viewport.top + viewport.bottom) / 2,
    );
  })).toBeLessThan(35);
  await expect.poll(() => neighborhood.evaluate(path => getComputedStyle(path).outlineStyle)).toBe("none");
});

test("일시적 API 오류를 다시 시도하면 뉴스 목록을 복구한다", async ({ page }) => {
  const api = await mockApi(page, { failNewsUntilRetry: true });
  await page.goto("/");
  await expect(page.getByText("뉴스 데이터를 불러오지 못했습니다.", { exact: true })).toBeVisible();
  api.recoverNews();
  await page.getByRole("button", { name: "다시 시도" }).click();
  await expect(page.getByRole("link", { name: "서울 반도체 산업 지원 발표" })).toBeVisible();
});

test("검색 결과가 없으면 안내를 보이고 필터 초기화로 뉴스 목록을 복구한다", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  const search = page.getByRole("textbox", { name: "뉴스 제목 검색" });
  await search.fill("존재하지 않는 뉴스");
  await expect(page.getByText("조건에 맞는 뉴스가 없습니다.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "필터 초기화" }).click();
  await expect(page.getByRole("link", { name: "서울 반도체 산업 지원 발표" })).toBeVisible();
  await expect(search).toHaveValue("");
});

test("뉴스를 불러오는 동안 접근 가능한 로딩 상태를 표시한다", async ({ page }) => {
  await mockApi(page, { delayNewsMs: 500 });
  await page.goto("/");
  await expect(page.getByRole("status", { name: "뉴스 불러오는 중" })).toBeVisible();
  await expect(page.getByRole("link", { name: "서울 반도체 산업 지원 발표" })).toBeVisible();
});

test("보도자료 카드는 유형을 표시하면서 제목을 원문으로 연결한다", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  const headline = page.getByRole("link", { name: "인천 교통 정책 발표" });
  const card = page.locator("article.news-card").filter({ has: headline });
  await expect(card.getByText("보도자료", { exact: true })).toBeVisible();
  await expect(headline).toHaveAttribute("href", "https://news.example.test/incheon");
});
