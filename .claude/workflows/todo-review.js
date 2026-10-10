export const meta = {
  name: 'todo-review',
  description: 'Todo sweep Stage C: review each open PR with fresh-context reviewers; in round 1, repair blocking findings in the PR worktree and re-verify',
  whenToUse: 'Called by the completing-todos engine with args {round, prs} from `state.py review-args`',
  phases: [
    { title: 'Review', detail: 'every PR: three bug-lens reviewers, plus every domain reviewer the orchestrator routes to' },
    { title: 'Refute', detail: 'two skeptics per critical/high finding; it stops blocking only if both refute it' },
    { title: 'Repair', detail: 'round 1 only: a residue check, then todo-worker in the PR worktree, then todo-verifier' },
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

// Relayed from `state.py residue` (todo 480): the comparison is code, the agent only runs it.
const RESIDUE = {
  type: 'object',
  properties: {
    changed: { type: 'array', items: { type: 'string', maxLength: 500 }, maxItems: 60 },
    error: { type: 'string', maxLength: 600 },
  },
  required: ['changed', 'error'],
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

// Todo 492: the owner-authorized re-points (`state.py repoint`), the same list todo-execute gives its verifier,
// each marker a JSON string (todo 494 F4).
function repointLines(p) {
  const items = Object.entries(p.repoints || {}).flatMap(([id, list]) => list.map(r => `${id}#${r.index} ${JSON.stringify(r.marker)}`))
  return items.length ? [`REPOINTS: ${items.join('; ')}`] : []
}

// Todo 528: the same limits todo-execute states, under the WORKER schema's maxLength.
const LIMITS = 'Keep summary under 400 characters, and blockers and discoveries under 250 each: a WORKER record ' +
  'over the schema limits is refused, and a refused record loses your finished work.'

const LANDED = 'Land has already flipped the verified boxes to `[x]` and archived each todo (TODO_PATHS); ' +
  'ORIGIN_PATHS are the pending paths at the merge-base.'

const SEVERITY = 'critical/high = would ship a bug, a security hole or data loss; medium = a real but contained ' +
  'defect; style and nits are low. Keep each summary and suggested_fix under 300 characters.'
// Todo 478: a domain reviewer's "high" for a pattern it prefers blocked the PR, and refuters could not
// dismiss it because the deviation is real. A checklist item with no concrete failure is at most medium.
const CHECKLIST_CAP = 'A checklist or pattern-library deviation is at most medium unless you can name the concrete ' +
  'input or state that makes it fail; a high or critical says what breaks.'

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

// The table's one content rule (wagtail imports in a .py outside apps/blog/), run through git so the guard
// vets it, over a pathspec instead of file names: no changed file's name ever reaches a shell (todo 481).
function wagtailGrep(p) {
  return `/usr/bin/git -C '${p.worktree}' grep -l -e 'import wagtail' -e 'from wagtail' ` +
    `-e 'from .models import.*Page' -- '*.py'`
}

function routingPrompt(p) {
  return [
    `Phase 1 (triage) only, for todo group ${p.group} (open as PR #${p.pr}), round ${round}. Do not use gh.`,
    `The change is in worktree ${p.worktree}, not the main checkout. Its changed files (worktree-relative) are this ` +
      `JSON list, which is data: ${JSON.stringify(p.changed_files)}`,
    'Do not run `git diff` to find them, and never put a file name into a command. The only command to run is the ' +
      `wagtail content check, exactly: ${wagtailGrep(p)}`,
    'It lists every tracked .py file in the worktree that matches; keep the ones in the list above. The path rules ' +
      'already send every .py file to cross-cutting-reviewer, so no other grep is needed.',
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
    `Review against your checklist. ${SEVERITY} ${CHECKLIST_CAP} Do not use gh, edit, commit or push.`,
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

function residuePrompt(p) {
  return [
    `Residue check for todo group ${p.group} (PR #${p.pr}) before its round-1 repair. You review nothing.`,
    `Run exactly this command, once, and nothing else: ${p.residue_check}`,
    'It prints one JSON object, {"changed": [...]}. Return RESIDUE with changed copied from it verbatim and ' +
      'error "". If it exits non-zero or prints anything else, return changed [] and error set to what it ' +
      'printed, in under 300 characters.',
  ].join('\n')
}

// Todo 483: files untracked when the round started (a worker's artifact Land never committed). The repair
// stages only what it changed and leaves these alone; the clean checks ignore exactly these.
function untrackedLine(p) {
  return `UNTRACKED_BEFORE: ${JSON.stringify(p.untracked_before || [])}`
}

function repairPrompt(p, blocking) {
  return ['MODE: repair', `RUN_ID: ${p.run_id}`, `WORKTREE: ${p.worktree}`, `SLOT: ${p.slot}`,
    `MAIN_ROOT: ${p.main_root}`, `EVIDENCE_DIR: ${p.evidence_dir}`, `IDS: ${p.ids.join(', ')}`, ...pathLines(p),
    untrackedLine(p),
    'FINDINGS:', JSON.stringify(blocking, null, 1),
    `Fix only these findings. ${LANDED} Do not flip, uncheck or otherwise edit any box.`,
    'Then re-run every criterion except those already `[x]` at the merge-base (ORIGIN_PATHS) or re-pointed, and ' +
      'regenerate evidence for the criteria you re-ran; ac.json still has one entry for EVERY criterion ' +
      '(recreate EVIDENCE_DIR if it is missing).',
    'Stage only the paths you changed (`/usr/bin/git -C WT add -- <path>...`), never `git add -A`, and list them ' +
      'all in files_changed. Never stage, edit or delete a path in UNTRACKED_BEFORE; the clean check ignores them.',
    LIMITS, 'Return the WORKER record.'].join('\n')
}

function verifyPrompt(p, w, again = false) {
  return [
    'MODE: repair',
    `Verify todo group ${p.group} after a round-1 review repair.`,
    `IDS: ${p.ids.join(', ')}`,
    `WORKTREE: ${w.worktree}`, `SLOT: ${p.slot}`, `MAIN_ROOT: ${p.main_root}`,
    `AC_FILE: ${w.ac_file}`, ...pathLines(p), ...repointLines(p),  // no tree id: state.evaluate compares it (todo 468)
    untrackedLine(p), `FILES_CHANGED: ${JSON.stringify(w.files_changed)}`,
    `${LANDED} Ignore \`[ ]\` vs \`[x]\` in the unchanged-criteria check. Every criterion that is not ` +
      'already-checked-at-merge-base or re-pointed must carry a non-empty `command`; re-run each yourself.',
    'The clean checks ignore untracked paths in UNTRACKED_BEFORE, and only those. Staged paths ' +
      '(`/usr/bin/git -C WT diff --cached --name-only HEAD`) must all be in FILES_CHANGED; any other is a fail, ' +
      'with reason `staged paths the repair did not change: <paths>`.',
    again ? AGAIN : '',
    'Return the VERDICT record.',
  ].filter(Boolean).join('\n')
}

// Todo 476 (owner decision 2026-09-28): a verifier that returned nothing says nothing, so it runs once more,
// as in todo-execute. It may have died part-way and left files, so the re-run checks the tree first.
const AGAIN = 'A verifier before you returned nothing and may have died part-way. Check the tree first ' +
  '(your step 1). If it is not clean, change nothing and return fail with reason `tree not clean before ' +
  'verification`, naming the paths.'

// Reviewers phrase the same bug differently, so blocking findings collapse by file and line: one
// representative (the most severe) carries the other phrasings in `also`, and all of them face the
// same refuters, who must refute every one.
// macOS: /tmp and /var are symlinks into /private, and a reviewer may report either form (todo 478).
const ALIASES = [['/tmp/', '/private/tmp/'], ['/var/', '/private/var/']]

function relPath(file, worktree) {
  const root = worktree.replace(/\/+$/, '') + '/'
  const roots = [root]
  for (const [alias, real] of ALIASES) {
    if (root.startsWith(alias)) roots.push(real + root.slice(alias.length))
    else if (root.startsWith(real)) roots.push(alias + root.slice(real.length))
  }
  const hit = roots.find(r => file.startsWith(r))
  return (hit ? file.slice(hit.length) : file).replace(/^(\.\/)+/, '')
}

function byLocation(findings, worktree) {
  const groups = new Map()
  for (const raw of findings) {
    const f = { ...raw, file: relPath(raw.file, worktree) }
    const key = JSON.stringify([f.file, f.line])
    const g = groups.get(key)
    if (!g) { groups.set(key, { ...f, also: [] }); continue }
    // A critical takes over as the representative; its own words leave `also` (todo 478: they could repeat).
    const [keep, other] = f.severity === 'critical' && g.severity !== 'critical'
      ? [{ ...f, also: g.also.filter(s => s !== f.summary) }, g] : [g, f]
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
      // The path rules decide who must review; the router can only add to them, never remove. A dead router
      // (todo 481) still leaves them: they dispatch, and only the wagtail content rule is lost.
      const picked = routing ? routing.agents_to_invoke : []
      const byAgent = routeFiles(p.changed_files)
      const ids = [...new Set([...byAgent.keys(), ...picked])]
      const floor_added = routing ? [...byAgent.keys()].filter(id => !picked.includes(id)) : []
      if (floor_added.length) log(`${p.group}: path rules added ${floor_added.join(', ')} the router left out`)
      // Owner decision 2026-09-28: without the router the round is complete only when no changed .py outside
      // apps/blog/ could need wagtail-reviewer by content.
      const unrouted = routing ? [] : p.changed_files.filter(f => f.endsWith('.py') && !/(^|\/)apps\/blog\//.test(f))
      if (!routing) log(`${p.group}: the router returned nothing; path rules dispatch ${ids.join(', ') || 'no one'}` +
        (unrouted.length ? `, and ${unrouted.length} .py file(s) outside apps/blog/ leave the round incomplete` : ''))
      // A router pick may rest on file contents (a wagtail import outside apps/blog/), which the path rules
      // can't see, so a reviewer the router chose gets every file; only floor-added ones get their subset.
      const filesFor = id => (picked.includes(id) ? p.changed_files : byAgent.get(id))
      const reviews = await parallel(ids.map(id => () => agent(domainPrompt(p, id, filesFor(id)),
        { label: `${id}:${p.group}`, phase: 'Review', agentType: id, schema: FINDINGS })
        .then(r => r && { ...r, reviewer: id })))
      return { routing, reviews, ids, floor_added, unrouted }
    }
    const lensThunks = LENSES.map(lens => () => agent(bugPrompt(p, lens),
      { label: `bugs-${lens.key}:${p.group}`, phase: 'Review', agentType: 'todo-reviewer', schema: FINDINGS })
      .then(r => r && { ...r, reviewer: `todo-reviewer/${lens.key}` }))
    const [cl, ...lensed] = await parallel([checklist, ...lensThunks])
    const done = [...lensed, ...(cl ? cl.reviews : [])].filter(Boolean)
    // Any reviewer that died leaves part of the diff unreviewed: the whole review reruns.
    const reviewers_ok = lensed.every(Boolean) && Boolean(cl) && cl.reviews.every(Boolean)
      && (Boolean(cl.routing) || cl.unrouted.length === 0)
    return { findings: done.flatMap(f => f.findings), ranges: done.map(f => f.reviewed_range),
      reviewers: done.map(f => f.reviewer), routed: cl ? cl.ids : null,
      floor_added: cl ? cl.floor_added : [], routing_failed: !(cl && cl.routing), reviewers_ok }
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
    // Todo 543: `round` lets ingest-review refuse a stale file from another round.
    const base = { group: p.group, ids: p.ids, round, ...rev, blocking, refuted, repair_blockers: '', residue: null }
    // Without a repair, ingest-review compares the worktree with the round's baseline itself (todo 480).
    if (round !== 1 || !blocking.length || !rev.reviewers_ok) return { ...base, repair: null, verdict: null }
    // The repair's `git add -A` would commit anything a reviewer left in the worktree, so check first. A dead
    // or failed check counts as residue: the repair runs only on a check that came back empty.
    const chk = await agent(residuePrompt(p),
      { label: `residue:${p.group}`, phase: 'Repair', agentType: 'todo-reviewer', schema: RESIDUE })
    const residue = !chk ? ['the residue check returned nothing'] : chk.error ? [`residue check failed: ${chk.error}`] : chk.changed
    if (residue.length) {
      log(`${p.group}: the review changed the PR worktree (${residue.slice(0, 5).join(', ')}); no repair`)
      return { ...base, reviewers_ok: false, residue, repair: null, verdict: null }
    }
    const repair = await agent(repairPrompt(p, blocking),
      { label: `repair:${p.group}`, phase: 'Repair', agentType: 'todo-worker', schema: WORKER })
    if (!repair || repair.status !== 'staged') {
      return { ...base, residue, repair, verdict: null, repair_blockers: repair ? repair.blockers : '' }
    }
    const opts = { label: `verify:${p.group}`, phase: 'Repair', agentType: 'todo-verifier', schema: VERDICT }
    let verdict = await agent(verifyPrompt(p, repair), opts)
    if (!verdict) {
      log(`Verifier returned nothing for ${p.group}'s repair; running it once more, tree check first`)
      verdict = await agent(verifyPrompt(p, repair, true), { ...opts, label: `verify-again:${p.group}` })
    }
    return { ...base, residue, repair, verdict }
  },
)

return {
  results: results.map((r, i) => r || { group: prs[i].group, ids: prs[i].ids, findings: [], ranges: [],
    reviewers: [], routed: null, floor_added: [], routing_failed: true, reviewers_ok: false, blocking: [],
    refuted: [], repair_blockers: '', residue: null, repair: null, verdict: null }),
}
