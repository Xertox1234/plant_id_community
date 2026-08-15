import { hashString } from './hashString';

/**
 * Default avatars — 8 specimen portraits (generated once, shipped in
 * /public/avatars/) shown when a user has no avatar of their own.
 * Deterministic per username, so a given user is always the same specimen
 * everywhere their posts appear.
 */

const SPECIMEN_COUNT = 8;

export function specimenAvatar(username: string): string {
  return `/avatars/specimen-${(hashString(username) % SPECIMEN_COUNT) + 1}.jpg`;
}
