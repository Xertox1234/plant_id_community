import { existsSync, readFileSync, statSync } from 'node:fs';
import { dirname, relative, resolve } from 'node:path';
import { expect, it } from 'vitest';

/**
 * Reading a thread must not download the editor (audit F110). Follows every
 * STATIC runtime import from the page; a dynamic `import()` is the boundary
 * the editor sits behind.
 */
const SRC = [resolve(process.cwd(), 'src'), resolve(process.cwd(), 'web/src')].find(existsSync)!;

function resolveImport(from: string, spec: string): string | null {
  const base = spec.startsWith('@/')
    ? resolve(SRC, spec.slice(2))
    : spec.startsWith('.')
      ? resolve(dirname(from), spec)
      : null;
  if (!base) return null;
  const candidates = [base, `${base}.ts`, `${base}.tsx`, `${base}/index.ts`, `${base}/index.tsx`];
  return candidates.find((path) => existsSync(path) && statSync(path).isFile()) ?? null;
}

function staticImports(file: string): string[] {
  const code = readFileSync(file, 'utf8');
  return [
    ...code.matchAll(/^(?:import|export)\s(?!type\s)(?:[^'"();]*?\sfrom\s+)?['"]([^'"]+)['"]/gm),
  ].map((match) => match[1]);
}

it('the thread page reaches no TipTap or ProseMirror code by static import', () => {
  const start = resolve(SRC, 'pages/forum/ThreadDetailPage.tsx');
  const seen = new Set<string>();
  const queue = [start];
  const found: string[] = [];
  while (queue.length) {
    const file = queue.pop()!;
    if (seen.has(file)) continue;
    seen.add(file);
    if (!/\.tsx?$/.test(file)) continue;
    for (const spec of staticImports(file)) {
      if (/^(@tiptap\/|prosemirror-)/.test(spec)) found.push(`${relative(SRC, file)}: ${spec}`);
      const next = resolveImport(file, spec);
      if (next) queue.push(next);
    }
  }
  // The walk really walked: the page's own cards are in it.
  expect([...seen].some((file) => file.endsWith('PostCard.tsx'))).toBe(true);
  expect(found).toEqual([]);
});
