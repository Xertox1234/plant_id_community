/**
 * Wrap @username mentions in styled spans, matching the composer's mention
 * styling (forumMentionNode.ts: text-primary font-medium).
 *
 * SECURITY: operates on ALREADY-SANITIZED HTML (call after createSafeMarkup),
 * walks text nodes only, and inserts only a span with a fixed class — it can
 * never introduce markup from user content.
 */

// A mention starts the string or follows whitespace/"(" — this skips emails,
// where "@" follows a word character.
const MENTION_RE = /(^|[\s(])@([A-Za-z0-9_]+)/g;

export function highlightMentions(sanitizedHtml: string): string {
  if (!sanitizedHtml.includes('@')) return sanitizedHtml;
  const doc = new DOMParser().parseFromString(
    `<div id="__mention_root">${sanitizedHtml}</div>`,
    'text/html'
  );
  const root = doc.getElementById('__mention_root');
  if (!root) return sanitizedHtml;
  const walker = doc.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const textNodes: Text[] = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const parent = (n as Text).parentElement;
    if (parent && !parent.closest('a, code, pre')) textNodes.push(n as Text);
  }
  for (const node of textNodes) {
    const text = node.textContent || '';
    MENTION_RE.lastIndex = 0;
    if (!MENTION_RE.test(text)) continue;
    const frag = doc.createDocumentFragment();
    let cursor = 0;
    MENTION_RE.lastIndex = 0;
    for (let m = MENTION_RE.exec(text); m; m = MENTION_RE.exec(text)) {
      const mentionStart = m.index + m[1].length;
      frag.appendChild(doc.createTextNode(text.slice(cursor, mentionStart)));
      const span = doc.createElement('span');
      span.className = 'text-primary font-medium';
      span.textContent = `@${m[2]}`;
      frag.appendChild(span);
      cursor = mentionStart + m[2].length + 1;
    }
    frag.appendChild(doc.createTextNode(text.slice(cursor)));
    node.replaceWith(frag);
  }
  return root.innerHTML;
}
