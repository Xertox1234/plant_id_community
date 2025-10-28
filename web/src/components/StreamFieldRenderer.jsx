import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { createSafeMarkup } from '../utils/domSanitizer';

/**
 * SafeHTML Component
 *
 * Wrapper component that handles async HTML sanitization with DOMPurify.
 * DOMPurify is dynamically imported to reduce initial bundle size.
 */
function SafeHTML({ html, className = '' }) {
  const [safeMarkup, setSafeMarkup] = useState(null);

  useEffect(() => {
    let isMounted = true;

    createSafeMarkup(html).then((markup) => {
      if (isMounted) {
        setSafeMarkup(markup);
      }
    });

    return () => {
      isMounted = false;
    };
  }, [html]);

  if (!safeMarkup) {
    return <div className={className}>Loading...</div>;
  }

  return <div className={className} dangerouslySetInnerHTML={safeMarkup} />;
}

SafeHTML.propTypes = {
  html: PropTypes.string.isRequired,
  className: PropTypes.string,
};

/**
 * StreamFieldRenderer Component
 *
 * Renders Wagtail StreamField blocks based on their type.
 * Supports all standard blog content blocks.
 */
export default function StreamFieldRenderer({ blocks }) {
  if (!blocks || blocks.length === 0) {
    return null;
  }

  return (
    <div className="prose prose-lg max-w-none">
      {blocks.map((block, index) => (
        <StreamFieldBlock key={block.id || index} block={block} />
      ))}
    </div>
  );
}

StreamFieldRenderer.propTypes = {
  blocks: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string,
      type: PropTypes.string.isRequired,
      value: PropTypes.any.isRequired,
    })
  ).isRequired,
};

/**
 * StreamFieldBlock Component
 *
 * Renders individual StreamField blocks based on their type.
 */
function StreamFieldBlock({ block }) {
  const { type, value } = block;

  switch (type) {
    case 'heading':
      return <h2 className="text-3xl font-bold mt-8 mb-4 text-gray-900">{value}</h2>;

    case 'paragraph':
      return <SafeHTML html={value} className="mb-4 text-gray-700 leading-relaxed" />;

    // Removed: image block (no backend definition, use paragraph with embedded images)

    case 'quote': {
      // Handle both possible quote structures
      const quoteText = typeof value === 'string' ? value : (value.quote || value.quote_text || '');
      const attribution = typeof value === 'object' ? value.attribution : null;

      return (
        <blockquote className="border-l-4 border-green-600 pl-6 py-4 my-8 italic text-gray-700 bg-gray-50 rounded-r-lg">
          {quoteText && <p className="text-xl mb-2">{quoteText}</p>}
          {attribution && (
            <footer className="text-sm text-gray-600 not-italic">
              — {attribution}
            </footer>
          )}
        </blockquote>
      );
    }

    case 'code':
      return (
        <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto my-6 shadow-inner">
          <code className={`language-${value.language || 'text'}`}>
            {value.code}
          </code>
        </pre>
      );

    case 'plant_spotlight':
      return (
        <div className="my-8 p-6 bg-green-50 border-2 border-green-200 rounded-lg shadow-sm">
          <h3 className="text-2xl font-bold text-gray-900 mb-3">
            🌿 {value.heading}
          </h3>
          {value.image && (
            <img
              src={value.image.url}
              alt={value.heading}
              className="w-full h-64 object-cover rounded-lg mb-4 shadow-md"
            />
          )}
          <SafeHTML html={value.description} className="text-gray-700 mb-4" />
          {value.care_level && (
            <p className="mt-4 text-sm font-semibold text-green-700 flex items-center">
              <svg
                className="w-5 h-5 mr-2"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
              Care Level: {value.care_level}
            </p>
          )}
        </div>
      );

    case 'call_to_action':
      return (
        <div className="my-8 p-8 bg-gradient-to-r from-green-500 to-green-600 text-white rounded-lg text-center shadow-lg">
          <h3 className="text-2xl font-bold mb-2">{value.heading}</h3>
          <p className="mb-6 text-green-50">{value.description}</p>
          <a
            href={value.button_url}
            className="inline-block px-8 py-3 bg-white text-green-600 font-semibold rounded-lg hover:bg-gray-100 transition-colors shadow-md"
          >
            {value.button_text}
          </a>
        </div>
      );

    // Removed: list and embed blocks (no backend definitions)

    default:
      return (
        <div className="my-4 p-4 bg-yellow-50 border border-yellow-200 rounded text-sm text-gray-600">
          <p className="font-semibold text-yellow-800 mb-1">
            Unsupported block type
          </p>
          <code className="text-xs">{type}</code>
        </div>
      );
  }
}

StreamFieldBlock.propTypes = {
  block: PropTypes.shape({
    type: PropTypes.string.isRequired,
    value: PropTypes.any.isRequired,
    id: PropTypes.string,
  }).isRequired,
};
