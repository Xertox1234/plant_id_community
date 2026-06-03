import { useState, useEffect, useCallback, FormEvent } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  fetchThread,
  fetchPosts,
  createPost,
  deletePost,
  toggleReaction,
} from '../../services/forumService';
import { parseLeadingId } from '../../utils/forumUrls';
import { useAuth } from '../../contexts/AuthContext';
import PostCard from '../../components/forum/PostCard';
import TipTapEditor from '../../components/forum/TipTapEditor';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import Button from '../../components/ui/Button';
import { logger } from '../../utils/logger';
import type { Thread, Post } from '@/types';

interface PostsData {
  items: Post[];
  meta: {
    count: number;
  };
}

/**
 * ThreadDetailPage Component
 *
 * Displays a thread with its posts and allows replying.
 * Route: /forum/:categorySlug/:threadSlug
 */
export default function ThreadDetailPage() {
  const { categorySlug, threadSlug } = useParams<{ categorySlug: string; threadSlug: string }>();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  // The route param is a hybrid "id-slug"; lookups use the leading topic id.
  const topicId = parseLeadingId(threadSlug);

  const [thread, setThread] = useState<Thread | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // Reaction failures are shown inline; they must not clobber the whole-page
  // `error` state, which unmounts the thread view.
  const [reactionError, setReactionError] = useState<string | null>(null);

  // Pagination state
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPosts, setTotalPosts] = useState<number>(0);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);

  // Reply form state
  const [replyContent, setReplyContent] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [replyError, setReplyError] = useState<string | null>(null);

  // Load thread and initial posts
  useEffect(() => {
    const loadData = async () => {
      if (topicId == null) {
        setError('Invalid thread URL');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        const [threadData, postsData] = (await Promise.all([
          fetchThread(topicId),
          fetchPosts({ thread: topicId, page: 1 }),
        ])) as [Thread, PostsData];

        setThread(threadData);
        setPosts(postsData.items);
        setTotalPosts(postsData.meta.count);
        setCurrentPage(1);
      } catch (err) {
        logger.error('Error loading thread data', {
          component: 'ThreadDetailPage',
          error: err,
          context: { categorySlug, threadSlug },
        });
        setError(err instanceof Error ? err.message : 'Failed to load thread');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [topicId, threadSlug, categorySlug]);

  // Handle reply submission
  const handleReplySubmit = useCallback(
    async (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();

      if (!isAuthenticated) {
        navigate('/login', { state: { from: window.location.pathname } });
        return;
      }

      if (!replyContent.trim()) {
        setReplyError('Reply content is required');
        return;
      }

      if (!thread || topicId == null) {
        setReplyError('Thread not found');
        return;
      }

      try {
        setIsSubmitting(true);
        setReplyError(null);

        const newPost = (await createPost({
          thread: topicId,
          content_raw: replyContent,
          content_format: 'html', // TipTap outputs HTML
        })) as Post;

        setPosts((prev) => [...prev, newPost]);
        setTotalPosts((prev) => prev + 1);
        setReplyContent(''); // Clear editor

        // Scroll to new post
        setTimeout(() => {
          const element = document.getElementById(`post-${newPost.id}`);
          element?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
      } catch (err) {
        logger.error('Error creating post', {
          component: 'ThreadDetailPage',
          error: err,
          context: { threadId: thread?.id, contentLength: replyContent?.length },
        });
        setReplyError(err instanceof Error ? err.message : 'Failed to create post');
      } finally {
        setIsSubmitting(false);
      }
    },
    [isAuthenticated, navigate, replyContent, thread, topicId]
  );

  // Handle post deletion
  const handleDeletePost = useCallback(async (post: Post) => {
    if (!window.confirm('Are you sure you want to delete this post?')) {
      return;
    }

    try {
      await deletePost(post.id);
      setPosts((prev) => prev.filter((p) => p.id !== post.id));
      setTotalPosts((prev) => prev - 1);
    } catch (err) {
      logger.error('Error deleting post', {
        component: 'ThreadDetailPage',
        error: err,
        context: { postId: post.id },
      });
      alert(`Failed to delete post: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  }, []);

  // Toggle a reaction on a post and reflect the new counts in place.
  const handleReact = useCallback(
    async (postId: string, reactionType: string) => {
      if (!isAuthenticated) {
        navigate('/login', { state: { from: window.location.pathname } });
        return;
      }

      setReactionError(null);
      try {
        const result = await toggleReaction(postId, reactionType);
        setPosts((prev) =>
          prev.map((p) => (p.id === postId ? { ...p, reaction_counts: result.reaction_counts } : p))
        );
      } catch (err) {
        setReactionError(err instanceof Error ? err.message : 'Could not react');
      }
    },
    [isAuthenticated, navigate]
  );

  // Load more posts (pagination)
  const handleLoadMore = useCallback(async () => {
    if (topicId == null) return;

    try {
      setLoadingMore(true);
      const nextPage = currentPage + 1;

      const postsData = (await fetchPosts({
        thread: topicId,
        page: nextPage,
      })) as PostsData;

      setPosts((prev) => [...prev, ...postsData.items]);
      setCurrentPage(nextPage);
    } catch (err) {
      logger.error('Error loading more posts', {
        component: 'ThreadDetailPage',
        error: err,
        context: { threadId: thread?.id, page: currentPage + 1 },
      });
      alert(`Failed to load more posts: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setLoadingMore(false);
    }
  }, [currentPage, topicId, thread?.id]);

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <LoadingSpinner />
      </div>
    );
  }

  if (error || !thread) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-error/10 border border-error/30 text-ink px-4 py-3 rounded">
          <strong>Error:</strong> {error || 'Thread not found'}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6 text-sm text-ink-2" aria-label="Breadcrumb">
        <ol className="flex items-center gap-2">
          <li>
            <Link to="/forum" className="hover:text-primary">
              Forums
            </Link>
          </li>
          <li aria-hidden="true">›</li>
          <li>
            <Link to={`/forum/${categorySlug}`} className="hover:text-primary">
              {thread.category.name}
            </Link>
          </li>
          <li aria-hidden="true">›</li>
          <li aria-current="page" className="font-medium text-ink">
            {thread.title}
          </li>
        </ol>
      </nav>

      {/* Thread Header */}
      <div className="mb-8 bg-surface-2 rounded-lg shadow-md p-6">
        <div className="flex items-start flex-wrap gap-4 mb-4">
          {thread.category.icon && (
            <span className="text-4xl" aria-hidden="true">
              {thread.category.icon}
            </span>
          )}

          <div className="flex-1 min-w-0">
            <h1 className="text-xl sm:text-3xl font-bold text-ink mb-2">{thread.title}</h1>

            <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-sm text-ink-3">
              <span>
                by{' '}
                <strong className="text-ink-2">
                  {thread.author.display_name || thread.author.username}
                </strong>
              </span>
              <span>•</span>
              <span>💬 {totalPosts} replies</span>
              <span>•</span>
              <span>👁️ {thread.view_count} views</span>
            </div>
          </div>

          {/* Badges */}
          <div className="flex gap-2">
            {thread.is_pinned && (
              <span className="px-3 py-1 bg-tertiary/20 text-ink text-sm font-semibold rounded">
                📌 Pinned
              </span>
            )}
            {thread.is_locked && (
              <span className="px-3 py-1 bg-surface-3 text-ink-2 text-sm font-semibold rounded">
                🔒 Locked
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Inline reaction error — never replaces the page */}
      {reactionError && (
        <div className="mb-4 flex items-center justify-between bg-error/10 border border-error/30 text-ink px-4 py-3 rounded">
          <span>{reactionError}</span>
          <button
            type="button"
            onClick={() => setReactionError(null)}
            className="text-sm text-error hover:text-error/80 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Posts List */}
      <div className="space-y-4 mb-8">
        {posts.map((post) => (
          <div key={post.id} id={`post-${post.id}`}>
            <PostCard post={post} onDelete={handleDeletePost} onReact={handleReact} />
          </div>
        ))}
      </div>

      {/* Load More Button */}
      {posts.length < totalPosts && (
        <div className="mb-8 text-center">
          <Button
            onClick={handleLoadMore}
            variant="outline"
            loading={loadingMore}
            disabled={loadingMore}
            className="min-h-11"
          >
            {loadingMore
              ? 'Loading...'
              : `Load More Posts (${totalPosts - posts.length} remaining)`}
          </Button>
        </div>
      )}

      {/* Reply Form */}
      {!thread.is_locked && (
        <div className="bg-surface-2 rounded-lg shadow-md p-6">
          <h3 className="text-xl font-bold mb-4 text-ink">Post Your Reply</h3>

          {!isAuthenticated ? (
            <div className="text-center py-8">
              <p className="text-ink-2 mb-4">You must be logged in to reply to this thread.</p>
              <Link to="/login" state={{ from: window.location.pathname }}>
                <Button variant="primary">Log In</Button>
              </Link>
            </div>
          ) : (
            <form onSubmit={handleReplySubmit}>
              <TipTapEditor
                content={replyContent}
                onChange={setReplyContent}
                placeholder="Write your reply..."
                className="mb-4"
              />

              {replyError && (
                <div className="mb-4 p-3 bg-error/10 text-ink rounded">{replyError}</div>
              )}

              <div className="flex gap-2">
                <Button
                  type="submit"
                  variant="primary"
                  loading={isSubmitting}
                  disabled={!replyContent.trim()}
                >
                  {isSubmitting ? 'Posting...' : 'Post Reply'}
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setReplyContent('')}
                  disabled={isSubmitting}
                >
                  Clear
                </Button>
              </div>
            </form>
          )}
        </div>
      )}

      {thread.is_locked && (
        <div className="bg-surface-2 border border-line-2 text-ink-2 px-6 py-4 rounded-lg text-center">
          🔒 This thread is locked. No new replies can be posted.
        </div>
      )}
    </div>
  );
}
