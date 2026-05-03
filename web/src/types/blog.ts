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
 * StreamField block types
 */
export type StreamFieldBlock =
  | ParagraphBlock
  | HeadingBlock
  | QuoteBlock
  | CodeBlock
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
