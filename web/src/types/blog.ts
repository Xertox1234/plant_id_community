/**
 * Blog & Wagtail CMS Types
 */

/**
 * StreamField block types
 */
export type StreamFieldBlock =
  | ParagraphBlock
  | HeadingBlock
  | ImageBlock
  | QuoteBlock
  | CodeBlock
  | ListBlock;

/**
 * Paragraph block
 */
export interface ParagraphBlock {
  type: 'paragraph';
  value: string;
  id: string;
}

/**
 * Heading block
 */
export interface HeadingBlock {
  type: 'heading';
  value: {
    text: string;
    level: 1 | 2 | 3 | 4 | 5 | 6;
  };
  id: string;
}

/**
 * Image block
 */
export interface ImageBlock {
  type: 'image';
  value: {
    image: string;
    alt_text?: string;
    caption?: string;
  };
  id: string;
}

/**
 * Quote block
 */
export interface QuoteBlock {
  type: 'quote';
  value: {
    text: string;
    attribution?: string;
  };
  id: string;
}

/**
 * Code block
 */
export interface CodeBlock {
  type: 'code';
  value: {
    code: string;
    language: string;
  };
  id: string;
}

/**
 * List block
 */
export interface ListBlock {
  type: 'list';
  value: {
    items: string[];
    list_type: 'ul' | 'ol';
  };
  id: string;
}

/**
 * Blog post (Wagtail page)
 */
export interface BlogPost {
  id: number;
  meta: {
    type: string;
    detail_url: string;
    html_url: string;
    slug: string;
    first_published_at: string;
  };
  title: string;
  introduction: string;
  content_blocks: StreamFieldBlock[];
  featured_image?: string;
  published_date: string;
  author?: string;
  tags?: string[];
  related_posts?: BlogPost[];
  view_count?: number;
}

/**
 * Blog post list response
 */
export interface BlogPostListResponse {
  items: BlogPost[];
  meta: {
    total_count: number;
  };
}

/**
 * Blog category
 */
export interface BlogCategory {
  id: number;
  name: string;
  slug: string;
  description?: string;
}

/**
 * Blog category list response
 */
export interface BlogCategoryListResponse {
  items: BlogCategory[];
}

/**
 * Fetch blog posts options
 */
export interface FetchBlogPostsOptions {
  page?: number;
  limit?: number;
  search?: string;
  category?: string;
  tag?: string;
  author?: string;
  order?: 'latest' | 'popular' | 'oldest';
}

/**
 * Fetch popular posts options
 */
export interface FetchPopularPostsOptions {
  limit?: number;
  days?: number;
}
