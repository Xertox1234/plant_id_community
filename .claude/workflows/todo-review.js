export const meta = {
  name: 'todo-review',
  description: 'Todo sweep Stage C: review each open PR with fresh-context reviewers; in round 1, repair blocking findings in the PR worktree and re-verify',
  whenToUse: 'Called by the completing-todos engine with args {round, prs} from `state.py review-args`',
  phases: [
    { title: 'Review', detail: 'every PR: three bug-lens reviewers, plus every domain reviewer the orchestrator routes to' },
    { title: 'Refute', detail: 'two skeptics per critical/high finding; it stops blocking only if both refute it' },
    { title: 'Repair', detail: 'round 1 only: todo-worker in the PR worktree, then todo-verifier' },
  ],
}

// No subagent can spawn subagents (pilot P8: "no Agent tool available"), so every fan-out a review
// needs is an agent() call here. The orchestrator only routes; this script dispatches its reviewers.
const DOMAIN_REVIEWERS = ['django-drf-reviewer', 'wagtail-reviewer', 'react-typescript-reviewer',
  'flutter-dart-reviewer', 'flutter-firebase-reviewer', 'firebase-cloudfunction-reviewer',
  'celery-async-reviewer', 'cross-cutting-reviewer']

const ROUTING = {
  type: 'object',
  properties: {
    agents_to_invoke: { type: 'array', items: { type: 'string', enum: DOMAIN_REVIEWERS }, maxItems: 8 },
    routing_reasons: { type: 'string', maxLength: 2000 },
  },
  required: ['agents_to_invoke', 'routing_reasons'],
}

const REFUTATION = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean' },
    reason: { type: 'string', maxLength: 600 },  // headroom over the prompt's 300, as for FINDINGS
  },
  required: ['refuted', 'reason'],
}

