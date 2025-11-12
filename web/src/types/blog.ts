/**
 * Blog & Wagtail CMS Types
 */

/**
 * Plant Spotlight block
 * Backend: StructBlock with plant_name, scientific_name, description, care_difficulty, image
 */
export interface PlantSpotlightBlock {
  type: 'plant_spotlight';
  value: {
    plant_name: string; // CharBlock (required)
    scientific_name?: string; // CharBlock (optional, auto-populated)
    description: string; // RichTextBlock (HTML string, auto-populated or AI-generated)
    care_difficulty?: 'easy' | 'moderate' | 'difficult'; // ChoiceBlock (optional)
    image?: {
      url: string;
      title?: string;
    }; // ImageChooserBlock (optional)
  };
  id: string;
}

/**
 * Call to Action block
 * Backend: StructBlock with cta_title, cta_description, button_text, button_url, button_style
 */
export interface CallToActionBlock {
  type: 'call_to_action';
  value: {
    cta_title: string; // CharBlock (required)
    cta_description?: string; // RichTextBlock (optional, HTML string)
    button_text: string; // CharBlock (required)
    button_url: string; // URLBlock (required)
    button_style?: 'primary' | 'secondary' | 'outline'; // ChoiceBlock (optional, default: primary)
  };
  id: string;
}

/**
 * StreamField block types
 */
export type StreamFieldBlock =
  | ParagraphBlock
  | HeadingBlock
  | ImageBlock
  | QuoteBlock
  | CodeBlock
  | ListBlock
  | PlantSpotlightBlock
  | CallToActionBlock;

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
 * Backend: CharBlock (simple string, not structured)
 */
export interface HeadingBlock {
  type: 'heading';
  value: string;
  id: string;
}

/**
 * Image block
 * NOTE: Removed from backend - use paragraph with embedded images instead
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
 * Backend: StructBlock with quote_text (RichTextBlock) and attribution (CharBlock)
 */
export interface QuoteBlock {
  type: 'quote';
  value: {
    quote_text: string; // RichTextBlock (HTML string)
    attribution?: string; // CharBlock (optional)
  };
  id: string;
}

/**
 * Code block
 * Backend: StructBlock with language (ChoiceBlock) and code (TextBlock)
 */
export interface CodeBlock {
  type: 'code';
  value: {
    code: string; // TextBlock
    language?: string; // ChoiceBlock (optional: python, javascript, html, css, bash, json)
  };
  id: string;
}

/**
 * List block
 * NOTE: Not defined in backend BlogStreamBlocks
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
 * Blog post author
 */
export interface BlogPostAuthor {
  first_name: string;
  last_name: string;
}

/**
 * Blog post featured image
 */
export interface BlogPostImage {
  url: string;
  thumbnail?: {
    url: string;
  };
  title?: string;
}

/**
 * Blog post category
 */
export interface BlogPostCategory {
  name: string;
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
  slug: string;
  title: string;
  introduction?: string;
  content_blocks: StreamFieldBlock[];
  featured_image?: BlogPostImage;
  publish_date?: string;
  author?: BlogPostAuthor;
  tags?: string[];
  categories?: BlogPostCategory[];
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
