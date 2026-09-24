#!/usr/bin/env node
/**
 * Fail when a class token in `src/` names no class in the built CSS (todo 399).
 *
 * Tailwind 4 emits nothing for a utility it does not recognise: no build error,
 * no lint failure. An invented name such as `rounded-card` (todo 374) ships as a
 * silently missing style. This script runs after `vite build` and compares the
 * two sides:
 *
 * 1. The CSS side. It collects every class selector in `dist/assets/*.css` and
 *    UNESCAPES it, so `.focus\:ring-primary` becomes `focus:ring-primary` and
 *    `.\32 xl\:flex` becomes `2xl:flex`. Tokens are then matched by exact name.
 *    Matching the escaped form, never a stripped base name, is the point: a
 *    grep for a bare `.ring-primary` finds nothing although the class compiles
 *    (todo 396 was filed on that false negative). Classes written by hand in
 *    `index.css` (`gt-*`, `canopy-*`, `wf-*`, `forum-editor-content`,
 *    `ProseMirror`) are selectors too, so they need no allowlist.
 *
 * 2. The source side. It walks every string literal and template literal in
 *    `src/**\/*.{ts,tsx}` with the TypeScript parser, not only `className=`,
 *    because class strings also live in constants (`POST_CARD_PADDING`,
 *    `TILE_BOX.sm`) and in ternaries nested inside template literals. A token
 *    that touches a `${...}` interpolation (`bg-${tone}-500`) is a fragment,
 *    not a class name. It is counted and skipped, never checked.
 *
 * A literal in class position (a `className` / `class` attribute, or a
 * `classList.add/remove/toggle` argument, including each branch of a
 * conditional passed there) is all class names, so every token in it is
 * checked. Inside a class attribute, a value that is compared, indexed, tested
 * with `in`, or passed to a call (`tags.includes('featured')`) is not a class;
 * only a class-joining helper's arguments are (todo 402). Other strings may be
 * prose, so there a token is checked
 * only when it looks like a utility: it contains `-`, `:`, `/` or `[`, and the
 * part of its utility name before the first `-` (`rounded` in
 * `md:rounded-card`) is the start of some class the build does define. A token
 * that fails the lookup and is not in ALLOWLIST is reported as
 * `file:line token`, and the exit code is 1.
 *
 * Usage: `npm run check:classes` (builds first), or
 * `node scripts/check-tailwind-classes.mjs [--dist dist/assets] [--src src]`.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

/**
 * Tokens the check cannot resolve, each with the reason it is allowed.
 * Keep this short. A dead class belongs in a fix, not here.
 */
export const ALLOWLIST = new Map([
  ['gt-density', 'localStorage key in ThemeContext KEYS, not a class'],
  ['gt-mode', 'localStorage key in ThemeContext KEYS, not a class'],
]);

// One CSS escape: a hex code point with an optional trailing space, or any
// other escaped character.
const ESCAPE = String.raw`\\[0-9a-fA-F]{1,6} ?|\\[^\r\n0-9a-fA-F]`;
// A class selector. An identifier cannot start with a digit, which also keeps
// out numbers such as `.5` that are not selectors.
const CLASS_SELECTOR = new RegExp(
  String.raw`\.(-?(?:[A-Za-z_]|${ESCAPE})(?:[A-Za-z0-9_-]|${ESCAPE})*)`,
  'g'
);
// A rule prelude: the text before a `{`, back to the previous `{`, `}` or `;`.
// Escaped characters (`\{` in an arbitrary value) do not end it.
const PRELUDE = /((?:\\[\s\S]|[^{};\\])*)\{/g;

/** Decode CSS escapes: `focus\:ring-2` → `focus:ring-2`, `\32 xl` → `2xl`. */
export function unescapeCssIdent(raw) {
  return raw.replace(/\\([0-9a-fA-F]{1,6}) ?|\\([\s\S])/g, (_, hex, ch) =>
    hex ? String.fromCodePoint(parseInt(hex, 16)) : ch
  );
}

/** Every class name used in a selector of `css`, unescaped. */
export function classesInCss(css) {
  const known = new Set();
  const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, '');
  // At-rule preludes (`@media (width>=48rem)`) go through the same match; they
  // hold no `.identifier`, since a number such as `.5` cannot start one.
  for (const [, prelude] of withoutComments.matchAll(PRELUDE)) {
    // A quoted attribute value such as [href$=".pdf"] is not a selector.
    const selector = prelude.replace(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/g, '""');
    for (const [, name] of selector.matchAll(CLASS_SELECTOR)) {
      known.add(unescapeCssIdent(name));
    }
  }
  return known;
}

