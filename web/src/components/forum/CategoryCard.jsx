import { memo } from 'react';
import { Link } from 'react-router';
import PropTypes from 'prop-types';

/**
 * CategoryCard Component
 *
 * Displays a forum category with stats and subcategories.
 * Used in category list view.
 */
function CategoryCard({ category }) {
  const hasChildren = category.children && category.children.length > 0;

  return (
    <div className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow">
      <Link
        to={`/forum/${category.slug}`}
        className="block p-6"
      >
        {/* Category Header */}
        <div className="flex items-start gap-4">
          {/* Icon */}
          {category.icon && (
            <div className="text-4xl" aria-hidden="true">
              {category.icon}
            </div>
          )}

          {/* Category Info */}
          <div className="flex-1">
            <h3 className="text-xl font-bold text-gray-900 hover:text-green-600 transition-colors">
              {category.name}
            </h3>

            {category.description && (
              <p className="text-gray-600 mt-1">
                {category.description}
              </p>
            )}

            {/* Stats */}
            <div className="flex gap-4 mt-3 text-sm text-gray-500">
              <span>
                <strong className="text-gray-700">{category.thread_count || 0}</strong> threads
              </span>
              <span>•</span>
              <span>
                <strong className="text-gray-700">{category.post_count || 0}</strong> posts
              </span>
            </div>
          </div>
        </div>

        {/* Subcategories (if any) */}
        {hasChildren && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="flex flex-wrap gap-2">
              <span className="text-sm text-gray-500">Subcategories:</span>
              {category.children.map(child => (
                <Link
                  key={child.id}
                  to={`/forum/${child.slug}`}
                  className="px-3 py-1 bg-gray-100 hover:bg-gray-200 text-sm text-gray-700 rounded-full transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  {child.icon && <span className="mr-1">{child.icon}</span>}
                  {child.name}
                </Link>
              ))}
            </div>
          </div>
        )}
      </Link>
    </div>
  );
}

CategoryCard.propTypes = {
  category: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    slug: PropTypes.string.isRequired,
    description: PropTypes.string,
    icon: PropTypes.string,
    thread_count: PropTypes.number,
    post_count: PropTypes.number,
    children: PropTypes.arrayOf(
      PropTypes.shape({
        id: PropTypes.string.isRequired,
        name: PropTypes.string.isRequired,
        slug: PropTypes.string.isRequired,
        icon: PropTypes.string,
      })
    ),
  }).isRequired,
};

export default memo(CategoryCard);
