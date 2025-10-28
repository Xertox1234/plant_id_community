import { Link } from 'react-router-dom';
import { useMemo, memo } from 'react';
import PropTypes from 'prop-types';
import { stripHtml } from '../utils/sanitize';

/**
 * BlogCard Component
 *
 * Displays a blog post preview card with image, title, excerpt, and metadata.
 * Used in blog list pages and related posts sections.
 * Memoized to prevent unnecessary re-renders when parent component updates.
 */
function BlogCard({ post, showImage = true, compact = false }) {
  const {
    slug,
    title,
    introduction,
    featured_image,
    author,
    publish_date,
    categories = [],
    view_count = 0,
  } = post;

  // Format date (memoized to prevent recalculation on every render)
  const formattedDate = useMemo(() => {
    if (!publish_date) return null;
    return new Date(publish_date).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  }, [publish_date]);

  // Get first category (memoized)
  const primaryCategory = useMemo(() => categories[0], [categories]);

  // Truncate introduction for preview (memoized)
  // Use centralized stripHtml instead of manual regex
  const excerpt = useMemo(() => {
    if (!introduction) return '';
    const plainText = stripHtml(introduction);
    return plainText.substring(0, compact ? 100 : 200) + '...';
  }, [introduction, compact]);

  return (
    <Link
      to={`/blog/${slug}`}
      className="group block bg-white rounded-lg shadow-md hover:shadow-xl transition-shadow duration-300 overflow-hidden"
    >
      {/* Featured Image */}
      {showImage && featured_image && (
        <div className="relative h-48 overflow-hidden bg-gray-200">
          <img
            src={featured_image.thumbnail?.url || featured_image.url}
            alt={featured_image.title || title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          />
          {primaryCategory && (
            <span className="absolute top-4 left-4 px-3 py-1 bg-green-600 text-white text-sm font-medium rounded-full shadow">
              {primaryCategory.name}
            </span>
          )}
        </div>
      )}

      {/* Content */}
      <div className={`p-${compact ? '4' : '6'}`}>
        {/* Title */}
        <h3
          className={`${
            compact ? 'text-lg' : 'text-2xl'
          } font-bold text-gray-900 mb-2 group-hover:text-green-600 transition-colors line-clamp-2`}
        >
          {title}
        </h3>

        {/* Excerpt */}
        {!compact && excerpt && (
          <p className="text-gray-600 mb-4 line-clamp-3">{excerpt}</p>
        )}

        {/* Metadata */}
        <div className="flex items-center justify-between text-sm text-gray-500">
          <div className="flex items-center gap-4">
            {/* Author */}
            {author && (
              <span className="flex items-center">
                <svg
                  className="w-4 h-4 mr-1"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z"
                    clipRule="evenodd"
                  />
                </svg>
                {author.first_name} {author.last_name}
              </span>
            )}

            {/* Date */}
            {formattedDate && (
              <span className="flex items-center">
                <svg
                  className="w-4 h-4 mr-1"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z"
                    clipRule="evenodd"
                  />
                </svg>
                {formattedDate}
              </span>
            )}
          </div>

          {/* View Count */}
          {view_count > 0 && (
            <span className="flex items-center text-gray-400">
              <svg
                className="w-4 h-4 mr-1"
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
              {view_count.toLocaleString()}
            </span>
          )}
        </div>

        {/* Tags (compact mode only) */}
        {compact && post.tags && post.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-3">
            {post.tags.slice(0, 3).map((tag, index) => (
              <span
                key={index}
                className="inline-block px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded"
              >
                #{tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </Link>
  );
}

BlogCard.propTypes = {
  post: PropTypes.shape({
    slug: PropTypes.string.isRequired,
    title: PropTypes.string.isRequired,
    introduction: PropTypes.string,
    featured_image: PropTypes.shape({
      url: PropTypes.string,
      thumbnail: PropTypes.shape({
        url: PropTypes.string,
      }),
      title: PropTypes.string,
    }),
    author: PropTypes.shape({
      first_name: PropTypes.string,
      last_name: PropTypes.string,
    }),
    publish_date: PropTypes.string,
    categories: PropTypes.arrayOf(
      PropTypes.shape({
        name: PropTypes.string,
      })
    ),
    tags: PropTypes.arrayOf(PropTypes.string),
    view_count: PropTypes.number,
  }).isRequired,
  showImage: PropTypes.bool,
  compact: PropTypes.bool,
};

// Export memoized component to prevent re-renders when props don't change
export default memo(BlogCard);
