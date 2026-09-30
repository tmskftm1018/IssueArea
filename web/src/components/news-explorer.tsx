"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { defaults, koreanTime, queryFor, readFilters, type Filters } from "@/lib/filters";
import type { Freshness, MapData, News, Topic } from "@/lib/types";
import NewsCard from "./news-card";
const RegionMap = dynamic(() => import("./region-map"), { ssr: false, loading: () => <div className="map-loading">지도 준비 중…</div> });
const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
async function request<T>(path: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(`${base}${path}`, { signal });
  if (!response.ok) throw new Error(`API ${response.status}`);
  return response.json() as Promise<T>;
}
export default function NewsExplorer() {
  const [filters, setFilters] = useState<Filters>(defaults);
  const [input, setInput] = useState("");
  const [ready, setReady] = useState(false);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [news, setNews] = useState<News | null>(null);
  const [mapData, setMapData] = useState<MapData | null>(null);
  const [fresh, setFresh] = useState<Freshness | null>(null);
  const [completedRequest, setCompletedRequest] = useState("");
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const requestKey = `${queryFor(filters)}:${refresh}`;
  const loading = !ready || completedRequest !== requestKey;
  const update = useCallback((patch: Partial<Filters>) => {
    const next = { ...filters, page: 1, ...patch };
    window.history.pushState(null, "", `/?${queryFor(next)}`);
    setFilters(next);
  }, [filters]);
  useEffect(() => {
    const restore = () => { const f = readFilters(window.location.search); setFilters(f); setInput(f.q); setReady(true); };
    restore();
    window.addEventListener("popstate", restore);
    const timer = window.setInterval(() => setRefresh(v => v + 1), 60000);
    return () => { window.removeEventListener("popstate", restore); window.clearInterval(timer); };
  }, []);
  useEffect(() => {
    if (!ready || input === filters.q) return;
    const timer = window.setTimeout(() => update({ q: input }), 300);
    return () => window.clearTimeout(timer);
  }, [input, filters.q, ready, update]);
  useEffect(() => {
    if (!ready) return;
    const controller = new AbortController();
    let active = true;
    const timeout = window.setTimeout(() => controller.abort(), 12000);
    Promise.all([
      request<News>(`/api/v1/news?${queryFor(filters)}`, controller.signal),
      request<MapData>(`/api/v1/map/regions?${queryFor(filters, false)}`, controller.signal),
      request<Topic[]>("/api/v1/topics", controller.signal),
      request<Freshness>("/api/v1/system/freshness", controller.signal),
    ]).then(([n, m, t, f]) => { if (active) { setNews(n); setMapData(m); setTopics(t); setFresh(f); setError(false); } })
      .catch(() => { if (active) setError(true); })
      .finally(() => { window.clearTimeout(timeout); if (active) setCompletedRequest(requestKey); });
    return () => { active = false; controller.abort(); window.clearTimeout(timeout); };
  }, [filters, ready, refresh, requestKey]);
  const selectRegion = useCallback((region: string) => update({ region }), [update]);
  const reset = () => { setInput(""); update(defaults); };
  const selected = mapData?.regions.find(r => r.code === filters.region);
  const mapAllowed = (process.env.NEXT_PUBLIC_MAP_PROVIDER || "leaflet_osm") === "leaflet_osm" && process.env.NEXT_PUBLIC_APP_ENV !== "production";
  return <main>
    <header className="site-header"><Link className="brand" href="/"><span className="brand-icon">I<span>↗</span></span>{process.env.NEXT_PUBLIC_APP_NAME || "IssueArea"}<span className="brand-sub">지역에서 발견하는 뉴스</span></Link><span className="header-note">대한민국 · 16개 광역 지역</span></header>
    <section className="intro"><div><div className="eyebrow">KOREA NEWS EXPLORER</div><h1>지금, 우리 지역의 이야기는?</h1><p>지도에서 지역을 선택하고 관심 있는 최신 뉴스를 찾아보세요.</p></div><div className="freshness"><span className={`status-dot ${fresh?.status === "healthy" ? "healthy" : ""}`} />주기적으로 업데이트<br /><small>{fresh?.last_successful_collection_at ? `마지막 업데이트 ${koreanTime(fresh.last_successful_collection_at)}` : "성공한 수집 기록을 기다리는 중"}</small></div></section>
    {fresh?.demo_mode && <div className="demo-banner"><strong>DEMO</strong> 가상의 개발용 기사입니다. 원문 링크는 example.com 예시 주소로 연결됩니다.</div>}
    <section className="filter-panel" aria-label="뉴스 검색 및 필터"><div className="search-row"><label className="search-box"><span aria-hidden="true">⌕</span><input aria-label="뉴스 제목 검색" placeholder="관심 있는 뉴스 제목을 검색하세요" value={input} maxLength={200} onChange={e => setInput(e.target.value)} /></label><label className="time-select"><span>기간</span><select aria-label="뉴스 기간" value={filters.hours} onChange={e => update({ hours: Number(e.target.value) })}>{[[1,"최근 1시간"],[6,"최근 6시간"],[24,"최근 24시간"],[168,"최근 7일"]].map(([v,l]) => <option key={v} value={v}>{l}</option>)}</select></label></div>
      <div className="topic-row"><span className="filter-label">관심 주제</span><button className={`chip ${!filters.topics.length ? "active" : ""}`} aria-pressed={!filters.topics.length} onClick={() => update({ topics: [] })}>전체</button>{topics.map(t => <button key={t.slug} className={`chip ${filters.topics.includes(t.slug) ? "active" : ""}`} aria-pressed={filters.topics.includes(t.slug)} onClick={() => update({ topics: filters.topics.includes(t.slug) ? filters.topics.filter(s => s !== t.slug) : [...filters.topics, t.slug] })}>{t.name}</button>)}</div>
    </section>
    <div className="workspace"><section className="map-panel"><div className="panel-heading"><div><h2>지역별 뉴스</h2><p>숫자는 기사 수예요. 가까운 지역 묶음을 누르면 확대됩니다.</p></div><button className="text-button" onClick={() => selectRegion("")}>전국 보기 ↗</button></div>
      {mapAllowed ? <RegionMap regions={error || loading ? [] : mapData?.regions || []} selected={filters.region} onSelect={selectRegion} /> : <div className="map-loading">지도 공급자 설정이 필요합니다. 뉴스 목록은 계속 확인할 수 있습니다.<br />현재 단계는 개발용 Leaflet/OSM을 지원합니다.</div>}
      <div className="region-list" aria-label="지역 선택">{mapData?.regions.map(r => <button key={r.code} disabled={loading || error} aria-pressed={filters.region === r.code} className={filters.region === r.code ? "selected" : ""} onClick={() => selectRegion(r.code)}>{filters.region === r.code ? "✓ " : ""}{r.short_name}<strong>{error || loading ? "–" : r.count}</strong></button>)}</div><div className="map-footnote">여러 지역 관련 기사는 각 지역에 포함됩니다. {mapData && !error && !loading && `전국·지역 미분류 ${mapData.unmapped_count}건`}</div>
    </section><section className="news-panel" aria-label="뉴스 목록" aria-busy={loading}><div className="panel-heading"><div><h2>{selected?.short_name || "전국"} 최신 뉴스 {!error && !loading && <span className="count-badge">{news?.total || 0}</span>}</h2><p>기사 원문은 각 출처에서 확인하세요.</p></div>{filters.region && <button className="text-button" onClick={() => selectRegion("")}>지역 해제 ×</button>}</div>
      {loading ? <div className="skeletons" role="status" aria-label="뉴스 불러오는 중">{[1,2,3].map(i => <div className="skeleton" key={i}><div /><div /><div /></div>)}</div> : error ? <div className="state-box" role="alert"><h3>뉴스 데이터를 불러오지 못했습니다.</h3><p>API 연결을 확인한 뒤 다시 시도해 주세요.</p><button className="primary-button" onClick={() => setRefresh(v => v + 1)}>다시 시도</button></div> : !news?.items.length ? <div className="state-box"><h3>조건에 맞는 뉴스가 없습니다.</h3><p>기간을 넓히거나 검색 조건을 바꿔보세요.</p><button className="primary-button" onClick={reset}>필터 초기화</button></div> : <><div className="news-list">{news.items.map(a => <NewsCard article={a} key={a.id} />)}</div><nav className="pagination" aria-label="뉴스 페이지"><button disabled={filters.page === 1} onClick={() => update({ page: filters.page - 1 })}>← 이전</button><span>{filters.page} / {Math.max(1, Math.ceil(news.total / news.page_size))}</span><button disabled={filters.page * news.page_size >= news.total} onClick={() => update({ page: filters.page + 1 })}>다음 →</button></nav></>}
    </section></div>
    <footer><strong>IssueArea</strong><p>본 서비스는 기사 제목, 출처 및 관련 지역 정보를 제공하며 기사 원문은 각 언론사에서 확인할 수 있습니다.</p><span>위치는 사건 좌표가 아닌 관련 지역의 대표 위치입니다.</span></footer>
  </main>;
}
