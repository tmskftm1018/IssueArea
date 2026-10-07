export type Region = { code: string; name: string; short_name: string; latitude: number; longitude: number; count: number };
export type Topic = { slug: string; name: string };
export type Article = { id: number; title: string; source: string; content_type: "news" | "press_release"; url: string; published_at: string | null; published_precision?: "date" | "datetime" | null; collected_at: string; geo_scope: string; regions: Pick<Region, "code" | "name">[]; topics: Topic[] };
export type News = { items: Article[]; total: number; page: number; page_size: number };
export type MapData = { regions: Region[]; unmapped_count: number };
export type Freshness = { last_successful_collection_at: string | null; status: string; demo_mode: boolean };
