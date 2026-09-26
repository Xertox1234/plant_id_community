import { describe, expect, it } from 'vitest';
import { shortLinkAddress } from './externalUrl';

// The same table as the mobile twin's test
// (plant_community_mobile/test/features/forum/models/forum_body_block_test.dart,
// `linkPreviewShortAddress`), so a card shows the same address line on both.
const SHORT_ADDRESS_TABLE: [string, string][] = [
  ['https://example.com', 'https://example.com'],
  ['https://example.com/', 'https://example.com'],
  ['https://microsoft.com/en-us/windows/some/long/path?x=1', 'https://microsoft.com/…'],
  ['https://example.com/?q=1', 'https://example.com/…'],
  ['https://example.com/#top', 'https://example.com/…'],
  ['http://example.com:8080/a', 'http://example.com:8080/…'],
  ['https://example.com:443/', 'https://example.com'],
  ['HTTPS://Example.COM/Path', 'https://example.com/…'],
];

describe('shortLinkAddress (todo 428)', () => {
  it.each(SHORT_ADDRESS_TABLE)('%s -> %s', (url, expected) => {
    expect(shortLinkAddress(url)).toBe(expected);
  });

  it.each(['javascript:alert(1)', 'https://user:pw@example.com/', '', null, 'not a url'])(
    'refuses %s',
    (url) => {
      expect(shortLinkAddress(url)).toBeNull();
    }
  );
});
