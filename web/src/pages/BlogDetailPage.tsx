import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Card from '../components/ui/Card';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import StreamFieldRenderer from '../components/StreamFieldRenderer';
import PageMeta from '../components/PageMeta';
import NotFoundPage from './NotFoundPage';
import { fetchBlogPost, mediaUrl } from '../services/blogService';
import { stripHtml } from '../utils/sanitize';
import { logger } from '../utils/logger';
import { useScrollToTop } from '../hooks/useScrollToTop';
import type { BlogPost } from '@/types';

/**
 * BlogDetailPage — Canopy blog article (PR 3, spec §8).
 *
 * Eyebrow (category · date) → display headline → author line → cover →
 * StreamField body at reading measure → "More from the blog" strip from the
 * server-computed related_posts. Rail deliberately empty: the RailSlot is
 * unused, so the shell widens the reading column (spec §9).
 */

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

export default function BlogDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  useScrollToTop();
  const [post, setPost] = useState<BlogPost | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    let cancelled = false;
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        setNotFound(false);
        const data = await fetchBlogPost(slug);
        if (!cancelled) setPost(data);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof Error && /not found/i.test(err.message)) {
          setNotFound(true);
        } else {
          logger.error('Error loading blog post', {
            component: 'BlogDetailPage',
            error: err,
            context: { slug },
          });
          setError(err instanceof Error ? err.message : 'Failed to load this article');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (notFound) return <NotFoundPage />;

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !post) {
    return (
      <div className="mx-auto max-w-[70ch] rounded-md border border-error/30 bg-error/10 p-6 text-center text-[13.5px] text-error">
        Couldn’t load this article{error ? ` — ${error}` : ''}
      </div>
    );
  }

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
        title={`${post.title} — Houseplant MD`}
        description={post.introduction ? stripHtml(post.introduction) : undefined}
        og={{ title: post.title, type: 'article' }}
      />

      <header className="mx-auto flex w-full max-w-[70ch] flex-col items-start gap-3.5">
        <div className="flex flex-wrap items-center gap-3">
          {category && (
            <span className="rounded-pill border border-line bg-surface-2/60 px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-2">
              {category.name}
            </span>
          )}
          {date && <span className="font-mono text-[12px] text-ink-3">{date}</span>}
        </div>
        <h1 className="gt-h1 text-balance md:text-[38px]">{post.title}</h1>
        {authorLine && <p className="font-mono text-[12.5px] text-ink-3">{authorLine}</p>}
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

      <StreamFieldRenderer blocks={post.content_blocks} variant="article" />

      {related.length > 0 && (
        <aside className="mx-auto w-full max-w-[860px] border-t border-line pt-8">
          <h2 className="mb-4 text-[17px] font-semibold text-ink">More from the blog</h2>
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
                    <span className="text-[14px] font-semibold leading-snug text-ink transition-colors group-hover:text-primary">
                      {rp.title}
                    </span>
                    {rp.excerpt && (
                      <span className="line-clamp-2 text-[12.5px] text-ink-2">{rp.excerpt}</span>
                    )}
                  </span>
                </Link>
              </Card>
            ))}
          </div>
        </aside>
      )}
    </article>
  );
}
