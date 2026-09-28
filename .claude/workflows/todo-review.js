export const meta = {
  name: 'todo-review',
  description: 'Todo sweep Stage C: review each open PR with fresh-context reviewers; in round 1, repair blocking findings in the PR worktree and re-verify',
  whenToUse: 'Called by the completing-todos engine with args {round, prs} from `state.py review-args`',
  phases: [
    { title: 'Review', detail: 'bug review for every PR; checklist review for size m and l' },
    { title: 'Repair', detail: 'round 1 only: todo-worker in the PR worktree, then todo-verifier' },
  ],
}

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
          summary: { type: 'string', maxLength: 300 },
          suggested_fix: { type: 'string', maxLength: 300 },
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

function bugPrompt(p) {
  return [
    `Review the change for todo group ${p.group} (${p.ids.join(', ')}), round ${round}. It is open as PR #${p.pr}; ` +
      'do not use gh or fetch the PR — review the local diff only.',
    `Branch ${p.branch}, worktree ${p.worktree}. The change is exactly: ${diffRange(p)}`,
    'Review that diff for correctness bugs, with reviewed_range "git diff origin/main...HEAD".',
    'critical/high = would ship a bug, a security hole or data loss. Style and nits are low.',
    p.test_edits.length ? `The verifier flagged edits to existing tests: ${p.test_edits.join(', ')}. Check each is justified.` : '',
    'Do not post comments, commit or push. Return FINDINGS.',
  ].filter(Boolean).join('\n')
}

function checklistPrompt(p) {
  return [
    `Checklist review of todo group ${p.group} (open as PR #${p.pr}), round ${round}. Do not use gh.`,
    `The change is in worktree ${p.worktree}, not the main checkout. Use ${diffRange(p)} for the diff and add --name-only for the file list.`,
    'Route to the domain reviewers as usual. Report only; do not repair. Return FINDINGS with reviewed_range set to the range you used.',
  ].join('\n')
}

function repairPrompt(p, blocking) {
  return ['MODE: repair', `WORKTREE: ${p.worktree}`, `SLOT: ${p.slot}`, `MAIN_ROOT: ${p.main_root}`,
    `EVIDENCE_DIR: ${p.evidence_dir}`, `IDS: ${p.ids.join(', ')}`, ...pathLines(p),
    'FINDINGS:', JSON.stringify(blocking, null, 1),
    `Fix only these findings. ${LANDED} Do not flip, uncheck or otherwise edit any box.`,
    'Then re-run every criterion except those already `[x]` at the merge-base (ORIGIN_PATHS) or re-pointed, and ' +
      'regenerate their evidence and ac.json (recreate EVIDENCE_DIR if it is missing).',
    'Return the WORKER record.'].join('\n')
}

function verifyPrompt(p, w) {
  return [
    'MODE: repair',
    `Verify todo group ${p.group} after a round-1 review repair.`,
    `IDS: ${p.ids.join(', ')}`,
    `WORKTREE: ${w.worktree}`, `SLOT: ${p.slot}`, `MAIN_ROOT: ${p.main_root}`,
    `AC_FILE: ${w.ac_file}`, ...pathLines(p), `CLAIMED_TREE: ${w.tree_id}`,
    `${LANDED} Ignore \`[ ]\` vs \`[x]\` in the unchanged-criteria check. Every criterion except those \`[x]\` ` +
      'at the merge-base or re-pointed must have been re-run.',
    'Return the VERDICT record.',
  ].join('\n')
}

function dedupe(findings) {
  const seen = new Set()
  return findings.filter(f => {
    const key = JSON.stringify([f.file, f.line, f.summary])
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

const results = await pipeline(
  prs,
  async p => {
    const reviewers = [() => agent(bugPrompt(p),
      { label: `bugs:${p.group}`, phase: 'Review', agentType: 'general-purpose', schema: FINDINGS })]
    if (p.size === 'm' || p.size === 'l') {
      reviewers.push(() => agent(checklistPrompt(p),
        { label: `checklist:${p.group}`, phase: 'Review', agentType: 'code-review-orchestrator', schema: FINDINGS }))
    }
    // The bug review gates. The checklist review is best-effort: if it cannot run (e.g. it cannot
    // dispatch nested reviewers from inside a workflow) the PR is flagged, not blocked.
    const found = await parallel(reviewers)
    const ok = found.filter(Boolean)
    return { findings: ok.flatMap(f => f.findings), ranges: ok.map(f => f.reviewed_range),
      reviewers_ok: Boolean(found[0]), checklist_skipped: reviewers.length > 1 && !found[1] }
  },
  async (rev, p) => {
    // The bug and checklist reviewers can report the same finding; count it once.
    const blocking = dedupe(rev.findings.filter(f => BLOCKING.has(f.severity)))
    const base = { group: p.group, ids: p.ids, ...rev, blocking, repair_blockers: '' }
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
    reviewers_ok: false, checklist_skipped: false, blocking: [], repair_blockers: '', repair: null, verdict: null }),
}
