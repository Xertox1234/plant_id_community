/**
 * Returns `value` normalised if it is an absolute http(s) URL with a host and
 * no embedded credentials, else `null`. Use it for any server-supplied URL that
 * becomes an `href`/`src` — never let a `javascript:`/`data:` value through.
 * Shared by the forum link preview card, the blog plant_spotlight photo
 * credit (todo 376), the composer's preview-URL detection
 * (`forumBody.ts` validPreviewUrl) and `fetchLinkPreview` (todo 438) — the
 * last two use it as the check only and keep the author's own string.
 */
export function safeExternalUrl(
  value: string | null | undefined,
  httpsOnly = false
): string | null {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    if (
      !['http:', 'https:'].includes(parsed.protocol) ||
      (httpsOnly && parsed.protocol !== 'https:') ||
      !parsed.hostname ||
      parsed.username ||
      parsed.password
    ) {
      return null;
    }
    return parsed.toString();
  } catch {
    return null;
  }
}
