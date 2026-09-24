/**
 * Profile API Service — read and edit the signed-in user's own profile
 * (web dead-code audit M3: the backend endpoint existed, only mobile used it).
 *
 * Goes through the shared `apiClient` (todo 407 item 9), so it inherits the
 * client's cookie credentials, X-Request-ID, CSRF header on mutating requests
 * only, and its one-shot refresh-and-retry when a stale CSRF token gets a 403.
 * A bodyless GET carries no `Content-Type` (axios's xhr adapter drops it).
 */
import axios from 'axios';
import apiClient from '../utils/httpClient';
import type {
  DashboardActivityItem,
  DashboardForumStats,
  DashboardStats,
  ProfileUpdate,
  UserProfile,
} from '../types/auth';

const AUTH_BASE = '/api/v1/auth';

/**
 * Turn a DRF error body into one readable message. Validation errors arrive
 * either flattened (`{message}`) or as a field map (`{website: ["Enter a valid URL."]}`).
 */
function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object') {
    const record = body as Record<string, unknown>;
    if (typeof record.message === 'string' && record.message) return record.message;
    if (typeof record.detail === 'string' && record.detail) return record.detail;
    for (const [field, value] of Object.entries(record)) {
      const first = Array.isArray(value) ? value[0] : value;
      if (typeof first === 'string' && first) return `${field.replace(/_/g, ' ')}: ${first}`;
    }
  }
  return `Request failed (HTTP ${status})`;
}

/**
 * Re-throw an HTTP failure as a plain `Error` carrying the server's readable
 * message — an AxiosError's own message is "Request failed with status code
 * 400", which is not what ProfilePage should show. Anything without a
 * response (network, timeout) propagates unchanged.
 */
function toProfileError(error: unknown): unknown {
  if (axios.isAxiosError(error) && error.response) {
    return new Error(errorMessage(error.response.data, error.response.status), { cause: error });
  }
  return error;
}

export async function fetchProfile(): Promise<UserProfile> {
  try {
    const response = await apiClient.get<UserProfile>(`${AUTH_BASE}/user/`);
    // A non-JSON 2xx body arrives as a string under axios (PR #817 review).
    if (typeof response.data !== 'object' || response.data === null) {
      throw new Error('Could not load your profile.');
    }
    return response.data;
  } catch (error) {
    throw toProfileError(error);
  }
}

export async function updateProfile(changes: ProfileUpdate): Promise<UserProfile> {
  try {
    const response = await apiClient.patch<{ message: string; user: UserProfile }>(
      `${AUTH_BASE}/user/update/`,
      changes
    );
    return response.data.user;
  } catch (error) {
    throw toProfileError(error);
  }
}

const FORUM_STAT_KEYS: (keyof DashboardForumStats)[] = [
  'total_topics',
  'total_posts',
  'topics_this_month',
  'posts_this_month',
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isForumStats(value: unknown): value is DashboardForumStats {
  return isRecord(value) && FORUM_STAT_KEYS.every((key) => typeof value[key] === 'number');
}

/**
 * Keep only the two forum activity kinds, and only internal forum paths. An
 * older server also sent `plant_identification` items linking to
 * `/identify/<id>`; todo 411 removed them because nothing writes that table.
 */
/**
 * A topic link, optionally deep-linked to a post: `/forum/<id>-<slug>/<id>-<slug>`
 * plus `#post-<id>`. A whole-path match, not a prefix: `/forum/../identify/x`
 * starts with `/forum/` but react-router resolves it elsewhere (PR #821).
 */
const FORUM_ACTIVITY_PATH = /^\/forum\/\d+-[^/?#\s]*\/\d+-[^/?#\s]*(#post-\d+)?$/;

function isForumActivity(value: unknown): value is DashboardActivityItem {
  return (
    isRecord(value) &&
    (value.type === 'forum_topic' || value.type === 'forum_post') &&
    typeof value.title === 'string' &&
    typeof value.description === 'string' &&
    typeof value.timestamp === 'string' &&
    typeof value.url === 'string' &&
    FORUM_ACTIVITY_PATH.test(value.url)
  );
}

/**
 * The signed-in user's forum totals and recent activity. Only the typed forum
 * fields are passed on, so a stray key (the removed plant block) never reaches
 * the page.
 */
export async function fetchDashboardStats(): Promise<DashboardStats> {
  let data: unknown;
  try {
    data = (await apiClient.get<unknown>(`${AUTH_BASE}/me/dashboard-stats/`)).data;
  } catch (error) {
    throw toProfileError(error);
  }
  if (!isRecord(data) || !isForumStats(data.forum_stats) || !Array.isArray(data.recent_activity)) {
    throw new Error('Unexpected response from the activity stats endpoint.');
  }
  const stats = data.forum_stats;
  return {
    forum_stats: {
      total_topics: stats.total_topics,
      total_posts: stats.total_posts,
      topics_this_month: stats.topics_this_month,
      posts_this_month: stats.posts_this_month,
    },
    recent_activity: data.recent_activity.filter(isForumActivity).map((item) => ({
      type: item.type,
      title: item.title,
      description: item.description,
      timestamp: item.timestamp,
      url: item.url,
    })),
  };
}