/**
 * The utility part of a token, without its variants or `!` / `-` modifiers:
 * `md:hover:-mt-2` → `mt-2`. A `:` inside `[...]` or `(...)` is part of an
 * arbitrary value, not a variant separator.
 */
export function utilityRoot(token) {
  let depth = 0;
  let cut = -1;
  for (let i = 0; i < token.length; i++) {
    const ch = token[i];
    if (ch === '[' || ch === '(') depth++;
    else if (ch === ']' || ch === ')') depth--;
    else if (ch === ':' && depth === 0) cut = i;
  }
  return token
    .slice(cut + 1)
    .replace(/^!|!$/g, '')
    .replace(/^-/, '');
}

/** The first segment of a utility name: `rounded-card` → `rounded`. */
export function utilityHead(root) {
  return root.split('-')[0];
}

/** The heads of every known class: the vocabulary a token must start with. */
export function knownHeads(known) {
  const heads = new Set();
  for (const name of known) heads.add(utilityHead(utilityRoot(name)));
  return heads;
}

/**
 * The tokens of one literal piece. `openStart` / `openEnd` say whether the
 * piece touches a `${...}` on that side. A token glued to an interpolation is a
 * fragment of a dynamic name, so it goes to `fragments` instead.
 */
export function splitPiece(text, { openStart = false, openEnd = false } = {}) {
  const tokens = text.split(/\s+/).filter(Boolean);
  const fragments = [];
  if (openStart && tokens.length && !/^\s/.test(text)) fragments.push(tokens.shift());
  if (openEnd && tokens.length && !/\s$/.test(text)) fragments.push(tokens.pop());
  return { tokens, fragments };
}

const CLASS_ATTRIBUTE = /^(class|className)$|ClassName$/;

function insideClassAttribute(node) {
  for (let n = node.parent; n; n = n.parent) {
    if (ts.isJsxAttribute(n)) return CLASS_ATTRIBUTE.test(n.name.getText());
  }
  return false;
}

function isDirectCallArgument(node) {
  const parent = node.parent;
  return (
    (ts.isStringLiteral(node) ||
      ts.isNoSubstitutionTemplateLiteral(node) ||
      ts.isTemplateExpression(node)) &&
    parent !== undefined &&
    (ts.isCallExpression(parent) || ts.isNewExpression(parent)) &&
    (parent.arguments ?? []).includes(node)
  );
}

const CLASS_LIST_METHOD = /^(add|remove|toggle|replace|contains)$/;

/**
 * Climb from a literal to the expression that stands for it: through
 * parentheses, either branch of a conditional (not its condition), and either
 * side of `||` / `??`. In `on ? 'a' : ('b' || 'c')` every literal is a value
 * the whole expression can take; the `on` test is not.
 */
function valueExpression(node) {
  let n = node;
  for (let parent = n.parent; parent; parent = n.parent) {
    const alternative =
      ts.isParenthesizedExpression(parent) ||
      (ts.isConditionalExpression(parent) && parent.condition !== n) ||
      (ts.isBinaryExpression(parent) &&
        (parent.operatorToken.kind === ts.SyntaxKind.BarBarToken ||
          parent.operatorToken.kind === ts.SyntaxKind.QuestionQuestionToken));
    if (!alternative) break;
    n = parent;
  }
  return n;
}

/**
 * `el.classList.add('canopy-flash')`: the argument is a class name, and so is
 * each literal the argument can evaluate to (`add(on ? 'a' : 'b')`).
 */
function isClassListArgument(node) {
  const arg = valueExpression(node);
  const call = arg.parent;
  if (!call || !ts.isCallExpression(call) || !call.arguments.includes(arg)) return false;
  const method = call.expression;
  return (
    ts.isPropertyAccessExpression(method) &&
    CLASS_LIST_METHOD.test(method.name.text) &&
    ts.isPropertyAccessExpression(method.expression) &&
    method.expression.name.text === 'classList'
  );
}

/**
 * Calls whose arguments are class names. The repo has none today; `clsx`-style
 * helpers are listed so adding one does not silently stop the check.
 */
const CLASS_JOIN_HELPERS = /^(clsx|cn|cx|classNames|classnames|twMerge)$/;

