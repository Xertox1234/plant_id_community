import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen } from 'lucide-react';
import RailModule from '../../ui/RailModule';
import { fetchPopularPosts } from '../../../services/blogService';
import { logger } from '../../../utils/logger';
import type { BlogPost } from '../../../types/blog';

const RAIL_POST_LIMIT = 3;

/**
 * Right-rail module: the most-read blog posts (spec §4 "From the blog").
 * Self-hides while loading, on error, and when the blog is empty — the rail
 * never shows a spinner or a fake placeholder.
 */
export default function FromTheBlogModule() {
  const [posts, setPosts] = useState<BlogPost[]>([]);

  useEffect(() => {
    let ignore = false;
    fetchPopularPosts({ limit: RAIL_POST_LIMIT })
      .then((items) => {
        if (!ignore) setPosts(items);
      })
      .catch((err) => {
        logger.error('Error loading rail blog posts', {
          component: 'FromTheBlogModule',
          error: err,
        });
      });
    return () => {
      ignore = true;
    };
  }, []);

  if (posts.length === 0) return null;

  return (
    <RailModule icon={<BookOpen aria-hidden="true" />} title="From the blog">
      <ul className="flex flex-col gap-3">
        {posts.map((post) => (
          <li key={post.id}>
            <Link to={`/blog/${post.meta?.slug ?? post.slug}`} className="group block">
              <span className="text-[13px] font-medium text-ink transition-colors group-hover:text-primary">
                {post.title}
              </span>
              {post.introduction && (
                <span className="mt-0.5 line-clamp-2 block text-[12px] text-ink-3">
                  {post.introduction}
                </span>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </RailModule>
  );
}
