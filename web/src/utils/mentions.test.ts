import { describe, it, expect } from 'vitest';
import { highlightMentions } from './mentions';

describe('highlightMentions', () => {
  it('wraps a mention in a styled span', () => {
    expect(highlightMentions('<p>Thanks @bob_botanist!</p>')).toBe(
      '<p>Thanks <span class="text-primary font-medium">@bob_botanist</span>!</p>'
    );
  });

  it('ignores email addresses', () => {
    expect(highlightMentions('<p>mail me at jdoe@example.com</p>')).toBe(
      '<p>mail me at jdoe@example.com</p>'
    );
  });

  it('does not touch text inside links or code', () => {
    const html = '<p><a href="https://x.test">@alice</a> and <code>@beta</code></p>';
    expect(highlightMentions(html)).toBe(html);
  });

  it('handles multiple mentions in one text node', () => {
    expect(highlightMentions('<p>@a and @b</p>')).toBe(
      '<p><span class="text-primary font-medium">@a</span> and <span class="text-primary font-medium">@b</span></p>'
    );
  });
});
