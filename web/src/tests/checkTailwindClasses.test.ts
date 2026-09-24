/**
 * Tests for scripts/check-tailwind-classes.mjs, the CI guard that fails on a
 * class token the built CSS does not define (todo 399). The guard exists
 * because a "does this class compile?" check was itself a false negative once
 * (todo 396), so these pin both directions: invented names fail, real
 * variant-prefixed names pass.
 */
import { describe, expect, it } from 'vitest';
import {
  classesInCss,
  findUnknownClasses,
  unescapeCssIdent,
} from '../../scripts/check-tailwind-classes.mjs';

// Shaped like Tailwind 4 output: variants escaped, a leading digit hex-escaped.
const BUILT_CSS = `
/* .commented-out { color: red } */
.p-2{padding:.5rem}
.rounded-sm{border-radius:10px}
.bg-surface-2{background:var(--x)}
.bg-black\\/50{background:#0008}
.max-h-\\[80vh\\]{max-height:80vh}
.focus\\:ring-primary:focus{--tw-ring-color:var(--gt-primary)}
.focus-within\\:ring-2:focus-within{--tw-ring-shadow:0 0 0 2px}
@media (width>=96rem){.\\32 xl\\:flex{display:flex}}
.group-hover\\:underline:is(:where(.group):hover *){text-decoration:underline}
.gt-h1{font-size:2rem}
a[href$=".pdf"]{color:red}
`;

const known = classesInCss(BUILT_CSS);

function check(source: string, allowlist = new Map<string, string>()) {
  return findUnknownClasses([{ fileName: 'Fixture.tsx', text: source }], known, allowlist);
}

function flagged(source: string, allowlist?: Map<string, string>) {
  return check(source, allowlist).hits.map((hit: { token: string }) => hit.token);
}

describe('unescapeCssIdent', () => {
  it('decodes the escapes Tailwind 4 emits', () => {
    expect(unescapeCssIdent('focus\\:ring-primary')).toBe('focus:ring-primary');
    expect(unescapeCssIdent('bg-black\\/50')).toBe('bg-black/50');
    expect(unescapeCssIdent('max-h-\\[80vh\\]')).toBe('max-h-[80vh]');
    expect(unescapeCssIdent('\\32 xl\\:flex')).toBe('2xl:flex');
  });
});

describe('classesInCss', () => {
  it('collects every class selector, unescaped', () => {
    for (const name of [
      'focus:ring-primary',
      'focus-within:ring-2',
      'bg-black/50',
      'max-h-[80vh]',
      '2xl:flex',
      'group',
      'group-hover:underline',
      'gt-h1',
    ]) {
      expect(known.has(name)).toBe(true);
    }
  });

  it('ignores comments, declarations and quoted attribute values', () => {
    expect(known.has('commented-out')).toBe(false);
    expect(known.has('pdf')).toBe(false);
    expect(known.has('5rem')).toBe(false);
  });
});

