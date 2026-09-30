export type Filters = { region: string; topics: string[]; hours: number; q: string; page: number };
export const defaults: Filters = { region: "", topics: [], hours: 24, q: "", page: 1 };
export function readFilters(query: string): Filters {
  const p = new URLSearchParams(query);
  const hours = Number(p.get("hours") || 24);
  const page = Number(p.get("page") || 1);
  return { region: p.get("region") || "", topics: (p.get("topics") || "").split(",").filter(Boolean),
    hours: [1, 6, 24, 168].includes(hours) ? hours : 24, q: (p.get("q") || "").slice(0, 200),
    page: Number.isInteger(page) && page > 0 ? page : 1 };
}
export function queryFor(f: Filters, includeRegion = true): string {
  const p = new URLSearchParams({ hours: String(f.hours) });
  if (f.topics.length) p.set("topics", f.topics.join(","));
  if (f.q) p.set("q", f.q);
  if (includeRegion && f.region) p.set("region", f.region);
  if (includeRegion) p.set("page", String(f.page));
  return p.toString();
}
export function safeArticleUrl(url: string): boolean {
  try { const parsed = new URL(url); return ["http:", "https:"].includes(parsed.protocol) && !parsed.username && !parsed.password; }
  catch { return false; }
}
export function koreanTime(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(value));
}
export function relativeKoreanTime(value: string): string {
  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (!Number.isFinite(elapsedSeconds)) return "시간 정보 없음";
  if (elapsedSeconds < 60) return "방금 전";
  const units: [number, Intl.RelativeTimeFormatUnit][] = [
    [60 * 60 * 24 * 365, "year"], [60 * 60 * 24 * 30, "month"],
    [60 * 60 * 24, "day"], [60 * 60, "hour"], [60, "minute"], [1, "second"],
  ];
  const rtf = new Intl.RelativeTimeFormat("ko-KR", { numeric: "auto" });
  for (let i = 0; i < units.length; i++) {
    const [seconds, unit] = units[i];
    if (elapsedSeconds >= seconds || i === 0) {
      return rtf.format(-Math.floor(elapsedSeconds / seconds), unit);
    }
  }
  return "방금 전";
}
