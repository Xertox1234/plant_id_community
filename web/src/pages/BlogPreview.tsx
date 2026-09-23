import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import BlogArticle from '../components/blog/BlogArticle';
import { fetchBlogPreview } from '../services/blogService';
import type { BlogPost } from '@/types';

/**
 * BlogPreview: an editor's unpublished blog draft (web dead-code audit M2).
 *
 * Wagtail's Preview button opens
 * `/blog/preview?content_type=blog.blogpostpage&token=<signed>`.
 * wagtail-headless-preview 0.9 appends QUERY parameters; the old path-param
 * route never matched, and this page only said "coming soon". The draft
 * renders through the same BlogArticle as a published post.
 */
export default function BlogPreview() {
  const [searchParams] = useSearchParams();
  const contentType = searchParams.get('content_type') ?? '';
  const token = searchParams.get('token') ?? '';
  const [post, setPost] = useState<BlogPost | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!contentType || !token) return;
    let cancelled = false;
    setPost(null);
    setError(null);
    fetchBlogPreview(contentType, token)
      .then((draft) => {
        if (!cancelled) setPost(draft);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Could not load this preview');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [contentType, token]);

  const problem =
    !contentType || !token
      ? 'This preview link is incomplete. Open Preview from the CMS again.'
      : error;

  if (problem) {
    return (
      <div
        role="alert"
        className="mx-auto max-w-[70ch] rounded-md border border-error/30 bg-error/10 p-6 text-center text-body-sm text-error"
      >
        {problem}
      </div>
    );
  }

  if (!post) {
    return (
      <div className="flex justify-center py-24">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <p
        role="status"
        className="mx-auto w-full max-w-[70ch] rounded-md border border-line bg-surface-2 px-4 py-2 text-center text-meta text-ink-2"
      >
        Preview: this draft is not published.
      </p>
      <BlogArticle post={post} preview />
    </div>
  );
}