describe('findUnknownClasses', () => {
  it('flags an invented utility, with or without a variant', () => {
    expect(flagged('<div className="rounded-card md:rounded-card p-2" />')).toEqual([
      'rounded-card',
      'md:rounded-card',
    ]);
  });

  it('passes real variant-prefixed and escaped classes', () => {
    const source =
      '<div className="focus:ring-primary focus-within:ring-2 bg-black/50 max-h-[80vh] 2xl:flex group group-hover:underline gt-h1" />';
    expect(flagged(source)).toEqual([]);
    // All eight looked up: in a class attribute even a bare `group` is checked.
    expect(check(source).checked).toBe(8);
  });

  it('checks every token in a class attribute, even with no known prefix', () => {
    // Review round 1: `prose` passed because only `max-w-prose` was built,
    // and a typo in the first segment passed because it matched no family.
    expect(flagged('<div className="prose prose-sm shadow-card roundd-sm p-2" />')).toEqual([
      'prose',
      'prose-sm',
      'shadow-card',
      'roundd-sm',
    ]);
  });

  it('checks classList arguments', () => {
    expect(flagged("el.classList.add('rounded-card'); el.classList.remove('p-2');")).toEqual([
      'rounded-card',
    ]);
  });

  it('does not check compared values or keys inside a class attribute', () => {
    const source =
      "<div className={`p-2 ${tab === 'active' ? 'rounded-sm' : ''} ${TONES['warm']}`} />";
    expect(flagged(source)).toEqual([]);
  });

  // Todo 402: a literal passed to a call inside a class attribute is an
  // argument, not a class. Each probe used to fail CI on the token shown.
  it.each([
    ["tags.includes('featured') ? 'p-2' : ''", 'featured'],
    ["href.startsWith('/forum') ? 'p-2' : 'rounded-sm'", '/forum'],
    ["variantClass('primary')", 'primary'],
    ["['a', 'b'].includes(x) ? 'p-2' : ''", 'a'],
    ["'foo' in obj ? 'p-2' : ''", 'foo'],
  ])('does not check %s as classes (flagged %s)', (expression) => {
    expect(flagged(`<div className={${expression}} />`)).toEqual([]);
  });

  it('still checks the classes around a call inside a class attribute', () => {
    expect(
      flagged("<div className={tags.includes('featured') ? 'rounded-card' : 'p-2'} />")
    ).toEqual(['rounded-card']);
  });

  it('checks the arguments of a class-joining helper', () => {
    // `prose` has no `-`, so only the strict class-position check flags it.
    expect(flagged("<div className={clsx('prose', on && 'p-2')} />")).toEqual(['prose']);
  });

  it('checks the elements of an array joined into a class string', () => {
    expect(flagged("<div className={['p-2', 'prose'].join(' ')} />")).toEqual(['prose']);
  });

  it('checks the literals a classList argument can evaluate to', () => {
    expect(flagged("el.classList.add(on ? 'bogus-x' : 'p-2');")).toEqual(['bogus-x']);
    expect(flagged("el.classList.add((mode ?? 'bogus-y') || 'p-2');")).toEqual(['bogus-y']);
  });

  it('does not check a classList conditional test as a class', () => {
    expect(flagged("el.classList.add(mode === 'darkish' ? 'p-2' : 'rounded-sm');")).toEqual([]);
  });

  it('treats a literal inside a glued interpolation as a fragment', () => {
    const result = check("<code className={`language-${lang || 'text'}`} />");
    expect(result.hits).toEqual([]);
    expect(result.fragments).toBe(2);
  });

  it('checks both branches of a ternary inside a template literal', () => {
    const source =
      "<button className={`p-2 ${busy ? 'rounded-card' : 'rounded-sm'} bg-surface-2`} />";
    expect(flagged(source)).toEqual(['rounded-card']);
  });

  it('checks class strings held in constants', () => {
    expect(flagged("const CARD = { sm: 'p-2 rounded-card md:rounded-card' };")).toEqual([
      'rounded-card',
      'md:rounded-card',
    ]);
  });

  it('checks JSX inside a call argument such as a .map callback', () => {
    expect(flagged('items.map((i) => <li className="rounded-card" />);')).toEqual(['rounded-card']);
  });

  it('skips a token glued to an interpolation instead of checking it', () => {
    const result = check('<div className={`p-2 bg-${tone}-500`} />');
    expect(result.hits).toEqual([]);
    expect(result.fragments).toBe(2);
  });

  it('ignores ids, test ids and strings passed straight to a call', () => {
    const source = [
      '<input id="rounded-card" data-testid="rounded-card" />;',
      "localStorage.getItem('rounded-card');",
    ].join('\n');
    expect(flagged(source)).toEqual([]);
  });

  it('ignores prose that does not look like a utility', () => {
    expect(flagged("const label = 'Save to my collection, well-known [AuthContext]';")).toEqual([]);
  });

  it('accepts an allowlisted token', () => {
    const allowlist = new Map([['rounded-card', 'test reason']]);
    expect(flagged('<div className="rounded-card" />', allowlist)).toEqual([]);
  });
});
