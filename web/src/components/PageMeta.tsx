/**
 * PageMeta — per-route document metadata (todo 256 H9).
 *
 * Renders `<title>` / `<meta>` inline; React 19 natively hoists these to
 * `<head>`, so each route gets a descriptive title + description (in-app UX +
 * JS-capable crawlers like Googlebot). OG tags are opt-in for shareable pages
 * (e.g. topic detail). Note: non-JS unfurlers (Slack/Twitter/Facebook) do not
 * execute the SPA, so they won't see these — an accepted tradeoff for the
 * cheap, no-prerender path (see the sitemap/RSS for crawl discovery).
 */
interface OpenGraph {
  title?: string;
  description?: string;
  url?: string;
  type?: string;
}

interface PageMetaProps {
  title: string;
  description?: string;
  og?: OpenGraph;
  /** Absolute feed URLs — caller resolves the API origin (e.g. blogService's API_URL). */
  rssFeedUrl?: string;
  atomFeedUrl?: string;
}

export default function PageMeta({
  title,
  description,
  og,
  rssFeedUrl,
  atomFeedUrl,
}: PageMetaProps) {
  return (
    <>
      <title>{title}</title>
      {description && <meta name="description" content={description} />}
      {rssFeedUrl && (
        <link rel="alternate" type="application/rss+xml" title={`${title} RSS`} href={rssFeedUrl} />
      )}
      {atomFeedUrl && (
        <link
          rel="alternate"
          type="application/atom+xml"
          title={`${title} Atom`}
          href={atomFeedUrl}
        />
      )}
      {og && (
        <>
          {og.title && <meta property="og:title" content={og.title} />}
          {og.description && <meta property="og:description" content={og.description} />}
          {og.url && <meta property="og:url" content={og.url} />}
          <meta property="og:type" content={og.type || 'article'} />
        </>
      )}
    </>
  );
}
