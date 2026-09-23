import { Link } from 'react-router-dom';
import Card from '../ui/Card';
import StreamFieldRenderer from '../StreamFieldRenderer';
import PageMeta from '../PageMeta';
import BlogCommentSection from './BlogCommentSection';
import { mediaUrl, API_URL } from '../../services/blogService';
import { stripHtml } from '../../utils/sanitize';
import type { BlogPost } from '@/types';

function formatDate(value?: string): string | null {
  if (!value) return null;
  // publish_date is a date-only string; bare new Date('YYYY-MM-DD') parses
  // as UTC midnight and renders the PREVIOUS day in negative-offset
  // timezones — anchor it to local midnight instead.
  const date = value.length === 10 ? new Date(`${value}T00:00:00`) : new Date(value);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

interface BlogArticleProps {
  post: BlogPost;
  /**
   * An editor's unpublished draft (the /blog/preview route): hides related
   * posts and comments, which belong to the published post.
   */
  preview?: boolean;
}

/**
 * BlogArticle — the Canopy article body shared by BlogDetailPage and
 * BlogPreview (web dead-code audit M2): eyebrow (category · date), display
 * headline, author line, cover, StreamField body at reading measure, then
 * "More from the blog" and comments for a published post.
 */
export default function BlogArticle({ post, preview = false }: BlogArticleProps) {
  const category = post.categories?.[0];
  const date = formatDate(post.publish_date);
  const authorLine = [
    post.author?.display_name && `By ${post.author.display_name}`,
    post.reading_time && `${post.reading_time} min read`,
  ]
    .filter(Boolean)
    .join(' · ');
  const related = post.related_posts ?? [];
  const coverSrc = post.featured_image?.url ? mediaUrl(post.featured_image.url) : undefined;

  return (
    <article className="flex flex-col gap-8">
      <PageMeta
        title={`${preview ? 'Preview: ' : ''}${post.title} — Houseplant MD`}
        description={post.introduction ? stripHtml(post.introduction) : undefined}
        og={{ title: post.title, type: 'article' }}
        rssFeedUrl={`${API_URL}/blog/rss/`}
        atomFeedUrl={`${API_URL}/blog/atom/`}
      />

      <header className="mx-auto flex w-full max-w-[70ch] flex-col items-start gap-3.5">
        <div className="flex flex-wrap items-center gap-3">
          {category && (
            <span className="rounded-pill border border-line bg-surface-2/60 px-2.5 py-0.5 font-mono text-micro uppercase tracking-[0.14em] text-ink-2">
              {category.name}
            </span>
          )}
          {date && <span className="font-mono text-meta text-ink-3">{date}</span>}
        </div>
        <h1 className="gt-h1 text-balance md:text-hero">{post.title}</h1>
        {authorLine && <p className="font-mono text-meta text-ink-3">{authorLine}</p>}
      </header>

      {coverSrc && (
        <Card className="mx-auto w-full max-w-[860px] overflow-hidden p-0">
          <img
            src={coverSrc}
            alt={post.featured_image?.alt || ''}
            width={post.featured_image?.width || 800}
            height={post.featured_image?.height || 400}
            className="aspect-[2/1] w-full object-cover"
          />
        </Card>
      )}

      {post.introduction && (
        <div className="mx-auto w-full max-w-[70ch]">
          <StreamFieldRenderer
            blocks={[{ type: 'paragraph', value: post.introduction }]}
            variant="article"
          />
        </div>
      )}

      {/* Anchors on the content blocks ONLY — the introduction above is a
          synthetic block and must not shift `#block-N` numbering (todo 289). */}
      <StreamFieldRenderer blocks={post.content_blocks} variant="article" anchorPrefix="block" />

      {!preview && related.length > 0 && (
        <aside className="mx-auto w-full max-w-[860px] border-t border-line pt-8">
          <h2 className="mb-4 text-lead font-semibold text-ink">More from the blog</h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {related.slice(0, 3).map((rp) => (
              <Card key={rp.id} interactive className="overflow-hidden">
                <Link
                  to={`/blog/${rp.slug}`}
                  className="group flex h-full flex-col focus:outline-none"
                >
                  {rp.featured_image && (
                    <img
                      src={mediaUrl(rp.featured_image.url)}
                      alt=""
                      aria-hidden="true"
                      className="aspect-[2/1] w-full object-cover"
                    />
                  )}
                  <span className="flex flex-1 flex-col gap-1.5 p-4">
                    <span className="text-body font-semibold leading-snug text-ink transition-colors group-hover:text-primary">
                      {rp.title}
                    </span>
                    {rp.excerpt && (
                      <span className="line-clamp-2 text-meta text-ink-2">{rp.excerpt}</span>
                    )}
                  </span>
                </Link>
              </Card>
            ))}
          </div>
        </aside>
      )}

      {/* Reader comments (todo 352). allow_comments/comment_count ride the
          v2 DETAIL payload — see fetchBlogPost. */}
      {!preview && (
        <BlogCommentSection
          postId={post.id}
          allowComments={post.allow_comments}
          commentCount={post.comment_count}
        />
      )}
    </article>
  );
}
