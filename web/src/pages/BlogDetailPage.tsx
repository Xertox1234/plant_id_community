import { useEffect, useState } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import BlogArticle from '../components/blog/BlogArticle';
import NotFoundPage from './NotFoundPage';
import { fetchBlogPost } from '../services/blogService';
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

export default function BlogDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const { hash } = useLocation();
  useScrollToTop();
  const [post, setPost] = useState<BlogPost | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // A citation deep link (`#block-N`, todo 289) arrives before the article
  // has rendered, so the browser's own hash jump finds nothing; scroll once
  // the post is in the DOM. useScrollToTop already yields to a hash.
  useEffect(() => {
    if (!post || !hash) return;
    document.getElementById(hash.slice(1))?.scrollIntoView({ block: 'start' });
  }, [post, hash]);

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
      <div className="mx-auto max-w-[70ch] rounded-md border border-error/30 bg-error/10 p-6 text-center text-body-sm text-error">
        Couldn’t load this article{error ? ` — ${error}` : ''}
      </div>
    );
  }

  return <BlogArticle post={post} />;
}
