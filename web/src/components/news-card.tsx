import type { Article } from "@/lib/types";
import { koreanDate, koreanTime, relativeKoreanTime, safeArticleUrl } from "@/lib/filters";
import Icon from "./icon";
export default function NewsCard({ article }: { article: Article }) {
  const region = article.regions.map(r => r.name).join(" · ") || (article.geo_scope === "national" ? "전국" : "지역 미분류");
  return <article className="news-card">
    <div className="card-region"><span className="article-location"><Icon name="map-pin" />{region}</span>{article.content_type === "press_release" && <strong className="content-type">보도자료</strong>}</div>
    <h3>{safeArticleUrl(article.url) ? <a className="article-title-link" href={article.url} target="_blank" rel="noopener noreferrer">{article.title}<Icon name="arrow-up-right" className="article-link-icon" /><span className="sr-only"> (새 탭)</span></a> : article.title}</h3>
    <div className="card-meta"><span>{article.source}</span><time dateTime={article.published_at || article.collected_at} title={article.published_precision === "date" && article.published_at ? koreanDate(article.published_at) : koreanTime(article.published_at || article.collected_at)}>{article.published_precision === "date" && article.published_at ? koreanDate(article.published_at) : relativeKoreanTime(article.published_at || article.collected_at)}</time></div>
    {article.topics.length > 0 && <div className="card-bottom"><div className="tags">{article.topics.map(t => <span key={t.slug}>{t.name}</span>)}</div></div>}
  </article>;
}
