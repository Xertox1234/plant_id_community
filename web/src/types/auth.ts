/**
 * Authentication & User Types
 */

/**
 * User model (from Django backend)
 */
export interface User {
  id: number;
  email: string;
  username?: string;
  name?: string; // Full name (may be used instead of first_name/last_name)
  display_name?: string; // Display name for forum/posts
  first_name?: string;
  last_name?: string;
  trust_level?: 'new' | 'basic' | 'trusted' | 'veteran' | 'expert';
  date_joined?: string;
  is_active?: boolean;
  is_staff?: boolean; // Django staff user
  is_moderator?: boolean; // Forum moderator
}

/**
 * The signed-in user's own profile, as GET /api/v1/auth/user/ returns it
 * (backend UserProfileSerializer). Only the fields the profile page uses.
 */
export interface UserProfile {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  display_name: string;
  bio: string;
  location: string;
  website: string;
}

/**
 * The fields the web profile page may change via PATCH /api/v1/auth/user/update/.
 * Email is deliberately absent: changing it needs re-verification, which the
 * backend does not do yet.
 */
export type ProfileUpdate = Partial<
  Pick<UserProfile, 'first_name' | 'last_name' | 'bio' | 'location' | 'website'>
>;

/**
 * The signed-in user's forum totals from GET /api/v1/auth/me/dashboard-stats/.
 * "This month" is the last 30 days. Posts include each topic's opening post.
 */
export interface DashboardForumStats {
  total_topics: number;
  total_posts: number;
  topics_this_month: number;
  posts_this_month: number;
}

/**
 * One `recent_activity` entry: a topic the user started or a reply they wrote.
 * `url` is a web forum path (`/forum/{boardId}-{slug}/{topicId}-{slug}`).
 */
export interface DashboardActivityItem {
  type: 'forum_topic' | 'forum_post';
  title: string;
  description: string;
  timestamp: string;
  url: string;
}

/**
 * GET /api/v1/auth/me/dashboard-stats/. Forum data only: todo 411 removed the
 * plant block (plant_stats, plant_identification activity, total_activity_score)
 * because nothing writes the tables it read.
 */
export interface DashboardStats {
  forum_stats: DashboardForumStats;
  recent_activity: DashboardActivityItem[];
}

/**
 * Login credentials
 */
export interface LoginCredentials {
  email: string;
  password: string;
}

/**
 * Signup data (matches frontend form)
 */
export interface SignupData {
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  confirmPassword?: string; // Optional for frontend validation
}

/**
 * Authentication response
 */
export interface AuthResponse {
  user: User;
  token?: string;
}

/**
 * Authentication error codes for categorization
 */
export enum AuthErrorCode {
  INVALID_CREDENTIALS = 'INVALID_CREDENTIALS',
  EMAIL_EXISTS = 'EMAIL_EXISTS',
  NETWORK_ERROR = 'NETWORK_ERROR',
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  SESSION_EXPIRED = 'SESSION_EXPIRED',
  RATE_LIMITED = 'RATE_LIMITED',
  UNKNOWN = 'UNKNOWN',
}

/**
 * Structured authentication error
 * Provides better debugging and error tracking (Sentry integration)
 */
export interface AuthError {
  message: string;
  code: AuthErrorCode;
  details?: Record<string, unknown>;
}
