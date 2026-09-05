/**
 * Forum Entity Types
 */

import type { StreamFieldBlock as BlogStreamFieldBlock } from './blog';

/**
 * Forum category
 */
export interface Category {
  id: string;
  name: string;
  slug: string;
  description?: string;
  icon?: string;
  thread_count?: number;
  post_count?: number;
  created_at: string;
  /** ISO timestamp of the newest live topic's activity; null when nobody has posted. */
  last_post_at?: string | null;
  children?: Category[];
}

/**
 * The forum home payload — boards plus the `ForumIndex` welcome copy the CMS
 * owns. One backend response (`GET boards/`), because both render on the same
 * screen and always change together (todo 278 L2).
 */
export interface ForumIndexPayload {
  categories: Category[];
  /** Sanitized HTML from the CMS; `''` when no intro is set. */
  intro: string;
}

/**
 * Forum author — the unified object every topic/post/notification-actor payload
 * shares (backend serialize_forum_author, todo 257 H26/M41). A deleted author is
 * the `[deleted]` sentinel object, never null. `trust_level` is the backend
 * ForumProfile integer enum (0=New … 4=Leader) or null when the author has no
 * profile; `avatar` is an absolute image URL or null.
 */
export interface ForumAuthor {
  username: string;
  display_name: string;
  avatar: string | null;
  trust_level: number | null;
}

/**
 * One suggested species inside an attached identification snapshot (audit M6).
 * `confidence` is 0–1, not a percentage.
 */
export interface IdentificationCandidate {
  name: string;
  scientific_name?: string;
  confidence: number;
}

/**
 * The plant-ID snapshot a topic carries (audit M6) — detail payload ONLY.
 *
 * Author-supplied, not a verified determination: the backend records what the
 * app suggested to the person who posted, so the card must be labelled as such
 * and never presented as an authoritative ID. `image` is null when the photo
 * was never attached or has since been deleted (the FK is SET_NULL) — the card
 * falls back to text-only rather than disappearing.
 */
export interface ThreadIdentification {
  image: {
    id: number;
    url: string;
    alt: string;
    width: number;
    height: number;
  } | null;
  provider: string;
  candidates: IdentificationCandidate[];
  created_at: string;
}

/** One choice in a thread's poll, with its server-aggregated count. */
export interface ThreadPollOption {
  id: number;
  text: string;
  order: number;
  /**
   * Aggregated server-side from vote rows on every read. There is no stored
   * counter and no writable path to this number — render it, never derive or
   * submit it.
   */
  vote_count: number;
}

/**
 * A thread's poll (audit M8; multi-choice since todo 349).
 *
 * One submission per user per poll. A second submission is REJECTED (409),
 * not replaced or topped up — so `my_vote_option_ids`, once non-empty, is
 * final for this viewer and the vote controls should read as decided.
 */
export interface ThreadPoll {
  id: number;
  question: string;
  /** ISO datetime, or null when the poll never closes. */
  closes_at: string | null;
  is_closed: boolean;
  /** 1 = single-choice; N = a voter may pick up to N options in one ballot. */
  max_choices: number;
  options: ThreadPollOption[];
  /**
   * People who answered (distinct voters), not vote rows — in a multi-choice
   * poll the per-option counts can sum past this.
   */
  total_votes: number;
  /**
   * THIS viewer's own choice(s); empty when they have not voted (and always
   * empty for anonymous). Never anyone else's — only the aggregate is public.
   */
  my_vote_option_ids: number[];
}

/**
 * Forum thread
 */
export interface Thread {
  id: string;
  title: string;
  slug: string;
  excerpt?: string;
  category: Category;
  author: ForumAuthor;
  created_at: string;
  updated_at?: string;
  last_activity_at: string;
  post_count?: number;
  view_count?: number;
  is_pinned?: boolean;
  is_locked?: boolean;
  is_active?: boolean;
  is_subscribed?: boolean;
  /** Save-for-later, distinct from is_subscribed's notify-me intent (todo 283 / M2). */
  is_bookmarked?: boolean;
  /**
   * The topic's poll with server-computed results (audit M8), or null when it
   * has none. Populated on thread DETAIL only. Every count here is aggregated
   * server-side from vote rows — the client renders them, never computes or
   * submits them.
   */
  poll?: ThreadPoll | null;
  is_unread?: boolean;
  /** Secondary discovery taxonomy beside the board (audit M5). Normalized lowercase. */
  tags?: string[];
  /**
   * Accepted-answer state (audit H6). `is_solved` drives the Solved badge on
   * both the list and the thread; `solved_post_id` is the id of the accepted
   * post so the thread can highlight it. The backend clears both when the
   * accepted post stops being visible, so a true `is_solved` always points at
   * a readable post.
   */
  is_solved?: boolean;
  solved_post_id?: number | null;
  /** Detail-only: whether the CURRENT viewer may accept/clear an answer here. */
  can_mark_solution?: boolean;
  /**
   * Detail-only: the plant-ID snapshot attached at compose time (audit M6).
   * Absent on list/search payloads by design — the card renders above the
   * opening post and nowhere else.
   */
  identification?: ThreadIdentification | null;
}

