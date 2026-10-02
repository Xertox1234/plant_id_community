import { describe, it, expect, beforeEach } from 'vitest';
import {
  isCapabilityUnavailable,
  markCapabilityUnavailable,
  resetAllCapabilityLatches,
  resetCapabilityAvailability,
  type CapabilityKey,
} from './capabilityLatch';

/**
 * capabilityLatch (todo 433) — the keyed registry behind forumService's
 * `isComposeAssistUnavailable` / `isPlantCareAskUnavailable` /
 * `isTopicSummaryUnavailable` wrappers. Module state, so every case starts
 * from a full reset.
 */

const KEYS: CapabilityKey[] = ['composeAssist', 'plantCareAsk', 'topicSummary'];

describe('capabilityLatch', () => {
  beforeEach(() => {
    resetAllCapabilityLatches();
  });

  it('starts clear and latches one capability without touching the others', () => {
    for (const key of KEYS) expect(isCapabilityUnavailable(key)).toBe(false);

    markCapabilityUnavailable('topicSummary');

    expect(isCapabilityUnavailable('topicSummary')).toBe(true);
    expect(isCapabilityUnavailable('composeAssist')).toBe(false);
    expect(isCapabilityUnavailable('plantCareAsk')).toBe(false);
  });

  it('resets one key and leaves another latched', () => {
    markCapabilityUnavailable('composeAssist');
    markCapabilityUnavailable('plantCareAsk');

    resetCapabilityAvailability('composeAssist');

    expect(isCapabilityUnavailable('composeAssist')).toBe(false);
    expect(isCapabilityUnavailable('plantCareAsk')).toBe(true);
  });

  it('resetAllCapabilityLatches clears every key — the one call AuthContext makes', () => {
    for (const key of KEYS) markCapabilityUnavailable(key);
    for (const key of KEYS) expect(isCapabilityUnavailable(key)).toBe(true);

    resetAllCapabilityLatches();

    for (const key of KEYS) expect(isCapabilityUnavailable(key)).toBe(false);
  });

  it('is idempotent: marking twice stays latched, resetting an unlatched key is a no-op', () => {
    markCapabilityUnavailable('plantCareAsk');
    markCapabilityUnavailable('plantCareAsk');
    expect(isCapabilityUnavailable('plantCareAsk')).toBe(true);

    resetCapabilityAvailability('topicSummary');
    expect(isCapabilityUnavailable('plantCareAsk')).toBe(true);
    expect(isCapabilityUnavailable('topicSummary')).toBe(false);
  });
});
