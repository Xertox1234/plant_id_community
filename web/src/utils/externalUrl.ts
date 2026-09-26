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

/**
 * The address line of a link preview card (todo 428, owner decision
 * 2026-09-24): the link's origin, plus "/…" when anything follows the root —
 * `https://microsoft.com/…` for `https://microsoft.com/en-us/windows?x=1`.
 * A card's visible text and its spoken label carry only this, never the
 * full URL (a screen reader spells a URL out character by character, the
 * build 13 bug from todo 424); the full URL is the card's `href` and its
 * `title` (hover). Null when `safeExternalUrl` refuses the URL.
 *
 * The mobile twin is `linkPreviewShortAddress` (forum_body_block.dart); both
 * are tested against the same table. They differ on an internationalised
 * host: `URL` shows it as punycode, Dart's `Uri` as written.
 */
export function shortLinkAddress(value: string | null | undefined): string | null {
  const safe = safeExternalUrl(value);
  if (!safe) return null;
  const parsed = new URL(safe);
  const rest = `${parsed.pathname}${parsed.search}${parsed.hash}`;
  return rest && rest !== '/' ? `${parsed.origin}/…` : parsed.origin;
}