/**
 * Forum post
 */
export interface Post {
  id: string;
  thread: string;
  // Same unified ForumAuthor object as Thread.author (todo 257 H26): username,
  // display_name, avatar, and the ForumProfile integer trust_level.
  author: ForumAuthor;
  content_raw: string;
  content_html?: string;
  content_format?: string;
  /** StreamField body blocks from wagtail_forum; rendered by StreamFieldRenderer. */
  body?: BlogStreamFieldBlock[];
  /**
   * Set only on search-result posts (from mapSearchPostToPost).
   * The topic title is carried so SearchPage can render a link without a PostCard.
   */
  topic_title?: string;
  /** Search-result-only link identity (mapSearchPostToPost). */
  topic_slug?: string;
  board_id?: number;
  board_slug?: string;
  created_at: string;
  updated_at?: string;
  edited_at?: string;
  edited_by?: {
    username: string;
    display_name?: string;
  };
  is_edited?: boolean;
  is_first_post?: boolean;
  is_active?: boolean;
  reaction_counts?: Record<string, number>;
  /** Reaction types the current user has active on this post (M23); [] when
   * logged out. Drives the reaction buttons' aria-pressed / pressed styling. */
  reacted?: string[];
  /** Permission flags from the backend (wagtail_forum PostSerializer). */
  can_edit?: boolean;
  can_delete?: boolean;
  can_report?: boolean;
  /** Whether the viewer has blocked this post's author (todo 284/M9). The
   * row is delivered in full (server doesn't redact) — PostCard collapses
   * it client-side with a local reveal toggle. */
  is_blocked?: boolean;
  /** Whether the viewer may block this post's author — false for their own
   * posts and for anonymous viewers. */
  can_block?: boolean;
  /** Whether the viewer has MUTED this author (todo 347) — one-directional,
   * content-only. Same COLLAPSE contract as is_blocked, its own flag. */
  is_muted?: boolean;
  /** Whether the viewer may mute this user — false for themselves/anonymous. */
  can_mute?: boolean;
}

/**
 * Paginated list response
 */
export interface PaginatedResponse<T> {
  items: T[];
  meta: {
    count: number;
    next?: string | null;
    previous?: string | null;
  };
}

/**
 * Update post input — body is HTML; the service wraps it as a paragraph block.
 */
export interface UpdatePostInput {
  content: string;
}

/**
 * The write shape of an identification snapshot (audit M6). Distinct from the
 * read shape `ThreadIdentification`: the request carries a bare `image_id` the
 * caller already uploaded via `uploadPostImage`, while the response carries the
 * resolved rendition object.
 */
export interface CreateIdentificationInput {
  image_id?: number | null;
  provider?: string;
  candidates: IdentificationCandidate[];
}

/**
 * The write shape of a poll (audit M8). Creation only — polls are attached at
 * compose time and never edited, since changing a question or an option after
 * votes exist silently rewrites what those votes meant.
 *
 * Note the absence of any count field, which is the point: results are
 * aggregated server-side from vote rows, so there is nothing here a caller
 * could use to seed them.
 */
export interface CreatePollInput {
  question: string;
  /** 2–10 after blanks are dropped; must be unique case-insensitively. */
  options: string[];
  /** ISO datetime in the future, or omitted for a poll that never closes. */
  closes_at?: string | null;
  /**
   * How many options one voter may pick (todo 349). Omitted = 1, the
   * single-choice poll; must not exceed the number of non-blank options.
   */
  max_choices?: number;
}

