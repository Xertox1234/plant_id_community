#!/usr/bin/env node
/**
 * Publish guard for the legal documents (Plan A, task 5).
 *
 * With LEGAL_PUBLISH=1, exits 1 and lists every file under
 * src/content/legal/ that still holds a `[[PLACEHOLDER]]` or the
 * "DRAFT — pending legal review" line. Otherwise exits 0 silently.
 */
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const DRAFT_LINE = 'DRAFT — pending legal review';

/** @param {{ name: string, text: string }[]} files */
export function findUnpublishable(files) {
  return files
    .filter(({ text }) => text.includes('[[') || text.includes(DRAFT_LINE))
    .map(({ name }) => name);
}

function main() {
  if (process.env.LEGAL_PUBLISH !== '1') return;
  const dir = fileURLToPath(new URL('../src/content/legal/', import.meta.url));
  const files = readdirSync(dir)
    .filter((n) => n.endsWith('.md'))
    .sort()
    .map((n) => ({ name: n, text: readFileSync(path.join(dir, n), 'utf8') }));
  const bad = findUnpublishable(files);
  if (bad.length > 0) {
    console.error('Legal documents are not publishable (placeholder or DRAFT line left):');
    for (const n of bad) console.error(`  ${n}`);
    process.exit(1);
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  main();
}