/** Whether a call joins class names: a helper above, or `[...].join(...)`. */
function isClassJoinCall(call) {
  const callee = call.expression;
  if (ts.isIdentifier(callee)) return CLASS_JOIN_HELPERS.test(callee.text);
  return (
    ts.isPropertyAccessExpression(callee) &&
    callee.name.text === 'join' &&
    ts.isArrayLiteralExpression(callee.expression)
  );
}

/**
 * Whether a literal is (a branch of) an interpolation glued to the text around
 * it, as `'text'` is in `` `language-${lang || 'text'}` ``. Such a literal is
 * part of a dynamic name, not a class name of its own.
 */
function inGluedInterpolation(node) {
  let n = node;
  let parent = n.parent;
  while (
    parent &&
    (ts.isParenthesizedExpression(parent) ||
      ts.isBinaryExpression(parent) ||
      (ts.isConditionalExpression(parent) && parent.condition !== n))
  ) {
    n = parent;
    parent = n.parent;
  }
  if (!parent || !ts.isTemplateSpan(parent) || parent.expression !== n) return false;
  const template = parent.parent;
  const i = template.templateSpans.indexOf(parent);
  const before = i === 0 ? template.head.text : template.templateSpans[i - 1].literal.text;
  const after = parent.literal.text;
  return (before !== '' && !/\s$/.test(before)) || (after !== '' && !/^\s/.test(after));
}

/**
 * Whether a literal is used as a value to compare, index or look up with, not
 * as classes, inside a className expression: `status === 'active'`,
 * `styles['primary']`, `'foo' in obj`, or an element of an array a method is
 * called on (`['a', 'b'].includes(x)`). `[...].join(' ')` builds a class
 * string, so its elements are still classes.
 */
function isComparedOrKey(node) {
  const parent = node.parent;
  if (ts.isElementAccessExpression(parent)) return parent.argumentExpression === node;
  if (ts.isCaseClause(parent)) return true;
  if (ts.isArrayLiteralExpression(parent)) {
    const access = parent.parent;
    return (
      access !== undefined &&
      ts.isPropertyAccessExpression(access) &&
      access.expression === parent &&
      access.parent !== undefined &&
      ts.isCallExpression(access.parent) &&
      access.parent.expression === access &&
      !isClassJoinCall(access.parent)
    );
  }
  if (!ts.isBinaryExpression(parent)) return false;
  const op = parent.operatorToken.kind;
  if (op === ts.SyntaxKind.InKeyword) return parent.left === node;
  return (
    op === ts.SyntaxKind.EqualsEqualsEqualsToken ||
    op === ts.SyntaxKind.ExclamationEqualsEqualsToken ||
    op === ts.SyntaxKind.EqualsEqualsToken ||
    op === ts.SyntaxKind.ExclamationEqualsToken
  );
}

/**
 * Every whitespace-separated token in the string and template literals of a
 * file, except those in a non-class JSX attribute, or passed straight to a
 * call that is not `classList.*`. A token is `strict` when the literal is in
 * class position (a class attribute or a `classList` call): every such token
 * is a class name, so it is checked whatever it looks like.
 */
export function literalTokens(fileName, sourceText) {
  const source = ts.createSourceFile(fileName, sourceText, ts.ScriptTarget.Latest, true);
  const tokens = [];
  const fragments = [];
  const add = (node, text, sides, strict) => {
    const line = source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;
    const piece = splitPiece(text, sides);
    for (const token of piece.tokens) tokens.push({ token, line, strict });
    for (const token of piece.fragments) fragments.push({ token, line });
  };
  const visit = (node) => {
    // Module paths are not class names.
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) return;
    // Other attributes hold ids, test ids and labels (`id="group-members"`).
    if (ts.isJsxAttribute(node) && !CLASS_ATTRIBUTE.test(node.name.getText(source))) return;
    const classList = isClassListArgument(node);
    // A literal passed straight to any other call is a log message, a selector
    // or a storage key (`querySelector('[data-autofocus]')`), and inside a
    // class attribute it is an argument (`tags.includes('featured')`,
    // `variantClass('primary')`), not a class. Only a class-joining helper's
    // arguments are classes. Other arguments are still walked, since a
    // `.map()` callback holds JSX.
    if (isDirectCallArgument(node) && !classList && !isClassJoinCall(node.parent)) return;
    const isLiteral =
      ts.isStringLiteral(node) ||
      ts.isNoSubstitutionTemplateLiteral(node) ||
      ts.isTemplateExpression(node);
    const strict =
      isLiteral && (classList || (insideClassAttribute(node) && !isComparedOrKey(node)));
    if (isLiteral && inGluedInterpolation(node)) {
      // `language-${lang || 'text'}`: the literal is part of a dynamic name.
      const line = source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;
      fragments.push({ token: node.getText(source), line });
      return;
    }
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
      add(node, node.text, {}, strict);
    } else if (ts.isTemplateExpression(node)) {
      add(node.head, node.head.text, { openEnd: true }, strict);
      node.templateSpans.forEach((span, i) => {
        const last = i === node.templateSpans.length - 1;
        add(span.literal, span.literal.text, { openStart: true, openEnd: !last }, strict);
      });
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return { tokens, fragments };
}

