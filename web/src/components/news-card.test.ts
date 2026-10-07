import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import NewsCard from "./news-card";
import type { Article } from "@/lib/types";

function makeArticle(overrides: Partial<Article> = {}): Article {
  return {
    id: 1,
    title: "서울 교통 정책 발표",
    source: "테스트 언론사",
    content_type: "news",
    url: "https://publisher.example/news/1",
    published_at: "2026-10-07T00:00:00Z",
    collected_at: "2026-10-07T00:01:00Z",
    geo_scope: "regional",
    regions: [{ code: "KR-11", name: "서울특별시" }],
    topics: [{ slug: "society", name: "사회" }],
    ...overrides,
  };
}

describe("NewsCard", () => {
  it("renders region, source and topic metadata with a safe original link", () => {
    const markup = renderToStaticMarkup(createElement(NewsCard, { article: makeArticle() }));

    expect(markup).toContain("관련 지역 · 서울특별시");
    expect(markup).toContain("테스트 언론사");
    expect(markup).toContain("사회");
    expect(markup).toContain(
      'href="https://publisher.example/news/1" target="_blank" rel="noopener noreferrer"',
    );
    expect(markup).toContain("서울 교통 정책 발표");
  });

  it("labels press releases and never links unsafe article URLs", () => {
    const markup = renderToStaticMarkup(
      createElement(NewsCard, {
        article: makeArticle({
          content_type: "press_release",
          title: "<script>alert(1)</script> 보도자료",
          url: "javascript:alert(1)",
          geo_scope: "national",
          regions: [],
        }),
      }),
    );

    expect(markup).toContain("<strong class=\"content-type\">보도자료</strong>");
    expect(markup).toContain("관련 지역 · 전국");
    expect(markup).toContain("&lt;script&gt;alert(1)&lt;/script&gt; 보도자료");
    expect(markup).not.toContain("<a ");
    expect(markup).not.toContain("javascript:");
  });
});
