import { useEffect, useState, useCallback, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import StreamFieldRenderer from '../components/StreamFieldRenderer';
import BlogCard from '../components/BlogCard';
import { fetchBlogPost } from '../services/blogService';
import { createSafeMarkup, SANITIZE_PRESETS } from '../utils/sanitize';
import { logger } from '../utils/logger';

/**
 * BlogDetailPage Component
 *
 * Full blog post detail page with content, metadata, and related posts.
 */
export default function BlogDetailPage() {
  const { slug } = useParams();
  const [post, setPost] = useState(null);
  const [relatedPosts, setRelatedPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  // Format date (memoized to prevent recalculation on every render)
  // Must be before early returns to comply with React Hooks rules
  const formattedDate = useMemo(() => {
    if (!post?.publish_date) return null;
    return new Date(post.publish_date).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  }, [post?.publish_date]);

  // Share button handler (memoized)
  const handleShare = useCallback(async () => {
    const url = window.location.href;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      logger.error('Failed to copy URL to clipboard', {
        component: 'BlogDetailPage',
        error: err,
        context: { url },
      });
    }
  }, []);

  useEffect(() => {
    const loadPost = async () => {
      try {
        setLoading(true);
        setError(null);

        const data = await fetchBlogPost(slug);

        // Parse content_blocks if it's a JSON string
        if (data.content_blocks && typeof data.content_blocks === 'string') {
          try {
            data.content_blocks = JSON.parse(data.content_blocks);
          } catch (e) {
            logger.error('Failed to parse content_blocks', {
              component: 'BlogDetailPage',
              error: e,
              context: { slug },
            });
            data.content_blocks = [];
          }
        }

        setPost(data);

        // Related posts are already included in the API response
        if (data.related_posts && Array.isArray(data.related_posts)) {
          setRelatedPosts(data.related_posts);
        }
      } catch (err) {
        logger.error('Error loading blog post', {
          component: 'BlogDetailPage',
          error: err,
          context: { slug },
        });
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    loadPost();
  }, [slug]);

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mb-4"></div>
          <p className="text-gray-600">Loading article...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="max-w-md text-center p-8 bg-white rounded-lg shadow-md">
          <div className="text-red-600 text-5xl mb-4">⚠️</div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Article Not Found</h1>
          <p className="text-gray-600 mb-4">{error}</p>
          <Link
            to="/blog"
            className="inline-block px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            Back to Blog
          </Link>
        </div>
      </div>
    );
  }

  // No post data
  if (!post) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-600">No article data available</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Breadcrumb */}
      <div className="bg-white border-b">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <nav className="flex items-center text-sm text-gray-600">
            <Link to="/" className="hover:text-green-600">
              Home
            </Link>
            <svg
              className="w-4 h-4 mx-2"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                clipRule="evenodd"
              />
            </svg>
            <Link to="/blog" className="hover:text-green-600">
              Blog
            </Link>
            <svg
              className="w-4 h-4 mx-2"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                clipRule="evenodd"
              />
            </svg>
            <span className="text-gray-900 truncate max-w-xs">{post.title}</span>
          </nav>
        </div>
      </div>

      {/* Article Content */}
      <article className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Featured Image */}
        {post.featured_image && (
          <div className="mb-8 rounded-lg overflow-hidden shadow-lg">
            <img
              src={post.featured_image.url}
              alt={post.featured_image.title || post.title}
              className="w-full h-auto"
            />
          </div>
        )}

        {/* Metadata Header */}
        <header className="mb-8">
          {/* Categories */}
          {post.categories && post.categories.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-4">
              {post.categories.map((category) => (
                <Link
                  key={category.id}
                  to={`/blog?category=${category.slug}`}
                  className="inline-block px-3 py-1 text-sm font-medium bg-green-100 text-green-800 rounded-full hover:bg-green-200 transition-colors"
                >
                  {category.name}
                </Link>
              ))}
            </div>
          )}

          {/* Title */}
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            {post.title}
          </h1>

          {/* Author and Date */}
          <div className="flex items-center gap-4 text-gray-600 mb-4">
            {post.author && (
              <div className="flex items-center">
                <svg
                  className="w-5 h-5 mr-2"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z"
                    clipRule="evenodd"
                  />
                </svg>
                <span>
                  {post.author.first_name} {post.author.last_name}
                </span>
              </div>
            )}

            {formattedDate && (
              <div className="flex items-center">
                <svg
                  className="w-5 h-5 mr-2"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z"
                    clipRule="evenodd"
                  />
                </svg>
                <span>{formattedDate}</span>
              </div>
            )}

            {/* View Count */}
            {post.view_count > 0 && (
              <div className="flex items-center">
                <svg
                  className="w-5 h-5 mr-2"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                  <path
                    fillRule="evenodd"
                    d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z"
                    clipRule="evenodd"
                  />
                </svg>
                <span>{post.view_count.toLocaleString()} views</span>
              </div>
            )}
          </div>

          {/* Tags */}
          {post.tags && post.tags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {post.tags.map((tag, index) => (
                <span
                  key={index}
                  className="inline-block px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded-full"
                >
                  #{tag}
                </span>
              ))}
            </div>
          )}
        </header>

        {/* Introduction */}
        {post.introduction && (
          <div className="text-xl text-gray-700 mb-8 leading-relaxed border-l-4 border-green-600 pl-6 py-2 bg-green-50 rounded-r-lg">
            <div dangerouslySetInnerHTML={createSafeMarkup(post.introduction, SANITIZE_PRESETS.STANDARD)} />
          </div>
        )}

        {/* StreamField Content */}
        {post.content_blocks && post.content_blocks.length > 0 && (
          <div className="mb-12">
            <StreamFieldRenderer blocks={post.content_blocks} />
          </div>
        )}

        {/* Related Plant Species */}
        {post.related_plant_species && post.related_plant_species.length > 0 && (
          <div className="mt-12 p-6 bg-green-50 border border-green-200 rounded-lg">
            <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center">
              <svg
                className="w-6 h-6 mr-2 text-green-600"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                  clipRule="evenodd"
                />
              </svg>
              Related Plants
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {post.related_plant_species.map((plant) => (
                <div
                  key={plant.id}
                  className="p-4 bg-white border border-green-100 rounded-lg shadow-sm hover:shadow-md transition-shadow"
                >
                  <h3 className="font-semibold text-gray-900 text-lg">
                    {plant.common_name}
                  </h3>
                  <p className="text-sm text-gray-600 italic">{plant.scientific_name}</p>
                  {plant.family && (
                    <p className="text-xs text-gray-500 mt-1">Family: {plant.family}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Share Buttons */}
        <div className="mt-12 pt-8 border-t border-gray-200">
          <h3 className="text-lg font-bold text-gray-900 mb-4">Share this article</h3>
          <div className="flex gap-3">
            <button
              onClick={handleShare}
              className={`px-4 py-2 rounded-lg transition-all flex items-center ${
                copied
                  ? 'bg-green-100 text-green-800 border-2 border-green-600'
                  : 'bg-green-600 text-white hover:bg-green-700'
              }`}
            >
              {copied ? (
                <>
                  <svg
                    className="w-5 h-5 mr-2"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                  Link Copied!
                </>
              ) : (
                <>
                  <svg
                    className="w-5 h-5 mr-2"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path d="M8 3a1 1 0 011-1h2a1 1 0 110 2H9a1 1 0 01-1-1z" />
                    <path d="M6 3a2 2 0 00-2 2v11a2 2 0 002 2h8a2 2 0 002-2V5a2 2 0 00-2-2 3 3 0 01-3 3H9a3 3 0 01-3-3z" />
                  </svg>
                  Copy Link
                </>
              )}
            </button>
          </div>
        </div>
      </article>

      {/* Related Posts */}
      {relatedPosts.length > 0 && (
        <div className="bg-gray-100 py-12">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <h2 className="text-3xl font-bold text-gray-900 mb-8">Related Articles</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {relatedPosts.map((relatedPost) => (
                <BlogCard key={relatedPost.id} post={relatedPost} />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Back to Blog Link */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Link
          to="/blog"
          className="inline-flex items-center text-green-600 hover:text-green-700 font-medium"
        >
          <svg
            className="w-5 h-5 mr-2"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z"
              clipRule="evenodd"
            />
          </svg>
          Back to Blog
        </Link>
      </div>
    </div>
  );
}