/**
 * Whether a token should be looked up at all. A token in class position always
 * is. Any other string may be prose, so it must look like a utility: contain
 * `-`, `:`, `/` or `[`, and start with the head of some built class. Returns
 * the token (with trailing prose punctuation removed), or null.
 */
export function asCandidate(token, heads, strict = false) {
  if (strict) return token;
  const cleaned = token.replace(/[.,;]+$/, '');
  if (!/[-:/[]/.test(cleaned)) return null;
  const root = utilityRoot(cleaned);
  // An arbitrary property such as `[mask-type:luminance]`. A bracketed word
  // with no `property:` inside (`[AuthContext]`, `[deleted]`) is prose.
  if (/^\[[a-z-]+:.+\]$/.test(root)) return cleaned;
  return heads.has(utilityHead(root)) ? cleaned : null;
}

/** Check source files against a set of known classes. */
export function findUnknownClasses(files, known, allowlist = ALLOWLIST) {
  const heads = knownHeads(known);
  const hits = [];
  let checked = 0;
  let fragments = 0;
  for (const { fileName, text } of files) {
    const found = literalTokens(fileName, text);
    fragments += found.fragments.length;
    for (const { token, line, strict } of found.tokens) {
      const candidate = asCandidate(token, heads, strict);
      if (candidate === null) continue;
      checked++;
      if (known.has(candidate) || allowlist.has(candidate)) continue;
      hits.push({ fileName, line, token: candidate });
    }
  }
  return { hits, checked, fragments };
}

function sourceFiles(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      // Test fixtures carry deliberate junk class names.
      if (entry.name === 'tests' || entry.name === '__tests__') continue;
      out.push(...sourceFiles(full));
    } else if (/\.tsx?$/.test(entry.name) && !/\.(test|spec|d)\.tsx?$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

function main(argv) {
  const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const option = (name, fallback) => {
    const i = argv.indexOf(name);
    return path.resolve(webRoot, i === -1 ? fallback : argv[i + 1]);
  };
  const distDir = option('--dist', 'dist/assets');
  const srcDir = option('--src', 'src');

  // A missing build must fail, not pass with nothing to compare against.
  const cssFiles = fs.existsSync(distDir)
    ? fs.readdirSync(distDir).filter((name) => name.endsWith('.css'))
    : [];
  if (cssFiles.length === 0) {
    console.error(`check-tailwind-classes: no CSS in ${distDir}. Run \`vite build\` first.`);
    return 2;
  }
  const known = new Set();
  for (const name of cssFiles) {
    for (const cls of classesInCss(fs.readFileSync(path.join(distDir, name), 'utf8'))) {
      known.add(cls);
    }
  }

  const files = sourceFiles(srcDir).map((file) => ({
    fileName: path.relative(webRoot, file),
    text: fs.readFileSync(file, 'utf8'),
  }));
  const { hits, checked, fragments } = findUnknownClasses(files, known);
  if (checked === 0) {
    console.error(`check-tailwind-classes: no class tokens found under ${srcDir}.`);
    return 2;
  }

  console.log(
    `check-tailwind-classes: ${files.length} files, ${checked} class tokens checked ` +
      `against ${known.size} built classes; ${fragments} dynamic fragments skipped.`
  );
  if (hits.length === 0) return 0;
  console.error(`\n${hits.length} class token(s) are not defined in the built CSS:`);
  for (const { fileName, line, token } of hits) console.error(`  ${fileName}:${line}  ${token}`);
  console.error(
    '\nTailwind emits nothing for a name it does not recognise. Use a real utility ' +
      'or token, or add the name to ALLOWLIST in this script with the reason.'
  );
  return 1;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = main(process.argv.slice(2));
}
