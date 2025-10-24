import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

/**
 * BlogPreview Component
 *
 * Renders unpublished blog posts for preview in Wagtail admin.
 * Integrates with wagtail-headless-preview to show draft content.
 *
 * URL Pattern: /blog/preview/:content_type/:token/
 *
 * The content_type and token are provided by Wagtail when clicking "Preview" in admin.
 */
export default function BlogPreview() {
  const { content_type, token } = useParams();
  const [post, setPost] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!content_type || !token) {
      setError('Missing content_type or token in URL');
      setLoading(false);
      return;
    }

    // Fetch preview content from Wagtail API
    const fetchPreview = async () => {
      try {
        setLoading(true);
        setError(null);

        const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        const previewUrl = `${API_URL}/api/v2/page_preview/1/?content_type=${content_type}&token=${token}`;

        console.log('[BlogPreview] Fetching preview:', previewUrl);

        const response = await fetch(previewUrl, {
          method: 'GET',
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
          },
          credentials: 'include', // Include cookies for authentication
        });

        if (!response.ok) {
          throw new Error(`Preview fetch failed: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        console.log('[BlogPreview] Preview data:', data);
        setPost(data);
      } catch (err) {
        console.error('[BlogPreview] Error fetching preview:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchPreview();
  }, [content_type, token]);

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mb-4"></div>
          <p className="text-gray-600">Loading preview...</p>
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
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Preview Error</h1>
          <p className="text-gray-600 mb-4">{error}</p>
          <p className="text-sm text-gray-500">
            Please try again from the Wagtail admin interface.
          </p>
        </div>
      </div>
    );
  }

  // No post data
  if (!post) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-gray-600">No preview data available</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Preview Mode Banner */}
      <div className="bg-yellow-500 text-black py-2 px-4 text-center font-semibold sticky top-0 z-50 shadow-md">
        <span className="inline-flex items-center">
          <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          PREVIEW MODE - This content is not published yet
        </span>
      </div>

      {/* Blog Post Content */}
      <div className="max-w-4xl mx-auto p-8">
        {/* Featured Image */}
        {post.featured_image && (
          <div className="mb-8 rounded-lg overflow-hidden shadow-lg">
            <img
              src={post.featured_image.thumbnail?.url || post.featured_image.url}
              alt={post.featured_image.title || post.title}
              className="w-full h-auto"
            />
          </div>
        )}

        {/* Post Metadata */}
        <div className="mb-6">
          {/* Categories */}
          {post.categories && post.categories.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-4">
              {post.categories.map((category) => (
                <span
                  key={category.id}
                  className="inline-block px-3 py-1 text-sm font-medium bg-green-100 text-green-800 rounded-full"
                >
                  {category.name}
                </span>
              ))}
            </div>
          )}

          {/* Title */}
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            {post.title}
          </h1>

          {/* Author and Date */}
          <div className="flex items-center text-gray-600 text-sm mb-4">
            {post.author && (
              <span className="mr-4">
                By {post.author.first_name} {post.author.last_name}
              </span>
            )}
            {post.publish_date && (
              <span>
                {new Date(post.publish_date).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                })}
              </span>
            )}
          </div>

          {/* Tags */}
          {post.tags && post.tags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {post.tags.map((tag, index) => (
                <span
                  key={index}
                  className="inline-block px-2 py-1 text-xs bg-gray-200 text-gray-700 rounded"
                >
                  #{tag}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Introduction */}
        {post.introduction && (
          <div
            className="text-xl text-gray-700 mb-8 leading-relaxed"
            dangerouslySetInnerHTML={{ __html: post.introduction }}
          />
        )}

        {/* StreamField Content Blocks */}
        {post.content_blocks && post.content_blocks.length > 0 && (
          <div className="prose prose-lg max-w-none">
            {post.content_blocks.map((block, index) => (
              <StreamFieldBlock key={block.id || index} block={block} />
            ))}
          </div>
        )}

        {/* Related Plant Species */}
        {post.related_plant_species && post.related_plant_species.length > 0 && (
          <div className="mt-12 p-6 bg-green-50 rounded-lg">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Related Plants</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {post.related_plant_species.map((plant) => (
                <div key={plant.id} className="p-4 bg-white rounded shadow">
                  <h3 className="font-semibold text-gray-900">{plant.common_name}</h3>
                  <p className="text-sm text-gray-600 italic">{plant.scientific_name}</p>
                  {plant.family && (
                    <p className="text-xs text-gray-500 mt-1">Family: {plant.family}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * StreamFieldBlock Component
 *
 * Renders individual StreamField blocks based on their type.
 */
function StreamFieldBlock({ block }) {
  const { type, value } = block;

  switch (type) {
    case 'heading':
      return <h2 className="text-3xl font-bold mt-8 mb-4">{value}</h2>;

    case 'paragraph':
      return (
        <div
          className="mb-4"
          dangerouslySetInnerHTML={{ __html: value }}
        />
      );

    case 'image':
      return (
        <figure className="my-8">
          {value.image && (
            <img
              src={value.image.renditions?.[0]?.url || value.image.url}
              alt={value.image.title}
              className="w-full h-auto rounded-lg shadow-md"
            />
          )}
          {value.caption && (
            <figcaption className="text-sm text-gray-600 mt-2 text-center">
              {value.caption}
            </figcaption>
          )}
        </figure>
      );

    case 'quote':
      return (
        <blockquote className="border-l-4 border-green-600 pl-6 py-4 my-8 italic text-gray-700">
          <p className="text-xl mb-2">{value.quote}</p>
          {value.attribution && (
            <footer className="text-sm text-gray-600">— {value.attribution}</footer>
          )}
        </blockquote>
      );

    case 'code':
      return (
        <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto my-6">
          <code className={`language-${value.language || 'text'}`}>
            {value.code}
          </code>
        </pre>
      );

    case 'plant_spotlight':
      return (
        <div className="my-8 p-6 bg-green-50 border-2 border-green-200 rounded-lg">
          <h3 className="text-2xl font-bold text-gray-900 mb-3">{value.heading}</h3>
          {value.image && (
            <img
              src={value.image.url}
              alt={value.heading}
              className="w-full h-64 object-cover rounded-lg mb-4"
            />
          )}
          <div dangerouslySetInnerHTML={{ __html: value.description }} />
          {value.care_level && (
            <p className="mt-4 text-sm font-semibold text-green-700">
              Care Level: {value.care_level}
            </p>
          )}
        </div>
      );

    case 'call_to_action':
      return (
        <div className="my-8 p-8 bg-gradient-to-r from-green-500 to-green-600 text-white rounded-lg text-center">
          <h3 className="text-2xl font-bold mb-2">{value.heading}</h3>
          <p className="mb-6">{value.description}</p>
          <a
            href={value.button_url}
            className="inline-block px-8 py-3 bg-white text-green-600 font-semibold rounded-lg hover:bg-gray-100 transition-colors"
          >
            {value.button_text}
          </a>
        </div>
      );

    default:
      return (
        <div className="my-4 p-4 bg-gray-100 rounded">
          <p className="text-sm text-gray-600">
            Unsupported block type: <code>{type}</code>
          </p>
        </div>
      );
  }
}
