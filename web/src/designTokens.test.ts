/**
 * Guards for the body-text scale (todo 351): the token layer must keep every
 * rung with a paired line-height, and no `text-[NNpx]` may come back under
 * src/ outside the recorded exceptions. Both checks read the files directly
 * so a future sweep cannot silently regress the design system.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = join(__dirname);
const RUNGS = ['micro', 'meta', 'body-sm', 'body', 'body-lg', 'lead', 'hero'];

/** file (relative to src/) → arbitrary sizes that are allowed to stay. */
const RECORDED_EXCEPTIONS: Record<string, string[]> = {
  'layouts/AppShell.tsx': ['9.5px'], // wordmark micro-label, tracked uppercase brand mark
  'components/ui/StatCard.tsx': ['22px'], // the mono figure — not body text
  'components/StreamFieldRenderer.tsx': ['24px', '19px', '19px'], // article h2/h3 scale
};

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.tsx$/.test(name) && !/\.test\.tsx$/.test(name)) out.push(full);
  }
  return out;
}

describe('body-text scale tokens (todo 351)', () => {
  const css = readFileSync(join(SRC, 'index.css'), 'utf8');

  it.each(RUNGS)('declares --text-%s with a paired line-height', (rung) => {
    expect(css).toMatch(new RegExp(`--text-${rung}:\\s*[0-9.]+px;`));
    expect(css).toMatch(new RegExp(`--text-${rung}--line-height:\\s*[0-9.]+;`));
  });

  it('has no arbitrary text-[NNpx] utilities outside the recorded exceptions', () => {
    const offenders: string[] = [];
    for (const file of walk(SRC)) {
      const rel = relative(SRC, file);
      const found = [...readFileSync(file, 'utf8').matchAll(/text-\[([0-9.]+px)\]/g)].map(
        (m) => m[1]
      );
      const allowed = [...(RECORDED_EXCEPTIONS[rel] ?? [])];
      for (const size of found) {
        const i = allowed.indexOf(size);
        if (i === -1) offenders.push(`${rel}: text-[${size}]`);
        else allowed.splice(i, 1);
      }
    }
    expect(offenders).toEqual([]);
  });
});