// The path rules of code-review-orchestrator.md's routing table, applied in code to the file list
// state.py computed (todo 478). Every reviewer a row names is dispatched whatever the router says;
// the router adds only what paths can't decide (the wagtail content grep). `row` is the table's
// pattern cell verbatim: test_workflows.js fails if the table and this list drift apart.
const seg = (f, re) => f.split('/').some(s => re.test(s))
const MOBILE = 'plant_community_mobile/'
const ROUTES = [
  { row: '`apps/**/*.py` (excluding blog/wagtail)', agents: ['django-drf-reviewer'],
    test: f => /(^|\/)apps\/.+\.py$/.test(f) && !/(^|\/)apps\/blog\//.test(f) },
  { row: '`apps/blog/**` OR any `.py` file matching `grep -l "import wagtail\\|from wagtail\\|from .models import.*Page"`',
    agents: ['wagtail-reviewer'], test: f => /(^|\/)apps\/blog\//.test(f) },
  { row: '`web/src/**/*.tsx` or `web/src/**/*.ts`', agents: ['react-typescript-reviewer'],
    test: f => /^web\/src\/.+\.tsx?$/.test(f) },
  { row: '`plant_community_mobile/**/*.dart`', agents: ['flutter-dart-reviewer'],
    test: f => /^plant_community_mobile\/.+\.dart$/.test(f) },
  // Any path segment, not just the file name: a lib/auth/ directory holds auth code too.
  { row: '`plant_community_mobile/**/firebase*` or `plant_community_mobile/**/auth*`', agents: ['flutter-firebase-reviewer'],
    test: f => f.startsWith(MOBILE) && seg(f.slice(MOBILE.length), /^(firebase|auth)/) },
  { row: '`firebase/**` or `*.rules`', agents: ['flutter-firebase-reviewer', 'cross-cutting-reviewer'],
    test: f => f.startsWith('firebase/') || f.endsWith('.rules') },
  { row: '`functions/**`', agents: ['firebase-cloudfunction-reviewer'], test: f => /(^|\/)functions\//.test(f) },
  { row: '`**/tasks.py` or `**/celery*.py` or `**/beat*.py`', agents: ['celery-async-reviewer'],
    test: f => /(^|\/)(tasks\.py|celery[^/]*\.py|beat[^/]*\.py)$/.test(f) },
  { row: '`**/serializers.py` or `**/api/**`', agents: ['cross-cutting-reviewer'],
    test: f => /(^|\/)serializers\.py$/.test(f) || /(^|\/)api\//.test(f) },
  { row: '`**/tests/**` or `**/test_*.py` or `**/*.test.ts`', agents: ['cross-cutting-reviewer'],
    test: f => /(^|\/)tests\//.test(f) || /(^|\/)test_[^/]*\.py$/.test(f) || /\.test\.tsx?$/.test(f) },
  { row: '`**/permissions.py`, `**/auth*.py`, `**/upload*.py`, `**/*token*.py`, `**/*secret*.py` OR `grep -l "SECRET\\|API_KEY\\|upload\\|permission" <changed_py_files>`',
    agents: ['cross-cutting-reviewer'], test: f => f.endsWith('.py') },
  { row: 'Any `.py` file', agents: ['cross-cutting-reviewer'], test: f => f.endsWith('.py') },
]

// The files each reviewer's rows match: the file list for a reviewer only the path rules chose.
function routeFiles(files) {
  const byAgent = new Map()
  for (const r of ROUTES) {
    for (const f of files.filter(r.test)) {
      for (const id of r.agents) byAgent.set(id, [...new Set([...(byAgent.get(id) || []), f])])
    }
  }
  return byAgent
}

// Each lens is a separate fresh-context finder over the whole diff: one reader misses what a
// differently-primed reader catches.
const LENSES = [
  { key: 'correctness', focus: 'logic errors, wrong conditions, off-by-one and edge cases (empty, None, ' +
      'unicode, concurrent calls), error paths that swallow or mis-report failures, and regressions in ' +
      'callers of anything the diff changed' },
  { key: 'security-data', focus: 'authentication and permission gaps, input validation and injection, ' +
      'secrets or PII exposure, migrations that lose or corrupt data, and destructive operations without a guard' },
  { key: 'contracts-tests', focus: 'API, serializer, schema and cache-key contracts that web or mobile ' +
      'callers rely on, state, caching, idempotency and retry behaviour, and tests that do not actually ' +
      'exercise the change or were weakened to pass' },
]

const FINDINGS = {
  type: 'object',
  properties: {
    reviewed_range: { type: 'string', maxLength: 200 },
    findings: {
      type: 'array',
      maxItems: 40,
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          file: { type: 'string' },
          line: { type: 'integer' },
          // Headroom over the prompt's 300: a domain reviewer that overshot 300 five times in a row
          // died on the schema retry cap (live run, PR #873), and a dead reviewer forces a rerun.
          summary: { type: 'string', maxLength: 600 },
          suggested_fix: { type: 'string', maxLength: 600 },
        },
        required: ['severity', 'file', 'line', 'summary', 'suggested_fix'],
      },
    },
  },
  required: ['reviewed_range', 'findings'],
}

const WORKER = {
  type: 'object',
  properties: {
    ids: { type: 'array', items: { type: 'string' } },
    status: { type: 'string', enum: ['staged', 'blocked', 'failed', 'no_change'] },
    worktree: { type: 'string' },
    branch: { type: 'string' },
    tree_id: { type: 'string' },
    files_changed: { type: 'array', items: { type: 'string' }, maxItems: 200 },
    ac_file: { type: 'string' },
    tests_run: { type: 'array', items: { type: 'string', maxLength: 300 }, maxItems: 30 },
    blockers: { type: 'string', maxLength: 300 },
    discoveries: { type: 'string', maxLength: 300 },
    summary: { type: 'string', maxLength: 600 },
  },
  required: ['ids', 'status', 'worktree', 'branch', 'tree_id', 'files_changed', 'ac_file', 'tests_run',
    'blockers', 'discoveries', 'summary'],
}

const VERDICT = {
  type: 'object',
  properties: {
    ids: { type: 'array', items: { type: 'string' } },
    verdict: { type: 'string', enum: ['pass', 'fail'] },
    ac: {
      type: 'array',
      maxItems: 60,
      items: {
        type: 'object',
        properties: {
          todo: { type: 'string' },
          index: { type: 'integer' },
          verified: { type: 'boolean' },
          note: { type: 'string', maxLength: 200 },
        },
        required: ['todo', 'index', 'verified', 'note'],
      },
    },
    test_edits_flagged: { type: 'array', items: { type: 'string' }, maxItems: 30 },
    commands_rerun: { type: 'integer' },
    tree_id_before: { type: 'string' },
    tree_id_after: { type: 'string' },
    clean_after: { type: 'boolean' },
    reasons: { type: 'array', items: { type: 'string', maxLength: 200 }, maxItems: 10 },
  },
  required: ['ids', 'verdict', 'ac', 'test_edits_flagged', 'commands_rerun', 'tree_id_before', 'tree_id_after',
    'clean_after', 'reasons'],
}

const round = args && args.round
const prs = (args && args.prs) || []
const BLOCKING = new Set(['critical', 'high'])

function diffRange(p) {
  return `/usr/bin/git -C '${p.worktree}' diff origin/main...HEAD`
}

// Land ran before review (spec §5.3): TODO_PATHS are the archived paths, ORIGIN_PATHS the pending ones.
function pathLines(p) {
  return [`TODO_PATHS: ${p.todo_paths.join(', ')}`, `ORIGIN_PATHS: ${p.origin_paths.join(', ')}`]
}

const LANDED = 'Land has already flipped the verified boxes to `[x]` and archived each todo (TODO_PATHS); ' +
  'ORIGIN_PATHS are the pending paths at the merge-base.'

const SEVERITY = 'critical/high = would ship a bug, a security hole or data loss; medium = a real but contained ' +
  'defect; style and nits are low. Keep each summary and suggested_fix under 300 characters.'

function bugPrompt(p, lens) {
  return [
    `Review the change for todo group ${p.group} (${p.ids.join(', ')}), round ${round}. It is open as PR #${p.pr}; ` +
      'do not use gh or fetch the PR — review the local diff only.',
    `Branch ${p.branch}, worktree ${p.worktree}. The change is exactly: ${diffRange(p)}`,
    `Your lens is ${lens.key}: ${lens.focus}. Other reviewers cover the other lenses, so go deep on this one ` +
      'and read the code around each hunk, not just the hunk.',
    `Set reviewed_range to "git diff origin/main...HEAD (${lens.key})". ${SEVERITY}`,
    p.test_edits.length ? `The verifier flagged edits to existing tests: ${p.test_edits.join(', ')}. Check each is justified.` : '',
    'Do not post comments, commit or push. Return FINDINGS.',
  ].filter(Boolean).join('\n')
}

function routingPrompt(p) {
  return [
    `Phase 1 (triage) only, for todo group ${p.group} (open as PR #${p.pr}), round ${round}. Do not use gh.`,
    `The change is in worktree ${p.worktree}, not the main checkout. These are its changed files (worktree-relative); ` +
      `do not run \`git diff\` to find them, and run any routing grep against '${p.worktree}/<path>':`,
    ...p.changed_files.map(f => `  - ${f}`),
    'Apply your routing table and return ROUTING: agents_to_invoke, and routing_reasons as one line per agent. ' +
      'The workflow dispatches the reviewers; do not review anything yourself.',
  ].join('\n')
}

function domainPrompt(p, id, files) {
  return [
    `Review these files for todo group ${p.group} (open as PR #${p.pr}), round ${round}. Report findings only for the files listed.`,
    `Batch label: todo-${p.group}-r${round} (${id})`,
    `The change is in worktree ${p.worktree}, NOT the main checkout: read every file as '${p.worktree}/<path>' and ` +
      `get the diff with ${diffRange(p)}. The main checkout holds a different version of these files.`,
    'Files:', ...files.map(f => `  - ${f}`),
    `Review against your checklist. ${SEVERITY} Do not use gh, edit, commit or push.`,
    `Return FINDINGS, not your usual JSON: description → summary, info → low, and reviewed_range ` +
      `"git diff origin/main...HEAD (${id})".`,
  ].join('\n')
}

function refutePrompt(p, f) {
  const claims = [f.summary, ...f.also]
  return [
    `Reviewers reported ${claims.length === 1 ? 'a' : claims.length} ${f.severity} finding(s) at ${f.file}:${f.line} ` +
      `in todo group ${p.group} (PR #${p.pr}). Try to refute them.`,
    `Worktree ${p.worktree}; the change is exactly: ${diffRange(p)}. Read the code, not just the hunk. Do not use gh.`,
    ...claims.map((c, i) => `${i + 1}. ${c}`),
    'These may be one bug in different words or different bugs on the same line; judge each. ' +
      'Set refuted=true only if you can show EVERY one is wrong: the code does not do that, the input cannot ' +
      'reach it, or something already handles it. If any holds, or you cannot tell, set refuted=false. Give the ' +
      'reason in under 300 characters.',
  ].join('\n')
}

function repairPrompt(p, blocking) {
  return ['MODE: repair', `RUN_ID: ${p.run_id}`, `WORKTREE: ${p.worktree}`, `SLOT: ${p.slot}`,
    `MAIN_ROOT: ${p.main_root}`, `EVIDENCE_DIR: ${p.evidence_dir}`, `IDS: ${p.ids.join(', ')}`, ...pathLines(p),
    'FINDINGS:', JSON.stringify(blocking, null, 1),
    `Fix only these findings. ${LANDED} Do not flip, uncheck or otherwise edit any box.`,
    'Then re-run every criterion except those already `[x]` at the merge-base (ORIGIN_PATHS) or re-pointed, and ' +
      'regenerate evidence for the criteria you re-ran; ac.json still has one entry for EVERY criterion ' +
      '(recreate EVIDENCE_DIR if it is missing).',
    'Return the WORKER record.'].join('\n')
}

function verifyPrompt(p, w) {
  return [
    'MODE: repair',
    `Verify todo group ${p.group} after a round-1 review repair.`,
    `IDS: ${p.ids.join(', ')}`,
    `WORKTREE: ${w.worktree}`, `SLOT: ${p.slot}`, `MAIN_ROOT: ${p.main_root}`,
    `AC_FILE: ${w.ac_file}`, ...pathLines(p),  // no tree id: state.evaluate compares it (todo 468)
    `${LANDED} Ignore \`[ ]\` vs \`[x]\` in the unchanged-criteria check. Every criterion that is not ` +
      'already-checked-at-merge-base or re-pointed must carry a non-empty `command`; re-run each yourself.',
    'Return the VERDICT record.',
  ].join('\n')
}

// Reviewers phrase the same bug differently, so blocking findings collapse by file and line: one
// representative (the most severe) carries the other phrasings in `also`, and all of them face the
// same refuters, who must refute every one.
function relPath(file, worktree) {
  const prefix = worktree.replace(/\/+$/, '') + '/'
  const rel = file.startsWith(prefix) ? file.slice(prefix.length) : file
  return rel.replace(/^\.\//, '')
}

function byLocation(findings, worktree) {
  const groups = new Map()
  for (const raw of findings) {
    const f = { ...raw, file: relPath(raw.file, worktree) }
    const key = JSON.stringify([f.file, f.line])
    const g = groups.get(key)
    if (!g) { groups.set(key, { ...f, also: [] }); continue }
    const [keep, other] = f.severity === 'critical' && g.severity !== 'critical' ? [{ ...f, also: g.also }, g] : [g, f]
    if (other.summary !== keep.summary && !keep.also.includes(other.summary)) keep.also.push(other.summary)
    groups.set(key, keep)
  }
  return [...groups.values()]
}

const results = await pipeline(
  prs,
  async p => {
    // Both lanes run for every size: the checklist lane is the pre-v2 review (orchestrator routing, then
    // every routed domain reviewer), and the bug lenses are the deep pass on top of it.
    const checklist = async () => {
      const routing = await agent(routingPrompt(p),
        { label: `route:${p.group}`, phase: 'Review', agentType: 'code-review-orchestrator', schema: ROUTING })
      if (!routing) return { routing: null, reviews: [] }
      // The path rules decide who must review; the router can only add to them, never remove.
      const byAgent = routeFiles(p.changed_files)
      const ids = [...new Set([...byAgent.keys(), ...routing.agents_to_invoke])]
      const floor_added = [...byAgent.keys()].filter(id => !routing.agents_to_invoke.includes(id))
      if (floor_added.length) log(`${p.group}: path rules added ${floor_added.join(', ')} the router left out`)
      // A router pick may rest on file contents (a wagtail import outside apps/blog/), which the path rules
      // can't see, so a reviewer the router chose gets every file; only floor-added ones get their subset.
      const filesFor = id => (routing.agents_to_invoke.includes(id) ? p.changed_files : byAgent.get(id))
      const reviews = await parallel(ids.map(id => () => agent(domainPrompt(p, id, filesFor(id)),
        { label: `${id}:${p.group}`, phase: 'Review', agentType: id, schema: FINDINGS })
        .then(r => r && { ...r, reviewer: id })))
      return { routing, reviews, ids, floor_added }
    }
    const lensThunks = LENSES.map(lens => () => agent(bugPrompt(p, lens),
      { label: `bugs-${lens.key}:${p.group}`, phase: 'Review', agentType: 'todo-reviewer', schema: FINDINGS })
      .then(r => r && { ...r, reviewer: `todo-reviewer/${lens.key}` }))
    const [cl, ...lensed] = await parallel([checklist, ...lensThunks])
    const done = [...lensed, ...(cl ? cl.reviews : [])].filter(Boolean)
    // Any reviewer that died leaves part of the diff unreviewed: the whole review reruns.
    const reviewers_ok = lensed.every(Boolean) && Boolean(cl && cl.routing) && cl.reviews.every(Boolean)
    return { findings: done.flatMap(f => f.findings), ranges: done.map(f => f.reviewed_range),
      reviewers: done.map(f => f.reviewer), routed: cl && cl.routing ? cl.ids : null,
      floor_added: cl && cl.routing ? cl.floor_added : [], reviewers_ok }
  },
  async (rev, p) => {
    // Different reviewers can report the same finding; count it once. Then each blocking finding
    // faces two skeptics, and stops blocking only if both refute it (a dead skeptic refutes nothing).
    const candidates = rev.reviewers_ok ? byLocation(rev.findings.filter(f => BLOCKING.has(f.severity)), p.worktree) : []
    const judged = await parallel(candidates.map(f => () => parallel([0, 1].map(n => () => agent(refutePrompt(p, f),
      { label: `refute-${n}:${p.group}:${f.file}:${f.line}`, phase: 'Refute', agentType: 'todo-reviewer', schema: REFUTATION })))))
    const blocking = [], refuted = []
    // Walk the candidates, not the judgments: a judgment that threw (null) must keep its finding blocking.
    candidates.forEach((f, i) => {
      const votes = judged[i] || []
      if (votes.length === 2 && votes.every(v => v && v.refuted)) refuted.push({ ...f, refutations: votes.map(v => v.reason) })
      else blocking.push(f)
    })
    if (refuted.length) log(`${p.group}: ${refuted.length} blocking finding(s) refuted by both skeptics`)
    const base = { group: p.group, ids: p.ids, ...rev, blocking, refuted, repair_blockers: '' }
    if (round !== 1 || !blocking.length || !rev.reviewers_ok) return { ...base, repair: null, verdict: null }
    const repair = await agent(repairPrompt(p, blocking),
      { label: `repair:${p.group}`, phase: 'Repair', agentType: 'todo-worker', schema: WORKER })
    if (!repair || repair.status !== 'staged') {
      return { ...base, repair, verdict: null, repair_blockers: repair ? repair.blockers : '' }
    }
    const verdict = await agent(verifyPrompt(p, repair),
      { label: `verify:${p.group}`, phase: 'Repair', agentType: 'todo-verifier', schema: VERDICT })
    return { ...base, repair, verdict }
  },
)

return {
  results: results.map((r, i) => r || { group: prs[i].group, ids: prs[i].ids, findings: [], ranges: [],
    reviewers: [], routed: null, floor_added: [], reviewers_ok: false, blocking: [], refuted: [],
    repair_blockers: '', repair: null, verdict: null }),
}
