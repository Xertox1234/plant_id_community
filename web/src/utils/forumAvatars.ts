/**
 * Field Notes default avatars — 8 vintage botanical engravings (generated
 * once, shipped in /public/avatars/) shown when a user has no avatar of
 * their own. Deterministic per username, so a given user is always the same
 * specimen everywhere their posts appear.
 */

const SPECIMEN_COUNT = 8;

export function specimenAvatar(username: string): string {
  let hash = 0;
  for (let i = 0; i < username.length; i++) {
    hash = (hash * 31 + username.charCodeAt(i)) >>> 0;
  }
  return `/avatars/specimen-${(hash % SPECIMEN_COUNT) + 1}.jpg`;
}
