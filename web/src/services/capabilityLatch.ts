/**
 * Keyed registry of the per-account API capability latches (todo 433).
 *
 * The web has no client-side premium flag: the server's 403 (or a `code:
 * "disabled"` 503) is what tells a surface that THIS account, or this
 * deployment, can never use a premium AI feature. That fact outlives any one
 * component — the reply composer is remounted after every post, the summary
 * panel on every thread — so it lives here, with the API client, for the
 * session (docs/rules/react.md, "Session-lifetime API state").
 *
 * One registry instead of a `let` per feature in forumService: each latch is
 * about the ACCOUNT, so `AuthContext` must clear all of them on every identity
 * change (a non-premium user who upgrades, or signs out and back in as someone
 * else in the same SPA session, would otherwise keep a dead button until
 * reload). With one `let` per feature that was one hand-written reset line per
 * feature — three by todo 414 — and the third copy was the review's cue that
 * "forgot to add the reset" was only a matter of time. Adding a capability now
 * means adding a key; `resetAllCapabilityLatches` covers it.
 *
 * Written by the CALLER's error branch (which decides `permanent`), never inside
 * the request function, so a test that stubs the request still sets the flag.
 * `forumService` keeps named wrappers (`isComposeAssistUnavailable`, ...) over
 * these: the components and the tests read better as a sentence than as a key.
 */

export type CapabilityKey = 'composeAssist' | 'plantCareAsk' | 'topicSummary';

const latched = new Set<CapabilityKey>();

/** True once the server has said this account/deployment can never use `key`. */
export function isCapabilityUnavailable(key: CapabilityKey): boolean {
  return latched.has(key);
}

/** Remember a permanent failure for the rest of the session (or identity). */
export function markCapabilityUnavailable(key: CapabilityKey): void {
  latched.add(key);
}

/** Clear one latch — tests, between cases in a file. */
export function resetCapabilityAvailability(key: CapabilityKey): void {
  latched.delete(key);
}

/** Clear every latch — `AuthContext`, on every auth-state change. */
export function resetAllCapabilityLatches(): void {
  latched.clear();
}
