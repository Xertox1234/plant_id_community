/**
 * Blog Preview Page
 *
 * Preview unpublished blog posts via secure token.
 * TODO: Implement full functionality
 */

import { useParams } from 'react-router-dom';

export default function BlogPreview() {
  const { content_type, token } = useParams<{ content_type: string; token: string }>();

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-4">Blog Preview</h1>
      <p className="text-gray-600">
        Preview for {content_type} (token: {token?.substring(0, 8)}...)
      </p>
      <p className="text-gray-500 mt-2">Blog preview implementation coming soon.</p>
    </div>
  );
}
