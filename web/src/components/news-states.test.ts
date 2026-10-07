import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { EmptyNewsState, LoadingNewsState, NewsErrorState } from "./news-states";

describe("news list states", () => {
  it("exposes an accessible loading status", () => {
    const markup = renderToStaticMarkup(createElement(LoadingNewsState));

    expect(markup).toContain('role="status" aria-label="뉴스 불러오는 중"');
    expect(markup.match(/class="skeleton"/g)).toHaveLength(3);
  });

  it("exposes an alert and retry action after a request failure", () => {
    const markup = renderToStaticMarkup(createElement(NewsErrorState, { onRetry: () => undefined }));

    expect(markup).toContain('role="alert"');
    expect(markup).toContain("뉴스 데이터를 불러오지 못했습니다.");
    expect(markup).toContain("다시 시도");
  });

  it("explains empty results and offers a filter reset", () => {
    const markup = renderToStaticMarkup(createElement(EmptyNewsState, { onReset: () => undefined }));

    expect(markup).toContain("조건에 맞는 뉴스가 없습니다.");
    expect(markup).toContain("기간을 넓히거나 검색 조건을 바꿔보세요.");
    expect(markup).toContain("필터 초기화");
  });
});
