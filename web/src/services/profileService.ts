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
import { toHttpError } from '../utils/httpError';
import type {
  DashboardActivityItem,
  DashboardForumStats,
  DashboardStats,
  ProfileUpdate,
  UserProfile,
} from '../types/auth';

const AUTH_BASE = '/api/v1/auth';

// Failures are re-thrown through the shared `toHttpError` (todo 434): the
// server's readable message, or a connection message for a network error or
// timeout — never axios's "Request failed with status code 400". A
// cancellation or any other response-less axios error (a client bug such as
// `ERR_INVALID_URL`) is re-thrown unchanged, with axios's own message
// (todo 489).

export async function fetchProfile(): Promise<UserProfile> {
  try {
    const response = await apiClient.get<UserProfile>(`${AUTH_BASE}/user/`);
    // A non-JSON 2xx body arrives as a string under axios (PR #817 review).
    if (typeof response.data !== 'object' || response.data === null) {
      throw new Error('Could not load your profile.');
    }
    return response.data;
  } catch (error) {
    throw toHttpError(error);
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
    throw toHttpError(error);
  }
}

/**
 * The fields passed on to the page. The guards check these keys and `pick`
 * copies exactly these keys, so a new payload field is one type edit plus one
 * entry here (todo 439).
 */
const FORUM_STAT_KEYS = [
  'total_topics',
  'total_posts',
  'topics_this_month',
  'posts_this_month',
] as const satisfies readonly (keyof DashboardForumStats)[];

const ACTIVITY_KEYS = [
  'type',
  'title',
  'description',
  'timestamp',
  'url',
] as const satisfies readonly (keyof DashboardActivityItem)[];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Copy only `keys` from `source`, dropping any stray field the server adds. */
function pick<T, K extends keyof T>(source: T, keys: readonly K[]): Pick<T, K> {
  const picked = {} as Pick<T, K>;
  for (const key of keys) picked[key] = source[key];
  return picked;
}

/**
 * Shown for a 401 instead of DRF's "Authentication credentials were not
 * provided." The JWT authenticator sends a challenge, so a missing or expired
 * session is always a 401 here; a 403 is something else and keeps its detail.
 */
const SIGNED_OUT_MESSAGE = 'Your session has ended. Sign in again to see your forum activity.';

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
 * the page. A 401 becomes a plain sign-in-again message rather than DRF's
 * raw detail (todo 439).
 */
export async function fetchDashboardStats(): Promise<DashboardStats> {
  let data: unknown;
  try {
    data = (await apiClient.get<unknown>(`${AUTH_BASE}/me/dashboard-stats/`)).data;
  } catch (error) {
    const status = axios.isAxiosError(error) ? error.response?.status : undefined;
    if (status === 401) {
      throw new Error(SIGNED_OUT_MESSAGE, { cause: error });
    }
    throw toHttpError(error);
  }
  if (!isRecord(data) || !isForumStats(data.forum_stats) || !Array.isArray(data.recent_activity)) {
    throw new Error('Unexpected response from the activity stats endpoint.');
  }
  return {
    forum_stats: pick(data.forum_stats, FORUM_STAT_KEYS),
    recent_activity: data.recent_activity
      .filter(isForumActivity)
      .map((item) => pick(item, ACTIVITY_KEYS)),
  };
}