/** Create-topic input (POST /boards/{slug}/topics/). content is HTML. */
export interface CreateTopicInput {
  boardSlug: string;
  title: string;
  content: string;
  /** Optional secondary taxonomy (audit M5). Server normalizes + bounds them. */
  tags?: string[];
  /**
   * Optional plant-ID snapshot to attach (audit M6) — the "Ask the community"
   * flow. The server bounds candidate count/length and requires `image_id` to
   * be an image THIS user uploaded to the forum collection.
   */
  identification?: CreateIdentificationInput | null;
  /** Optional poll to attach (audit M8). Server bounds and normalizes it. */
  poll?: CreatePollInput | null;
}

/** Create-reply input (POST /topics/{id}/posts/). content is HTML. */
export interface CreateReplyInput {
  thread: number;
  content: string;
}

/** Thin create-topic response — the topic may be pending moderation. */
export interface CreateTopicResult {
  id: string;
  slug: string;
  status: 'published' | 'pending';
}

/** Thin create-reply response — the reply may be pending moderation. */
export interface CreateReplyResult {
  id: string;
  status: 'published' | 'pending';
}

/** Edit response — the (currently-live) post plus its moderation outcome. */
export interface EditPostResult {
  post: Post;
  status: 'published' | 'pending';
}

/**
 * Search forum options
 */
export interface SearchForumOptions {
  q: string;
  /** Board slug — sent to the backend as ?board= */
  category?: string;
  /** 1-based page; only sent to the backend when > 1. */
  page?: number;
  /** Cancels the in-flight request when aborted (e.g. a superseding query). */
  signal?: AbortSignal;
}

export interface SearchForumResponse {
  query: string;
  threads: Thread[];
  posts: Post[];
  /** Length of THIS response's threads/posts (per page), not a grand total. */
  total_threads: number;
  total_posts: number;
  /** Whether a further page of thread/post results exists. */
  has_more_threads: boolean;
  has_more_posts: boolean;
}

// ---------------------------------------------------------------------------
// RAG plant-care answers (todo 289 / M13) — POST /forum/care/ask/
// ---------------------------------------------------------------------------

export type PlantCareReferralReason = 'ingestion' | 'chemical_dosing';

interface PlantCareSourceBase {
  /** 1-based; matches the `[n]` markers inside `answer`. */
  n: number;
  title: string;
  /** ISO date (blog: YYYY-MM-DD) or datetime (topic). */
  date: string;
  snippet: string;
}

export interface PlantCareBlogSource extends PlantCareSourceBase {
  kind: 'blog';
  slug: string;
  /** `block-N` on the article, or null once the index drifted after an edit. */
  anchor: string | null;
}

export interface PlantCareTopicSource extends PlantCareSourceBase {
  kind: 'topic';
  topic_id: number;
  topic_slug: string;
  board_id: number;
  board_slug: string;
}

export type PlantCareSource = PlantCareBlogSource | PlantCareTopicSource;

/**
 * Status-discriminated 200 envelope. "No information" and a blocked question
 * are RESULTS, not errors; only `answered` carries an `answer_id` (and is the
 * only status that can be reported).
 */
export type PlantCareAnswer =
  | {
      status: 'answered';
      answer_id: number;
      answer: string;
      citations: number[];
      sources: PlantCareSource[];
      disclaimer: string;
    }
  | {
      status: 'passages_only';
      answer_id: null;
      sources: PlantCareSource[];
      disclaimer: string;
    }
  | { status: 'no_information'; answer_id: null; sources: [] }
  | {
      status: 'referral';
      answer_id: null;
      referral: { reason: PlantCareReferralReason; message: string };
    };

/** Result of toggling a reaction on a post (backend toggle endpoint). */
export interface ReactionToggleResult {
  /** Map of reaction_type -> count, e.g. { like: 5, love: 2 } */
  reaction_counts: Record<string, number>;
  /** Whether the current user now has this reaction active on the post. */
  reacted: boolean;
}

/** A public forum profile (GET /forum/users/{username}/, todo 257 H7). */
export interface ForumUserProfile {
  username: string;
  display_name: string;
  avatar: string | null;
  trust_level: number | null;
  bio: string;
  signature: string;
  /** Lifetime denormalized post count — not the length of recent_posts. */
  post_count: number;
  joined_at: string | null;
  recent_topics: {
    id: number;
    slug: string;
    title: string;
    board_id: number;
    board_slug: string;
    reply_count: number;
    created_at: string;
  }[];
  recent_posts: {
    id: number;
    topic_id: number;
    topic_slug: string;
    topic_title: string;
    board_id: number;
    board_slug: string;
    created_at: string;
  }[];
  /** Whether the viewer has blocked this profile's user (todo 284/M9).
   * recent_topics/recent_posts are still returned in full when true — the
   * page renders its own blocked notice, not a server-side redaction. */
  is_blocked?: boolean;
  /** Whether the viewer may block this user — false for their own profile
   * and for anonymous viewers. */
  can_block?: boolean;
  /** Earned badges in display order (todo 348) — public identity, shown
   * even to a viewer who blocked or muted this member. */
  badges?: ForumBadge[];
  /** Whether the viewer has MUTED this author (todo 347) — one-directional,
   * content-only. Same COLLAPSE contract as is_blocked, its own flag. */
  is_muted?: boolean;
  /** Whether the viewer may mute this user — false for themselves/anonymous. */
  can_mute?: boolean;
}

