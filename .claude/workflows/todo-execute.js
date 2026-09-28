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
  },
  required: ['ids', 'verdict', 'ac', 'test_edits_flagged', 'commands_rerun', 'tree_id_before', 'tree_id_after',
    'clean_after'],
}

const briefs = (args && args.briefs) || []

function planPrompt(b) {
  return [
    'MODE: plan',
    `Write an implementation plan for todo group ${b.group}: ${b.todo_paths.join(', ')}.`,
    `Owner decisions (binding): ${JSON.stringify(b.owner_decisions)}`,
    'Return the plan field only.',
  ].join('\n')
}

function workPrompt(b, plan) {
  return ['MODE: implement', 'BRIEF:', JSON.stringify(b, null, 1), plan ? `PLAN:\n${plan}` : 'PLAN: none',
    'Return the WORKER record.'].join('\n')
}

function verifyPrompt(b, w) {
  return [
    `Verify todo group ${b.group} (${b.ids.join(', ')}).`,
    `WORKTREE: ${w.worktree}`, `SLOT: ${b.slot}`, `MAIN_ROOT: ${b.main_root}`,
    `AC_FILE: ${w.ac_file}`, `CLAIMED_TREE: ${w.tree_id}`,
    'Return the VERDICT record.',
  ].join('\n')
}

function retryPrompt(b, w, v) {
  const notes = v.ac.filter(a => !a.verified).map(a => `todo ${a.todo} AC ${a.index + 1}: ${a.note}`).join('\n')
  return ['MODE: retry', `WORKTREE: ${w.worktree}`, 'BRIEF:', JSON.stringify(b, null, 1),
    `VERIFIER NOTES:\n${notes || `verdict ${v.verdict}; tree or cleanliness check failed`}`,
    'Return the WORKER record.'].join('\n')
}

const results = await pipeline(
  briefs,
  async b => {
    if (!b.plan_needed) return ''
    const p = await agent(planPrompt(b), { label: `plan:${b.group}`, phase: 'Plan', agentType: 'todo-triager', schema: PLAN })
    return p ? p.plan : ''
  },
  (plan, b) => agent(workPrompt(b, plan),
    { label: `work:${b.group}`, phase: 'Implement', agentType: 'todo-worker', isolation: 'worktree', schema: WORKER }),
  async (worker, b) => {
    const base = { group: b.group, ids: b.ids }
    if (!worker || worker.status !== 'staged') return { ...base, worker, verdict: null, retried: false }
    const verdict = await agent(verifyPrompt(b, worker),
      { label: `verify:${b.group}`, phase: 'Verify', agentType: 'todo-verifier', schema: VERDICT })
    if (!verdict || verdict.verdict === 'pass') return { ...base, worker, verdict, retried: false }
    const retry = await agent(retryPrompt(b, worker, verdict),
      { label: `retry:${b.group}`, phase: 'Verify', agentType: 'todo-worker', schema: WORKER })
    if (!retry || retry.status !== 'staged') return { ...base, worker: retry || worker, verdict, retried: true }
    const second = await agent(verifyPrompt(b, retry),
      { label: `verify2:${b.group}`, phase: 'Verify', agentType: 'todo-verifier', schema: VERDICT })
    return { ...base, worker: retry, verdict: second, retried: true }
  },
)

return {
  results: results.map((r, i) => r || { group: briefs[i].group, ids: briefs[i].ids, worker: null, verdict: null, retried: false }),
}
