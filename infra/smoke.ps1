$ErrorActionPreference = 'Stop'
$apiBase = 'http://localhost:8000'
$health = Invoke-RestMethod "$apiBase/health"
if ($health.status -ne 'ok') { throw 'API health failed' }
$news = Invoke-RestMethod "$apiBase/api/v1/news?hours=24"
$map = Invoke-RestMethod "$apiBase/api/v1/map/regions?hours=24"
$fresh = Invoke-RestMethod "$apiBase/api/v1/system/freshness"
if ($map.regions.Count -ne 17) { throw 'Region catalog incomplete' }
if ($fresh.demo_mode -and $news.total -lt 20) { throw 'Demo data incomplete' }
if (-not $fresh.demo_mode -and $news.total -lt 1) { throw 'No live news in the selected window' }
if (-not $fresh.demo_mode -and ($news.items.title -match '^\[개발용\]')) { throw 'Demo news exposed in live mode' }
$seoul = Invoke-RestMethod "$apiBase/api/v1/news?hours=24&region=KR-11"
foreach ($article in $seoul.items) {
    if ('KR-11' -notin $article.regions.code) { throw 'Region filter returned unrelated news' }
}
if (-not $fresh.last_successful_collection_at) { throw 'No successful collection timestamp' }
$web = Invoke-WebRequest 'http://localhost:3000'
if ($web.StatusCode -ne 200 -or $web.Content -notmatch 'IssueArea') { throw 'Web smoke failed' }
Write-Output "IssueArea smoke passed: $($news.total) articles, 17 regions, $($seoul.total) Seoul articles."
