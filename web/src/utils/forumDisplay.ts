import type { ForumColour, ForumTheme, ForumWatchLevel } from '@/types';

/**
 * A forum's or category's accent (todo 669) as a CSS colour. Each name maps
 * to a Canopy token that is defined for light AND dark mode (index.css), so a
 * stored accent can never fail contrast in either; the backend only accepts
 * these four names. Undefined for no accent.
 */
const ACCENT_VARS: Record<ForumColour, string> = {
  sage: 'var(--gt-leaf)',
  pollen: 'var(--gt-tertiary)',
  bloom: 'var(--gt-berry)',
  orchid: 'var(--gt-sky)',
};

export function forumAccent(colour: string | null | undefined): string | undefined {
  return colour && colour in ACCENT_VARS ? ACCENT_VARS[colour as ForumColour] : undefined;
}

/** The themes index.css defines a token scope for (todo 681). */
export const FORUM_THEMES: readonly ForumTheme[] = ['botanical', 'moss', 'terracotta', 'slate'];

/** The `data-forum-theme` value for a stored theme, or undefined for none or
 * an unknown value (a newer backend's theme this build has no tokens for). */
export function forumThemeAttr(theme: string | null | undefined): ForumTheme | undefined {
  return theme && (FORUM_THEMES as readonly string[]).includes(theme)
    ? (theme as ForumTheme)
    : undefined;
}

/** The four levels (todo 672, Discourse's), with what each one does. */
export const WATCH_LEVEL_OPTIONS: { value: ForumWatchLevel | ''; label: string }[] = [
  { value: '', label: 'Normal' },
  { value: 'watching', label: 'Watching: every new topic and reply' },
  { value: 'watching_first_post', label: 'Watching first post: new topics only' },
  { value: 'tracking', label: 'Tracking: show an unread count' },
  { value: 'muted', label: 'Muted: hide from Recent and the digest' },
];
