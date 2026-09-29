export const meta = {
  name: 'todo-execute',
  description: 'Todo sweep Stage B: per group, an optional planner, one todo-worker in its own worktree, then an independent todo-verifier with one retry on fail',
  whenToUse: 'Called by the completing-todos engine with args {run_id, briefs} from `state.py execute-args`',
  phases: [
    { title: 'Plan', detail: 'only groups triaged needs-research' },
    { title: 'Implement', detail: 'todo-worker, isolation: worktree' },
    { title: 'Verify', detail: 'todo-verifier; one retry on fail' },
  ],
}

const PLAN = { type: 'object', properties: { plan: { type: 'string', maxLength: 4000 } }, required: ['plan'] }

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

const briefs = (args && args.briefs) || []

// Before Land nothing is archived, so a todo's current path and its merge-base path are the same.
function pathLines(b) {
  return [`TODO_PATHS: ${b.todo_paths.join(', ')}`, `ORIGIN_PATHS: ${b.todo_paths.join(', ')}`]
}

// Todo 492: the owner-authorized re-points (`state.py repoint`). The verifier accepts a criterion changed
// only by one of these markers; any other change to a criterion is still an edit.
function repointLines(b) {
  const items = Object.entries(b.repoints || {}).flatMap(([id, list]) => list.map(r => `${id}#${r.index} "${r.marker}"`))
  return items.length ? [`REPOINTS: ${items.join('; ')}`] : []
}

// Todo 492: a reopened todo whose staged worktree is verified as it is (`state.py set --reverify`).
// No planner and no worker run; this stands in for the worker record the verifier checks against.
function reverifyWorker(b) {
  return { ids: b.ids, status: 'staged', ...b.reverify, files_changed: [], tests_run: [], blockers: '',
    discoveries: '', summary: 're-verify of the staged worktree an earlier attempt left' }
}

function planPrompt(b) {
  return [
    'MODE: plan',
    `Write an implementation plan for todo group ${b.group}: ${b.todo_paths.join(', ')}.`,
    `Owner decisions (binding): ${JSON.stringify(b.owner_decisions)}`,
    'Return the plan field only.',
  ].join('\n')
}

function workPrompt(b, plan) {
  return ['MODE: implement', ...pathLines(b), 'BRIEF:', JSON.stringify(b, null, 1),
    plan ? `PLAN:\n${plan}` : 'PLAN: none', 'Return the WORKER record.'].join('\n')
}

function verifyPrompt(b, w) {
  return [
    'MODE: execute',
    `Verify todo group ${b.group}.`,
    `IDS: ${b.ids.join(', ')}`,
    `WORKTREE: ${w.worktree}`, `SLOT: ${b.slot}`, `MAIN_ROOT: ${b.main_root}`,
    `AC_FILE: ${w.ac_file}`, ...pathLines(b), ...repointLines(b),
    'Return the VERDICT record.',
  ].join('\n')
}

// A verifier that returns nothing says nothing about the work, so it runs once more on the same
// worktree before the group can fail (owner decision 2026-09-28, todo 468). The worker's tree id is
// not in the prompt: state.evaluate compares it with the verdict's tree ids.
async function verify(b, w, label) {
  const opts = { label, phase: 'Verify', agentType: 'todo-verifier', schema: VERDICT }
  const first = await agent(verifyPrompt(b, w), opts)
  if (first) return first
  log(`Verifier returned nothing for ${b.group}; running it once more`)
  return agent(verifyPrompt(b, w), { ...opts, label: `${label}-again` })
}

function retryPrompt(b, w, v) {
  const notes = v.ac.filter(a => !a.verified).map(a => `todo ${a.todo} index ${a.index}: ${a.note}`)
  const reasons = (v.reasons || []).join('; ')
  if (reasons) notes.push(`group: ${reasons}`)
  return ['MODE: retry', `RUN_ID: ${b.run_id}`, `WORKTREE: ${w.worktree}`, ...pathLines(b), 'BRIEF:',
    JSON.stringify(b, null, 1),
    `VERIFIER NOTES:\n${notes.join('\n') || `verdict ${v.verdict}; tree or cleanliness check failed`}`,
    'An entry noted `external` cannot be fixed: return `status: blocked`, naming that criterion.',
    'Return the WORKER record.'].join('\n')
}

const results = await pipeline(
  briefs,
  async b => {
    if (!b.plan_needed || b.reverify) return ''
    const p = await agent(planPrompt(b), { label: `plan:${b.group}`, phase: 'Plan', agentType: 'todo-triager', schema: PLAN })
    if (!p) log(`Planner returned nothing for ${b.group}; its worker gets PLAN: none`)
    return p ? p.plan : ''
  },
  (plan, b) => b.reverify ? reverifyWorker(b) : agent(workPrompt(b, plan),
    { label: `work:${b.group}`, phase: 'Implement', agentType: 'todo-worker', isolation: 'worktree', schema: WORKER }),
  async (worker, b) => {
    // The first attempt's worktree rides on every result, so a dead retry (worker: null) still
    // tells ingest-execute where the staged work is.
    const base = { group: b.group, ids: b.ids, worktree: worker ? worker.worktree : null }
    if (!worker || worker.status !== 'staged') return { ...base, worker, verdict: null, retried: false }
    const verdict = await verify(b, worker, `verify:${b.group}`)
    if (!verdict || verdict.verdict === 'pass') return { ...base, worker, verdict, retried: false }
    const retry = await agent(retryPrompt(b, worker, verdict),
      { label: `retry:${b.group}`, phase: 'Verify', agentType: 'todo-worker', schema: WORKER })
    // A dead or non-staged retry is the result: never pass the first attempt off as the retry's.
    if (!retry || retry.status !== 'staged') return { ...base, worker: retry, verdict: null, retried: true }
    const second = await verify(b, retry, `verify2:${b.group}`)
    return { ...base, worker: retry, verdict: second, retried: true }
  },
)

return {
  results: results.map((r, i) => r || { group: briefs[i].group, ids: briefs[i].ids, worktree: null, worker: null,
    verdict: null, retried: false }),
}