/** GET me/blocks/ row (todo 284/M9) — a member the viewer has blocked. */
export interface BlockedUser {
  username: string;
  display_name: string;
  avatar: string | null;
  trust_level: number | null;
  title: string;
  blocked_at: string;
}

/** GET me/mutes/ row (todo 347) — a member the viewer has muted. */
export interface MutedUser {
  username: string;
  display_name: string;
  avatar: string | null;
  trust_level: number | null;
  title: string;
  muted_at: string;
}

/** An earned badge from the CMS-curated engine (todo 348). */
export interface ForumBadge {
  slug: string;
  name: string;
  description: string;
  awarded_at: string;
}

/** GET me/stats/ — all-time counts ("Your season" cards, todo 300). */
export interface ForumMyStats {
  posts: number;
  solutions_accepted: number;
  identifications_shared: number;
  streak_days: number;
  badge_name: string;
  badge_progress: number;
  badge_target: number;
  /** Earned badges in display order (todo 348). */
  badges: ForumBadge[];
}

/** The minimal board identity carried on a topic-shaped API row. */
export interface BoardSummary {
  id: number;
  name: string;
  slug: string;
}

/** GET topics/recent/ row — the landing rail's "Active now" shape. */
export interface RecentTopic {
  id: number;
  slug: string;
  title: string;
  board: BoardSummary;
  reply_count: number;
  last_post_at: string | null;
  is_pinned: boolean;
  thumbnail_url: string | null;
}

/** GET users/experts/ row — serialize_forum_author + title + online (todo 301). */
export interface ForumExpert {
  username: string;
  display_name: string;
  avatar: string | null;
  trust_level: number | null;
  title: string;
  // Optional, not `boolean` — a server predating todo 301, or any other
  // client/server version skew, omits the field entirely rather than
  // sending `false`. The module must treat "absent" as "no claim", not as
  // offline (todo 301 AC3), so it can never be silently widened to
  // `boolean` with an implicit `?? false` at the read site.
  online?: boolean;
}

/** GET event/ `topic` — the CMS-featured landing-page hero (todo 304). */
export interface EventHeroTopic {
  id: number;
  slug: string;
  title: string;
  board: BoardSummary;
  eyebrow: string;
  description: string;
}

/** GET event/ — `{topic: null}` when no event is currently featured. */
export interface EventHero {
  topic: EventHeroTopic | null;
}

// ---------------------------------------------------------------------------
// Direct messages (todo 339) — GET /forum/conversations/ and friends.
//
// Typed verbatim off the backend serializers (snake_case, no mapping layer),
// the same way notifications and the block/mute lists are — there is no
// string-id or slug convention to translate here.
// ---------------------------------------------------------------------------

/** The inbox preview of a conversation's most recent message (body ≤140 chars). */
export interface ConversationLastMessage {
  body: string;
  /** True when the VIEWER sent it — the inbox prefixes the preview "You: ". */
  is_mine: boolean;
  created_at: string;
}

/** GET conversations/ row — one two-party thread, most recent activity first. */
export interface Conversation {
  id: number;
  /** The member on the other side; the viewer is never listed. */
  other_participant: ForumAuthor;
  created_at: string;
  last_message_at: string;
  /** Messages from the other side the viewer has not opened yet. */
  unread_count: number;
  /** Null only for a conversation with no messages (not reachable via the API today). */
  last_message: ConversationLastMessage | null;
}

/** GET conversations/{id}/messages/ row. `body` is plain text — render it as text. */
export interface DirectMessage {
  id: number;
  conversation_id: number;
  sender: ForumAuthor;
  body: string;
  created_at: string;
}

/** DRF cursor page (no count) shared by the inbox and the message thread. */
export interface DirectMessageCursorPage<T> {
  results: T[];
  next: string | null;
  previous: string | null;
}
