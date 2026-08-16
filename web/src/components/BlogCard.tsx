import { memo } from 'react';
import { Link } from 'react-router-dom';
import Card from './ui/Card';
import { stripHtml } from '../utils/sanitize';
import { mediaUrl } from '../services/blogService';
import type { BlogPost } from '@/types';

/**
 * BlogCard — Canopy blog post card (PR 3).
 *
 * Grid variant: cover (fill-800x400 rendition), category label, title,
 * excerpt, and the artifact's meta line ("N min read · Author").
 * Compact variant: thumb + title + meta, for rail modules.
 *
 * Card `interactive` + a DIRECT child <Link> is load-bearing: the row focus
 * outline rides `.canopy-interactive:has(> a:focus-visible)` (PR 2).
 */

interface BlogCardProps {
  post: BlogPost;
  compact?: boolean;
}

function metaLine(post: BlogPost): string {
  const parts: string[] = [];
  if (post.reading_time) parts.push(`${post.reading_time} min read`);
  if (post.author?.display_name) parts.push(post.author.display_name);
  return parts.join(' · ');
}

function excerptText(post: BlogPost): string {
  if (post.excerpt) return post.excerpt;
  if (post.introduction) return stripHtml(post.introduction);
  return '';
}

function BlogCard({ post, compact = false }: BlogCardProps) {
  const meta = metaLine(post);

  if (compact) {
    const thumb = post.featured_image_thumb?.url ?? post.featured_image?.url;
    return (
      <Link
        to={`/blog/${post.slug}`}
        className="group flex items-center gap-3 rounded-sm p-1.5 transition-colors hover:bg-surface-2/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-secondary"
      >
        {thumb && (
          <img
            src={mediaUrl(thumb)}
            alt=""
            aria-hidden="true"
            width={48}
            height={48}
            className="h-12 w-12 shrink-0 rounded-sm object-cover"
          />
        )}
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className="truncate text-[13px] font-medium text-ink transition-colors group-hover:text-primary">
            {post.title}
          </span>
          {meta && <span className="font-mono text-[11px] text-ink-3">{meta}</span>}
        </span>
      </Link>
    );
  }

  const cover = post.featured_image?.url ?? post.featured_image_thumb?.url;
  const category = post.categories?.[0];
  const excerpt = excerptText(post);

  return (
    <Card interactive className="overflow-hidden">
      <Link to={`/blog/${post.slug}`} className="group flex h-full flex-col focus:outline-none">
        {cover && (
          <img
            src={mediaUrl(cover)}
            alt=""
            aria-hidden="true"
            width={800}
            height={400}
            className="aspect-[2/1] w-full object-cover"
          />
        )}
        <span className="flex flex-1 flex-col gap-2.5 p-5">
          {category && (
            <span className="self-start rounded-pill border border-line bg-surface-2/60 px-2.5 py-0.5 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-2">
              {category.name}
            </span>
          )}
          <span className="text-[17px] font-semibold leading-snug text-ink transition-colors group-hover:text-primary">
            {post.title}
          </span>
          {excerpt && (
            <span className="line-clamp-2 text-[13.5px] leading-relaxed text-ink-2">{excerpt}</span>
          )}
          {meta && <span className="mt-auto pt-1 font-mono text-[11.5px] text-ink-3">{meta}</span>}
        </span>
      </Link>
    </Card>
  );
}

export default memo(BlogCard);
