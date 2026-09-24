/**
 * Profile API Service — read and edit the signed-in user's own profile
 * (web dead-code audit M3: the backend endpoint existed, only mobile used it).
 *
 * Cookie-based JWT auth with CSRF on mutating requests (same pattern as
 * notificationService.ts).
 */
import { getCsrfToken } from '../utils/csrf';
import type {
  DashboardActivityItem,
  DashboardForumStats,
  DashboardStats,
  ProfileUpdate,
  UserProfile,
} from '../types/auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const AUTH_BASE = `${API_URL}/api/v1/auth`;

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

async function authenticatedFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
  const csrfToken = await getCsrfToken();
  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...(csrfToken && { 'X-CSRFToken': csrfToken }),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(errorMessage(body, response.status));
  }
  return response.json();
}

export async function fetchProfile(): Promise<UserProfile> {
  return authenticatedFetch<UserProfile>(`${AUTH_BASE}/user/`);
}

export async function updateProfile(changes: ProfileUpdate): Promise<UserProfile> {
  const data = await authenticatedFetch<{ message: string; user: UserProfile }>(
    `${AUTH_BASE}/user/update/`,
    { method: 'PATCH', body: JSON.stringify(changes) }
  );
  return data.user;
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
function isForumActivity(value: unknown): value is DashboardActivityItem {
  return (
    isRecord(value) &&
    (value.type === 'forum_topic' || value.type === 'forum_post') &&
    typeof value.title === 'string' &&
    typeof value.description === 'string' &&
    typeof value.timestamp === 'string' &&
    typeof value.url === 'string' &&
    value.url.startsWith('/forum/')
  );
}

/**
 * The signed-in user's forum totals and recent activity. Only the typed forum
 * fields are passed on, so a stray key (the removed plant block) never reaches
 * the page.
 */
export async function fetchDashboardStats(): Promise<DashboardStats> {
  const data = await authenticatedFetch<unknown>(`${AUTH_BASE}/me/dashboard-stats/`);
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
