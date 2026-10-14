"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { defaults, koreanTime, queryFor, readFilters, type Filters } from "@/lib/filters";
import type { Freshness, MapData, News, SubregionCollection, Topic } from "@/lib/types";
import NewsCard from "./news-card";
import Icon from "./icon";
import { EmptyNewsState, LoadingNewsState, NewsErrorState } from "./news-states";
const RegionMap = dynamic(() => import("./region-map"), { ssr: false, loading: () => <div className="map-loading">지도 준비 중…</div> });
const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";
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
  const [subregions, setSubregions] = useState<SubregionCollection | null>(null);
  const [subregionError, setSubregionError] = useState(false);
  const [subregionRefresh, setSubregionRefresh] = useState(0);
  const [fresh, setFresh] = useState<Freshness | null>(null);
  const [completedRequest, setCompletedRequest] = useState("");
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const requestKey = `${queryFor(filters)}:${refresh}`;
  const loading = !ready || completedRequest !== requestKey;
  const drilldown = filters.drilldown;
  const update = useCallback((patch: Partial<Filters>) => {
    const next = { ...filters, page: 1, ...patch };
    window.history.pushState(null, "", `${basePath}/?${queryFor(next)}`);
    setFilters(next);
  }, [filters]);
  useEffect(() => {
    const restore = () => { const f = readFilters(window.location.search); setFilters(f); setInput(f.q); setSubregions(null); setSubregionError(false); setReady(true); };
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
  useEffect(() => {
    if (!ready || !drilldown || !filters.region) return;
    const controller = new AbortController();
    setSubregionError(false);
    const query = new URLSearchParams(queryFor(filters, false));
    query.set("region", filters.region);
    request<SubregionCollection>(`/api/v1/map/subregions?${query}`, controller.signal)
      .then(setSubregions).catch(() => { if (!controller.signal.aborted) { setSubregions(null); setSubregionError(true); } });
    return () => controller.abort();
  }, [filters.region, filters.hours, filters.topics, filters.q, drilldown, ready, subregionRefresh]);
  const selectRegion = useCallback((region: string) => { update({ region, locality: "", drilldown: false }); setSubregions(null); }, [update]);
  const selectRegionOnMap = useCallback((region: string) => { update({ region, locality: "", drilldown: true }); setSubregions(null); setSubregionError(false); }, [update]);
  const selectLocality = useCallback((locality: string) => update({ locality, drilldown: true }), [update]);
  const reset = () => { setInput(""); setSubregions(null); setSubregionError(false); update(defaults); };
  const selected = mapData?.regions.find(r => r.code === filters.region);
  const selectedSubregion = subregions?.features.find(f => f.properties.name === filters.locality)?.properties.name;
  const mapAllowed = (process.env.NEXT_PUBLIC_MAP_PROVIDER || "leaflet_osm") === "leaflet_osm" && (process.env.NEXT_PUBLIC_APP_ENV !== "production" || process.env.NEXT_PUBLIC_MAP_ENABLED === "true");
  const hasFilters = Boolean(filters.region || filters.q || filters.topics.length || filters.hours !== defaults.hours);
  return <main>
    <a className="skip-link" href="#explore">뉴스 탐색으로 바로가기</a>
    <header className="site-header"><Link className="brand" href="/" translate="no"><span className="brand-icon"><Icon name="map-pin" /></span>{process.env.NEXT_PUBLIC_APP_NAME || "IssueArea"}<span className="brand-sub">지역에서 발견하는 뉴스</span></Link><nav className="header-nav" aria-label="화면 바로가기"><a href="#region-map">지도 탐색</a><a href="#news-list">뉴스 목록</a></nav></header>
    <section className="intro"><div><h1>지역으로 읽는 오늘의 뉴스</h1><p>궁금한 지역을 고르면, 그곳의 이야기가 보입니다.</p></div><div className="freshness"><div className="freshness-status"><span className={`status-dot ${fresh?.status === "healthy" ? "healthy" : ""}`} />주기적으로 업데이트</div><small><Icon name="clock" />{fresh?.last_successful_collection_at ? `최근 수집 ${koreanTime(fresh.last_successful_collection_at)}` : "수집 기록을 기다리는 중"}</small></div></section>
    {fresh?.demo_mode && <div className="demo-banner"><strong>DEMO</strong> 가상의 개발용 기사입니다. 원문 링크는 example.com 예시 주소로 연결됩니다.</div>}
    <section className="filter-panel" aria-label="뉴스 검색 및 필터"><div className="search-row"><label className="search-box"><Icon name="search" /><input type="search" name="q" autoComplete="off" aria-label="뉴스 제목 검색" placeholder="검색할 뉴스 제목을 입력하세요…" value={input} maxLength={200} onChange={e => setInput(e.target.value)} /></label><label className="time-select"><Icon name="clock" /><span>기간</span><select name="hours" aria-label="뉴스 기간" value={filters.hours} onChange={e => update({ hours: Number(e.target.value) })}>{[[1,"최근 1시간"],[6,"최근 6시간"],[24,"최근 24시간"],[168,"최근 7일"]].map(([v,l]) => <option key={v} value={v}>{l}</option>)}</select></label></div>
      <div className="topic-row"><span className="filter-label">관심 주제</span><button className={`chip ${!filters.topics.length ? "active" : ""}`} aria-pressed={!filters.topics.length} onClick={() => update({ topics: [] })}>전체</button>{topics.map(t => <button key={t.slug} className={`chip ${filters.topics.includes(t.slug) ? "active" : ""}`} aria-pressed={filters.topics.includes(t.slug)} onClick={() => update({ topics: filters.topics.includes(t.slug) ? filters.topics.filter(s => s !== t.slug) : [...filters.topics, t.slug] })}>{t.name}</button>)}</div>
    </section>
    <div className="explore-context" id="explore" tabIndex={-1}><span><Icon name="map-pin" /><strong>{selectedSubregion || selected?.short_name || "대한민국 전체"}</strong><span className="context-note">{drilldown ? "시군구 탐색" : "지역별 뉴스 탐색"}</span></span>{hasFilters && <button className="text-button" onClick={reset}>필터 초기화</button>}</div>
    <div className="workspace"><section className="map-panel" id="region-map"><div className="panel-heading"><div><h2>지역별 뉴스</h2><p>{drilldown ? "경계나 지역 이름을 선택해 자세히 살펴보세요." : "지역 묶음을 누르면 확대되고, 지역을 고르면 뉴스가 바뀝니다."}</p></div><button className="text-button" onClick={() => selectRegion("")}>전국 보기</button></div>
      {mapAllowed ? <RegionMap regions={error || loading || drilldown ? [] : mapData?.regions || []} selected={filters.region} onSelect={selectRegionOnMap} subregions={subregions} selectedLocality={filters.locality} onSelectLocality={selectLocality} /> : <div className="map-loading">지도 공급자 설정이 필요합니다. 뉴스 목록은 계속 확인할 수 있습니다.<br />현재 단계는 개발용 Leaflet/OSM을 지원합니다.</div>}
      {filters.region && <div className="drilldown-actions"><button className="text-button" onClick={() => { update({ drilldown: !drilldown, locality: drilldown ? "" : filters.locality }); setSubregions(null); setSubregionError(false); }}>{drilldown ? "시도 지도 보기 ↑" : "시군구 자세히 보기 ↓"}</button>{drilldown && !subregions && !subregionError && <span>시군구 경계를 불러오는 중…</span>}{drilldown && subregionError && <span role="status">경계를 불러오지 못했어요. <button className="text-button" onClick={() => setSubregionRefresh(v => v + 1)}>다시 시도</button></span>}{drilldown && subregions && <span>시군구를 누르면 해당 뉴스만 보여요</span>}</div>}
      {drilldown && subregions ? <div className="region-list" aria-label="시군구 선택">{subregions.features.map(f => <button key={f.properties.code} aria-pressed={filters.locality === f.properties.name} className={filters.locality === f.properties.name ? "selected" : ""} onClick={() => selectLocality(filters.locality === f.properties.name ? "" : f.properties.name)}>{f.properties.name}<strong>{f.properties.count}</strong></button>)}</div> : <div className="region-list" aria-label="지역 선택">{mapData?.regions.map(r => <button key={r.code} disabled={loading || error} aria-pressed={filters.region === r.code} className={filters.region === r.code ? "selected" : ""} onClick={() => selectRegion(r.code)}>{filters.region === r.code ? "✓ " : ""}{r.short_name}<strong>{error || loading ? "–" : r.count}</strong></button>)}</div>}<div className="map-footnote">시군구 기사 수는 제목에 지역명이 명시된 기사 기준이에요. 경계 데이터: VWorld. {mapData && !error && !loading && `전국·지역 미분류 ${mapData.unmapped_count}건`}</div>
    </section><section className="news-panel" id="news-list" aria-label="뉴스 목록" aria-busy={loading}><div className="panel-heading"><div><h2>{selectedSubregion || selected?.short_name || "전국"} 최신 뉴스 {!error && !loading && <span className="count-badge">{news?.total || 0}</span>}</h2><p>제목을 누르면 원문이 새 탭에서 열립니다.</p></div>{filters.region && <button className="text-button" onClick={() => selectRegion("")}>지역 해제 ×</button>}</div>
      {loading ? <LoadingNewsState /> : error ? <NewsErrorState onRetry={() => setRefresh(v => v + 1)} /> : !news?.items.length ? <EmptyNewsState onReset={reset} /> : <><div className="news-list">{news.items.map(a => <NewsCard article={a} key={a.id} />)}</div><nav className="pagination" aria-label="뉴스 페이지"><button disabled={filters.page === 1} onClick={() => update({ page: filters.page - 1 })}>← 이전</button><span>{filters.page} / {Math.max(1, Math.ceil(news.total / news.page_size))}</span><button disabled={filters.page * news.page_size >= news.total} onClick={() => update({ page: filters.page + 1 })}>다음 →</button></nav></>}
    </section></div>
    <footer><strong>IssueArea</strong><p>본 서비스는 기사 제목, 출처 및 관련 지역 정보를 제공하며 기사 원문은 각 언론사에서 확인할 수 있습니다.</p><span>위치는 사건 좌표가 아닌 관련 지역의 대표 위치입니다.</span></footer>
  </main>;
}
