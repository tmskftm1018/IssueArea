import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { defaults, queryFor, readFilters, safeArticleUrl } from "./filters.ts";
describe("filter URL semantics", () => {
  it("restores shared URL state", () => {
    const state = { ...defaults, region: "KR-11", topics: ["economy", "technology"], q: "반도체", page: 2 };
    assert.deepEqual(readFilters(queryFor(state)), state);
  });
  it("keeps selected region out of map aggregation", () => {
    const query = queryFor({ ...defaults, region: "KR-11", page: 4, q: "산불" }, false);
    assert.equal(query, "hours=24&q=%EC%82%B0%EB%B6%88");
  });
  it("rejects unsupported time and pagination values", () => {
    assert.deepEqual(readFilters("hours=2&page=-1"), defaults);
  });
  it("rejects executable and credential URLs", () => {
    assert.equal(safeArticleUrl("javascript:alert(1)"), false);
    assert.equal(safeArticleUrl("https://user:password@example.com"), false);
    assert.equal(safeArticleUrl("https://example.com/news/demo-001"), true);
  });
});
