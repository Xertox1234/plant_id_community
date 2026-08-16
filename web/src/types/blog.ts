/**
 * Blog & Wagtail CMS Types
 */

export type StreamFieldBlockId = string | number;

interface BaseStreamFieldBlock {
  id?: StreamFieldBlockId;
}

/**
 * Heading block value.
 * Backend: CharBlock serialized as a string.
 */
export type HeadingBlockValue = string;

/**
 * Paragraph block value.
 * Backend: RichTextBlock serialized as an HTML string.
 */
export type ParagraphBlockValue = string;

/**
 * Quote block value.
 * Backend canonical field is quote_text; quote is accepted for legacy API payloads.
 */
export interface QuoteBlockValue {
  quote_text?: string;
  quote?: string;
  attribution?: string;
}

/**
 * Code block value.
 * Backend: StructBlock with language (ChoiceBlock) and code (TextBlock).
 */
export interface CodeBlockValue {
  code: string;
  language?: string;
}

/**
 * Plant spotlight block value.
 * Backend canonical fields use plant_name and care_difficulty; heading/care_level
 * are accepted for older generated payloads.
 */
export interface PlantSpotlightBlockValue {
  plant_name?: string;
  heading?: string;
  scientific_name?: string;
  description?: string;
  care_difficulty?: 'easy' | 'moderate' | 'difficult';
  care_level?: string;
  image?: {
    url: string;
    title?: string;
    alt?: string;
  };
}

/**
 * Call to action block value.
 * Backend canonical fields use cta_title and cta_description; heading/description
 * are accepted for older generated payloads.
 */
export interface CallToActionBlockValue {
  cta_title?: string;
  heading?: string;
  cta_description?: string;
  description?: string;
  button_text?: string;
  button_url?: string;
  button_style?: 'primary' | 'secondary' | 'outline';
}

/**
 * Plant Spotlight block
 * Backend: StructBlock with plant_name, scientific_name, description, care_difficulty, image
 */
export interface PlantSpotlightBlock extends BaseStreamFieldBlock {
  type: 'plant_spotlight';
  value: PlantSpotlightBlockValue;
}

/**
 * Call to Action block
 * Backend: StructBlock with cta_title, cta_description, button_text, button_url, button_style
 */
export interface CallToActionBlock extends BaseStreamFieldBlock {
  type: 'call_to_action';
  value: CallToActionBlockValue;
}

/**
 * Image block value.
 * Backend (forum PR-3): an ImageChooserBlock serialized as a flat rendition dict.
 */
export interface ImageBlockValue {
  id: number;
  url: string;
  alt?: string;
  width?: number;
  height?: number;
}

/**
 * Image block
 * Backend: ImageChooserBlock (forum inline images) → {id, url, alt, width, height}.
 */
export interface ImageBlock extends BaseStreamFieldBlock {
  type: 'image';
  value: ImageBlockValue;
}

/**
 * StreamField block types
 */
export type StreamFieldBlock =
  | ParagraphBlock
  | HeadingBlock
  | QuoteBlock
  | CodeBlock
  | ImageBlock
  | PlantSpotlightBlock
  | CallToActionBlock;

/**
 * Paragraph block
 */
export interface ParagraphBlock extends BaseStreamFieldBlock {
  type: 'paragraph';
  value: ParagraphBlockValue;
}

/**
 * Heading block
 * Backend: CharBlock (simple string, not structured)
 */
export interface HeadingBlock extends BaseStreamFieldBlock {
  type: 'heading';
  value: HeadingBlockValue;
}

/**
 * Quote block
 * Backend: StructBlock with quote_text (RichTextBlock) and attribution (CharBlock)
 */
export interface QuoteBlock extends BaseStreamFieldBlock {
  type: 'quote';
  value: QuoteBlockValue | string;
}

/**
 * Code block
 * Backend: StructBlock with language (ChoiceBlock) and code (TextBlock)
 */
export interface CodeBlock extends BaseStreamFieldBlock {
  type: 'code';
  value: CodeBlockValue;
}

/**
 * Blog post author
 */
export interface BlogPostAuthor {
  id?: number;
  username?: string;
  first_name?: string;
  last_name?: string;
  /** Server-computed: get_full_name() or username. Preferred display string. */
  display_name?: string;
}

/**
 * Wagtail ImageRenditionField payload (probed 2026-08-16):
 * featured_image = fill-800x400, featured_image_thumb = fill-300x200.
 * `url` is relative (`/media/...`) — resolve with `mediaUrl` (see
 * `services/blogService.ts`) before using it as a src.
 */
export interface BlogPostImage {
  url: string;
  width?: number;
  height?: number;
  alt?: string;
}

/** Item shape of the detail response's server-computed related_posts. */
export interface RelatedPostSummary {
  id: number;
  title: string;
  slug: string;
  url?: string | null;
  published_date?: string | null;
  excerpt?: string;
  /**
   * fill-300x200 URL string (or null) — `_get_post_image` returns a bare
   * URL here, unlike the rendition objects used elsewhere
   * (featured_image/featured_image_thumb on BlogPost). Absolute when a
   * request is in serializer context, a bare rendition path otherwise —
   * resolve with `mediaUrl` either way before use as a src.
   */
  featured_image?: string | null;
}

/**
 * Blog post category.
 * Backend `BlogCategorySerializer` also serves id/slug (and other snippet
 * fields) alongside name — id/slug added here to match the probed shape.
 */
export interface BlogPostCategory {
  id?: number;
  name: string;
  slug?: string;
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
  /** List/popular endpoints send a trimmed `excerpt` instead of `introduction`. */
  excerpt?: string;
  content_blocks: StreamFieldBlock[];
  featured_image?: BlogPostImage;
  featured_image_thumb?: BlogPostImage;
  publish_date?: string;
  author?: BlogPostAuthor;
  tags?: string[];
  categories?: BlogPostCategory[];
  related_posts?: RelatedPostSummary[];
  reading_time?: number | null;
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
