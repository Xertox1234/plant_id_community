#!/usr/bin/env node
// Tests for .claude/workflows/todo-*.js — run: node scripts/todos/test_workflows.js
// Runs each workflow with stub agent()/pipeline()/parallel(), so the control
// flow (which agents run, with which isolation, when retry and repair happen)
// is pinned without spending a token. It also proves each file parses.
'use strict'
const fs = require('fs')
const path = require('path')

const ROOT = path.resolve(__dirname, '..', '..')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const failures = []

function check(label, cond, detail = '') {
  console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${label}${cond ? '' : `  -- ${JSON.stringify(detail)}`}`)
  if (!cond) failures.push(label)
}

function source(name) {
  return fs.readFileSync(path.join(ROOT, '.claude', 'workflows', `${name}.js`), 'utf8')
}

// The subset of JSON Schema the workflows use: type (one or a list), properties, required, enum, maxLength,
// items, maxItems. Returns a list of problems, empty when `value` matches (todo 468). A type it does not
// know is itself a problem, never a throw (todo 476: a throw read as "no stage threw" failing).
const IS = { object: v => v !== null && typeof v === 'object' && !Array.isArray(v), array: Array.isArray,
  string: v => typeof v === 'string', integer: Number.isInteger, boolean: v => typeof v === 'boolean',
  number: v => typeof v === 'number' && Number.isFinite(v), null: v => v === null }
function schemaErrors(value, schema, at = '$') {
  if (schema.type !== undefined) {
    const types = Array.isArray(schema.type) ? schema.type : [schema.type]
    const unknown = types.filter(t => !Object.prototype.hasOwnProperty.call(IS, t))
    if (unknown.length) return [`${at}: unknown schema type ${JSON.stringify(unknown.length === 1 ? unknown[0] : unknown)}`]
    if (!types.some(t => IS[t](value))) return [`${at}: not ${types.join(' or ')}`]
  }
  const errs = []
  if (schema.enum && !schema.enum.includes(value)) errs.push(`${at}: ${JSON.stringify(value)} not in enum`)
  if (schema.maxLength !== undefined && typeof value === 'string' && value.length > schema.maxLength) {
    errs.push(`${at}: longer than ${schema.maxLength}`)
  }
  // Todo 476: items and maxItems apply to any array value, with or without `type: 'array'`.
  if (Array.isArray(value)) {
    if (schema.maxItems !== undefined && value.length > schema.maxItems) errs.push(`${at}: more than ${schema.maxItems} items`)
    if (schema.items) value.forEach((v, i) => errs.push(...schemaErrors(v, schema.items, `${at}[${i}]`)))
  }
  if (IS.object(value)) {
    for (const key of schema.required || []) if (!(key in value)) errs.push(`${at}.${key}: missing`)
    for (const [key, sub] of Object.entries(schema.properties || {})) {
      if (key in value) errs.push(...schemaErrors(value[key], sub, `${at}.${key}`))
    }
  }
  return errs
}

// A stage that throws is swallowed into a null row by pipeline()/parallel(), which reads exactly like a
// handled dead agent. So every run asserts that nothing threw, unless the case opts out with allowErrors.
// Every stub response must also match the schema the workflow asked for, or the test proves nothing about
// real records (todo 468); a case that feeds a bad record on purpose opts out with badFixtures.
// parallelThrows (todo 478): a predicate on a parallel() call's results; when it holds, that call throws, as a
// real nested parallel can. The enclosing parallel() then records a null for it, which no stub agent can do.
// mutate: [old, new] replaces one exact string in the workflow source first, so a check can prove that a
// test FAILS on a known-bad version (todo 478). The anchor must occur exactly once.
// chain (todo 494 F8): pipeline() calls each stage and chains .then on what it returns, as a runtime that does not
// await a plain value would; a stage that is not async then throws.
async function run(name, args, respond, { allowErrors = false, badFixtures = false, parallelThrows = null,
  mutate = null, chain = false } = {}) {
  let text = source(name)
  if (mutate) {
    if (text.split(mutate[0]).length !== 2) throw new Error(`mutation anchor not found once: ${mutate[0]}`)
    text = text.replace(mutate[0], () => mutate[1])
  }
  const body = text.replace(/^export const meta/m, 'const meta')
  const calls = []
  const errors = []
  const logs = []
  const fixtureErrors = []
  const agent = async (prompt, opts = {}) => {
    calls.push({ prompt, opts })
    const out = await respond(prompt, opts, calls)
    if (out !== null && out !== undefined && opts.schema) {
      fixtureErrors.push(...schemaErrors(out, opts.schema).map(e => `${opts.label}: ${e}`))
    }
    return out
  }
  const pipeline = async (items, ...stages) =>
    Promise.all(items.map(async (item, i) => {
      let value = item
      try {
        for (const stage of stages) value = chain ? await stage(value, item, i).then(v => v) : await stage(value, item, i)
        return value
      } catch (e) {
        errors.push(String(e))
        return null
      }
    }))
  const parallel = async thunks => {
    const out = await Promise.all(thunks.map(t => t().catch(e => { errors.push(String(e)); return null })))
    if (parallelThrows && parallelThrows(out)) throw new Error('stub: this parallel() threw')
    return out
  }
  const fn = new AsyncFunction('agent', 'pipeline', 'parallel', 'phase', 'log', 'args', 'budget', 'workflow', body)
  const result = await fn(agent, pipeline, parallel, () => {}, m => logs.push(m), args, { total: null }, async () => null)
  if (!allowErrors) check(`${name}: no stage threw`, errors.length === 0, errors)
  if (!badFixtures) check(`${name}: every stub response matches its schema`, fixtureErrors.length === 0, fixtureErrors)
  return { result, calls, errors, logs, fixtureErrors }
}

const worker = (over = {}) => ({ ids: ['1'], status: 'staged', worktree: '/wt/g1', branch: 'b', tree_id: 'T',
  files_changed: [], ac_file: '.sweep-evidence/g1/ac.json', tests_run: [], blockers: '', discoveries: '', summary: '', ...over })
const verdict = (v, over = {}) => ({ ids: ['1'], verdict: v, ac: [{ todo: '1', index: 0, verified: v === 'pass', note: 'n' }],
  test_edits_flagged: [], commands_rerun: 1, tree_id_before: 'T', tree_id_after: 'T', clean_after: true, reasons: [], ...over })
const brief = (over = {}) => ({ run_id: 'r', group: 'g1', ids: ['1'], todo_paths: ['todos/1-pending-p3-x.md'],
  owner_decisions: {}, plan_needed: false, verify_only: false, in_scope_files: [], lanes_held: [], lanes_forbidden: [],
  slot: 1, evidence_dir: '.sweep-evidence/g1', main_root: '/main', ...over })
const pr = (over = {}) => ({ run_id: 'r', round: 1, group: 'g1', ids: ['1'], worktree: '/wt/g1', branch: 'b', pr: 861,
  size: 's', slot: 1, evidence_dir: '.sweep-evidence/g1', main_root: '/main', test_edits: [],
  todo_paths: ['todos/archive/1-completed-p3-x.md'], origin_paths: ['todos/1-pending-p3-x.md'],
  changed_files: ['backend/apps/x/views.py'], residue_check: "python3 '/main/scripts/todos/state.py' residue '/main/run.json' g1",
  ...over })
const triage = (over = {}) => ({ id: '1', class: 'ready', evidence: 'e', blocked_on: '', owner_question: '',
  predicted_files: ['a.py'], size: 's', needs_e2e: false, notes_for_siblings: '', ...over })
const byType = (calls, type) => calls.filter(c => c.opts.agentType === type)
const firstLine = c => c.prompt.split('\n')[0]

function schemaBlock(src, name) {
  const start = src.indexOf(`const ${name} = {`)
  let depth = 0
  for (let i = src.indexOf('{', start); i < src.length; i++) {
    if (src[i] === '{') depth++
    if (src[i] === '}' && --depth === 0) return src.slice(start, i + 1)
  }
  return ''
}

async function main() {
  // --- triage
  let r = await run('todo-triage', { todos: [{ id: '1', path: 'a' }, { id: '2', path: 'b' }] },
    (p, o) => (p.includes('id: 2') ? null : triage({ id: 'WRONG' })))
  check('triage: one todo-triager per todo', byType(r.calls, 'todo-triager').length === 2)
  check('triage: record ids are forced to the input id', r.result.records[0].id === '1', r.result)
  check('triage: a dead agent is reported missing', r.result.missing.join() === '2', r.result)
  check('triage: no root line unless a root is given', !byType(r.calls, 'todo-triager')[0].prompt.includes('root:'))
  // Todo 468: the harness itself rejects a stub that is not a valid record (the old triage stub).
  r = await run('todo-triage', { todos: [{ id: '1', path: 'a' }] }, () => ({ id: 'WRONG', class: 'ready' }),
    { badFixtures: true })
  check('fixtures: a stub that does not match its schema is rejected (todo 468)',
    r.fixtureErrors.some(e => e.includes('$.evidence: missing')) && r.fixtureErrors.some(e => e.includes('$.size: missing')),
    r.fixtureErrors)
  r = await run('todo-triage', { todos: [{ id: '1', path: 'a' }] }, () => triage({ class: 'maybe', size: 'xl' }),
    { badFixtures: true })
  check('fixtures: an enum value outside the schema is rejected',
    r.fixtureErrors.length === 2 && r.fixtureErrors.every(e => e.includes('not in enum')), r.fixtureErrors)
  r = await run('todo-triage', { todos: [{ id: '1', path: 'a' }], root: '/scratch/triage-r' }, () => triage())
  check('triage: a root reaches every triager prompt (todo 468)',
    byType(r.calls, 'todo-triager')[0].prompt.includes('\nroot: /scratch/triage-r\n'))

  // --- execute: pass first time
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] },
    (p, o) => (o.agentType === 'todo-worker' ? worker() : verdict('pass')))
  const work = byType(r.calls, 'todo-worker')
  check('execute: the implementer runs in its own worktree', work.length === 1 && work[0].opts.isolation === 'worktree')
  check('execute: no planner unless plan_needed', byType(r.calls, 'todo-triager').length === 0)
  check('execute: one verifier on a pass', byType(r.calls, 'todo-verifier').length === 1)
  check('execute: result carries the verdict', r.result.results[0].verdict.verdict === 'pass' && !r.result.results[0].retried)

  // --- execute: fail, then retry in the same worktree
  let verifies = 0
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] },
    (p, o) => (o.agentType === 'todo-worker' ? worker() : verdict(++verifies === 1 ? 'fail' : 'pass')))
  const works = byType(r.calls, 'todo-worker')
  check('execute: a failed verdict gets exactly one retry', works.length === 2 && byType(r.calls, 'todo-verifier').length === 2)
  check('execute: the retry reuses the worktree, no new isolation',
    works[1].opts.isolation === undefined && works[1].prompt.startsWith('MODE: retry') && works[1].prompt.includes('/wt/g1'))
  check('execute: retried result is flagged', r.result.results[0].retried && r.result.results[0].verdict.verdict === 'pass')

  // --- execute: planner and dead worker
  r = await run('todo-execute', { run_id: 'r', briefs: [brief({ plan_needed: true })] },
    (p, o) => (o.agentType === 'todo-triager' ? { plan: 'PLAN-TEXT' } : o.agentType === 'todo-worker' ? worker() : verdict('pass')))
  check('execute: needs-research runs a planner in plan mode', byType(r.calls, 'todo-triager')[0].prompt.startsWith('MODE: plan'))
  check('execute: the plan reaches the worker', byType(r.calls, 'todo-worker')[0].prompt.includes('PLAN-TEXT'))
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] }, () => null)
  check('execute: a dead worker yields worker null and no verifier',
    r.result.results[0].worker === null && byType(r.calls, 'todo-verifier').length === 0, r.result)
  check('execute: a dead first worker has worktree null in its result', r.result.results[0].worktree === null, r.result)
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] },
    (p, o) => (o.agentType === 'todo-worker' ? worker({ status: 'blocked', blockers: 'device check' }) : verdict('pass')))
  check('execute: a blocked first worker is the result and carries its worktree',
    r.result.results[0].worker.status === 'blocked' && r.result.results[0].worktree === '/wt/g1'
    && byType(r.calls, 'todo-verifier').length === 0, r.result)

  // --- execute: the prompt contract with the Task 11 agents
  const pending = 'todos/1-pending-p3-x.md'
  const external = verdict('fail', { ac: [{ todo: '1', index: 0, verified: false, note: 'external' }],
    reasons: ['acceptance criteria were edited'] })
  verifies = 0
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] },
    (p, o) => (o.agentType === 'todo-worker' ? worker() : ++verifies === 1 ? external : verdict('pass')))
  const [impl, retry] = byType(r.calls, 'todo-worker')
  const execVerifies = byType(r.calls, 'todo-verifier')
  check('execute: worker prompts open with MODE: implement, then MODE: retry',
    firstLine(impl) === 'MODE: implement' && firstLine(retry) === 'MODE: retry', [firstLine(impl), firstLine(retry)])
  check('execute: every verifier prompt opens with MODE: execute',
    execVerifies.length === 2 && execVerifies.every(c => firstLine(c) === 'MODE: execute'), execVerifies.map(firstLine))
  check('execute: verifier prompts carry IDS, TODO_PATHS and ORIGIN_PATHS', execVerifies.every(c =>
    c.prompt.includes('\nIDS: 1\n') && c.prompt.includes(`TODO_PATHS: ${pending}`) && c.prompt.includes(`ORIGIN_PATHS: ${pending}`)))
  check('execute: implement and retry prompts carry both path lists', [impl, retry].every(c =>
    c.prompt.includes(`TODO_PATHS: ${pending}`) && c.prompt.includes(`ORIGIN_PATHS: ${pending}`)))
  check('execute: retry notes use the 0-based index', retry.prompt.includes('todo 1 index 0: external')
    && !/AC \d/.test(retry.prompt), retry.prompt)
  check('execute: retry notes carry the verdict reasons', retry.prompt.includes('acceptance criteria were edited'))
  check('execute: the retry prompt names the run id for the Work Log', retry.prompt.includes('\nRUN_ID: r\n'))
  check('execute: an external entry tells the retry worker to block',
    retry.prompt.includes('noted `external` cannot be fixed: return `status: blocked`, naming that criterion'))

  verifies = 0
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] }, (p, o) => (o.agentType === 'todo-worker' ? worker()
    : ++verifies === 1 ? verdict('fail', { ac: [{ todo: '1', index: 0, verified: true, note: 'ok' }] }) : verdict('pass')))
  check('execute: with nothing unverified and no reasons, the retry gets the generic note',
    byType(r.calls, 'todo-worker')[1].prompt.includes('tree or cleanliness check failed'))

  // --- execute: dead and non-staged agents
  r = await run('todo-execute', { run_id: 'r', briefs: [brief({ plan_needed: true })] },
    (p, o) => (o.agentType === 'todo-triager' ? null : o.agentType === 'todo-worker' ? worker() : verdict('pass')))
  check('execute: a dead planner is logged and the worker gets PLAN: none',
    r.logs.some(m => m.includes('g1')) && byType(r.calls, 'todo-worker')[0].prompt.includes('PLAN: none'), r.logs)
  let works2 = 0
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] },
    (p, o) => (o.agentType === 'todo-worker' ? (++works2 === 1 ? worker() : null) : verdict('fail')))
  check('execute: a dead retry worker yields worker null, retried, no second verifier',
    r.result.results[0].worker === null && r.result.results[0].verdict === null && r.result.results[0].retried
    && byType(r.calls, 'todo-verifier').length === 1, r.result)
  check('execute: a dead retry still carries the first attempt\'s worktree (final review I5)',
    r.result.results[0].worktree === '/wt/g1', r.result)
  works2 = 0
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] }, (p, o) => (o.agentType === 'todo-worker'
    ? (++works2 === 1 ? worker() : worker({ status: 'blocked', blockers: 'todo 1 AC index 0 is owner-only' }))
    : verdict('fail')))
  check('execute: a blocked retry worker is the result, with no second verifier',
    r.result.results[0].worker.status === 'blocked' && r.result.results[0].verdict === null
    && r.result.results[0].retried && byType(r.calls, 'todo-verifier').length === 1, r.result)
  verifies = 0
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] },
    (p, o) => (o.agentType === 'todo-worker' ? worker() : ++verifies === 1 ? verdict('fail') : null))
  check('execute: a dead second verifier yields verdict null on the retried result',
    r.result.results[0].verdict === null && r.result.results[0].retried && r.result.results[0].worker !== null, r.result)

  // --- execute: owner decisions 2026-09-28 (todo 468)
  check('execute: verifier prompts carry no CLAIMED_TREE (evaluate() compares tree ids)',
    execVerifies.every(c => !c.prompt.includes('CLAIMED_TREE')), execVerifies.map(c => c.prompt))
  verifies = 0
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] },
    (p, o) => (o.agentType === 'todo-worker' ? worker() : ++verifies === 1 ? null : verdict('pass')))
  check('execute: a null verdict re-runs only the verifier, on the same worktree',
    byType(r.calls, 'todo-verifier').length === 2 && byType(r.calls, 'todo-worker').length === 1
    && byType(r.calls, 'todo-verifier')[1].prompt.includes('WORKTREE: /wt/g1')
    && r.result.results[0].verdict.verdict === 'pass' && !r.result.results[0].retried, r.result)
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] },
    (p, o) => (o.agentType === 'todo-worker' ? worker() : null))
  check('execute: two null verdicts give verdict null, with no worker retry',
    byType(r.calls, 'todo-verifier').length === 2 && byType(r.calls, 'todo-worker').length === 1
    && r.result.results[0].verdict === null && !r.result.results[0].retried, r.result)

  // --- execute: todo 492 -- a re-verified group runs only the verifier, on the staged worktree it names
  const rv = { worktree: '/wt/old', branch: 'worktree-old', tree_id: 'T9', ac_file: '.sweep-evidence/g1/ac.json' }
  const reps = { 1: [{ index: 1, to: '8', marker: '→ todo 8 (re-pointed 2026-09-28)' }] }
  r = await run('todo-execute', { run_id: 'r', briefs: [brief({ reverify: rv, repoints: reps, plan_needed: true })] },
    () => verdict('pass', { tree_id_before: 'T9', tree_id_after: 'T9' }))
  const rvVerify = byType(r.calls, 'todo-verifier')
  check('execute: a re-verify runs no planner and no worker (todo 492)',
    byType(r.calls, 'todo-worker').length === 0 && byType(r.calls, 'todo-triager').length === 0, r.calls)
  check('execute: its verifier checks the staged worktree and evidence the brief names',
    rvVerify.length === 1 && rvVerify[0].prompt.includes('WORKTREE: /wt/old')
    && rvVerify[0].prompt.includes('AC_FILE: .sweep-evidence/g1/ac.json'), rvVerify.map(c => c.prompt))
  const rvResult = r.result.results[0]
  check('execute: a re-verify result carries the brief tree as a staged worker record',
    rvResult.worker.status === 'staged' && rvResult.worker.tree_id === 'T9' && rvResult.worktree === '/wt/old'
    && rvResult.verdict.verdict === 'pass' && !rvResult.retried, rvResult)
  check('execute: the verifier prompt lists the owner-authorized re-points',
    rvVerify[0].prompt.includes('\nREPOINTS: 1#1 "→ todo 8 (re-pointed 2026-09-28)"\n'), rvVerify[0].prompt)
  check('execute: no REPOINTS line when the brief has none', execVerifies.every(c => !c.prompt.includes('REPOINTS')))
  verifies = 0
  r = await run('todo-execute', { run_id: 'r', briefs: [brief({ reverify: rv })] }, (p, o) => (o.agentType === 'todo-worker'
    ? worker({ worktree: '/wt/old', tree_id: 'T10' }) : ++verifies === 1 ? verdict('fail') : verdict('pass')))
  const rvRetry = byType(r.calls, 'todo-worker')
  check('execute: a failed re-verify gets the usual one retry, in that same worktree',
    rvRetry.length === 1 && rvRetry[0].opts.isolation === undefined && rvRetry[0].prompt.startsWith('MODE: retry')
    && rvRetry[0].prompt.includes('WORKTREE: /wt/old') && r.result.results[0].retried, rvRetry.map(c => c.prompt))

  // --- review: stub responders. todo-reviewer runs both the bug lenses and the refuters; the schema tells them apart.
  const high = { reviewed_range: 'x', findings: [{ severity: 'high', file: 'a.py', line: 1, summary: 'bug', suggested_fix: '' }] }
  const low = { reviewed_range: 'x', findings: [{ severity: 'low', file: 'a.py', line: 2, summary: 'nit', suggested_fix: '' }] }
  const none = { reviewed_range: 'x', findings: [] }
  const routed = (...ids) => ({ agents_to_invoke: ids, routing_reasons: 'r' })
  const holds = { refuted: false, reason: 'real' }
  const wrong = { refuted: true, reason: 'input cannot reach it' }
  const isRefuter = o => Boolean(o.schema && o.schema.properties.refuted)
  const isResidue = o => Boolean(o.schema && o.schema.properties.changed)
  const clean = { changed: [], error: '' }
  function reviewStub({ lens = none, route = routed('django-drf-reviewer', 'cross-cutting-reviewer'), domain = none,
    refute = holds, repair = worker(), check: v = verdict('pass'), residue = clean } = {}) {
    return (p, o) => {
      if (isResidue(o)) return typeof residue === 'function' ? residue(p, o) : residue
      if (o.agentType === 'todo-reviewer') return typeof (isRefuter(o) ? refute : lens) === 'function'
        ? (isRefuter(o) ? refute : lens)(p, o) : (isRefuter(o) ? refute : lens)
      if (o.agentType === 'code-review-orchestrator') return route
      if (o.agentType === 'todo-worker') return repair
      if (o.agentType === 'todo-verifier') return typeof v === 'function' ? v(p, o) : v
      return typeof domain === 'function' ? domain(p, o) : domain
    }
  }
  const lensCalls = calls => byType(calls, 'todo-reviewer').filter(c => !isRefuter(c.opts) && !isResidue(c.opts))
  const residueCalls = calls => calls.filter(c => isResidue(c.opts))
  const refuteCalls = calls => byType(calls, 'todo-reviewer').filter(c => isRefuter(c.opts))

  // --- review round 1, size s, blocking finding
  r = await run('todo-review', { round: 1, prs: [pr()] }, reviewStub({ lens: high }))
  check('review: every size gets three bug lenses as the guarded todo-reviewer (todo 468 m8)',
    lensCalls(r.calls).length === 3 && byType(r.calls, 'general-purpose').length === 0
    && new Set(lensCalls(r.calls).map(c => c.opts.label)).size === 3, r.calls.map(c => c.opts.label))
  check('review: size s still gets the checklist lane (pre-v2 parity)', byType(r.calls, 'code-review-orchestrator').length === 1)
  check('review: the workflow dispatches every routed domain reviewer itself',
    byType(r.calls, 'django-drf-reviewer').length === 1 && byType(r.calls, 'cross-cutting-reviewer').length === 1)
  check('review: the orchestrator is asked for routing only, and gets the ROUTING schema',
    byType(r.calls, 'code-review-orchestrator')[0].prompt.includes('Phase 1 (triage) only')
    && Boolean(byType(r.calls, 'code-review-orchestrator')[0].opts.schema.properties.agents_to_invoke))
  check('review: the result lists which reviewers ran and what was routed',
    r.result.results[0].reviewers.length === 5 && r.result.results[0].reviewers.includes('django-drf-reviewer')
    && r.result.results[0].routed.join() === 'django-drf-reviewer,cross-cutting-reviewer', r.result)
  check('review: a blocking finding faces two refuters', refuteCalls(r.calls).length === 2)
  const rep = byType(r.calls, 'todo-worker')
  check('review: round 1 repairs in the PR worktree', rep.length === 1 && rep[0].opts.isolation === undefined
    && rep[0].prompt.startsWith('MODE: repair') && rep[0].prompt.includes('/wt/g1'))
  check('review: the repair is re-verified', byType(r.calls, 'todo-verifier').length === 1)
  check('review: reviewer prompts name the explicit diff range',
    lensCalls(r.calls)[0].prompt.includes('diff origin/main...HEAD'))
  const archived = 'todos/archive/1-completed-p3-x.md'
  const repairP = rep[0].prompt
  check('review: the repair prompt carries IDS, both path lists and never TODOS', repairP.includes('\nIDS: 1\n')
    && !repairP.includes('TODOS:') && repairP.includes(`TODO_PATHS: ${archived}`) && repairP.includes(`ORIGIN_PATHS: ${pending}`))
  check('review: the repair prompt says Land already flipped and archived, and forbids box edits',
    repairP.includes('Land has already flipped the verified boxes to `[x]` and archived each todo')
    && repairP.includes('Do not flip, uncheck or otherwise edit any box')
    && repairP.includes('re-run every criterion except those already `[x]` at the merge-base'), repairP)
  check('review: the repair regenerates evidence only for re-run criteria, ac.json keeps every entry',
    repairP.includes('regenerate evidence for the criteria you re-ran; ac.json still has one entry for EVERY criterion'))
  check('review: the repair prompt names the run id for the Work Log', repairP.includes('\nRUN_ID: r\n'))
  const repairV = byType(r.calls, 'todo-verifier')[0]
  check('review: the post-repair verifier opens with MODE: repair', firstLine(repairV) === 'MODE: repair', firstLine(repairV))
  check('review: the post-repair verifier gets IDS and both path lists', repairV.prompt.includes('\nIDS: 1\n')
    && repairV.prompt.includes(`TODO_PATHS: ${archived}`) && repairV.prompt.includes(`ORIGIN_PATHS: ${pending}`))
  check('review: the post-repair verifier gets no CLAIMED_TREE (todo 468)', !repairV.prompt.includes('CLAIMED_TREE'))
  check('review: no REPOINTS line when the PR has none', !repairV.prompt.includes('REPOINTS'))
  r = await run('todo-review', { round: 1, prs: [pr({ repoints: reps })] },
    reviewStub({ lens: high }))
  check('review: the post-repair verifier gets the owner-authorized re-points (todo 492)',
    byType(r.calls, 'todo-verifier')[0].prompt.includes('\nREPOINTS: 1#1 "→ todo 8 (re-pointed 2026-09-28)"\n'))
  check('review: the post-repair verifier ignores box state and knows Land ran',
    repairV.prompt.includes('Ignore `[ ]` vs `[x]`') && repairV.prompt.includes('Land has already flipped'), repairV.prompt)
  check('review: the post-repair verifier requires a command on every open criterion and re-runs each',
    repairV.prompt.includes('not already-checked-at-merge-base or re-pointed must carry a non-empty `command`; ' +
      're-run each yourself') && !repairV.prompt.includes('must have been re-run'), repairV.prompt)
  const bugP = lensCalls(r.calls)[0].prompt
  check('review: the bug reviewer reviews the local diff, single-quoted, never via gh',
    bugP.includes("/usr/bin/git -C '/wt/g1' diff origin/main...HEAD") && bugP.includes('do not use gh')
    && !/Skill|against PR|gh pr/.test(bugP), bugP)
  // A no-isolation agent's cwd is the main checkout, so every checklist prompt must point at the worktree.
  // Todo 481 changed the router's form: the list is JSON data, and its one command is a git grep over a
  // pathspec in the worktree, not a grep built from '<worktree>/<path>' (which a file name could escape).
  const routeP = byType(r.calls, 'code-review-orchestrator')[0].prompt
  check('review: the router gets the changed files from review-args and is told not to diff (todo 478)',
    routeP.includes('["backend/apps/x/views.py"]') && routeP.includes('Do not run `git diff`')
    && routeP.includes("/usr/bin/git -C '/wt/g1' grep -l"), routeP)
  const domP = byType(r.calls, 'django-drf-reviewer')[0].prompt
  check('review: a domain reviewer reads files from the worktree and gets the routed file list',
    domP.includes("'/wt/g1/<path>'") && domP.includes('NOT the main checkout') && domP.includes('  - backend/apps/x/views.py')
    && domP.includes("/usr/bin/git -C '/wt/g1' diff origin/main...HEAD"), domP)

  // --- review round 2, blocking finding from every reviewer
  r = await run('todo-review', { round: 2, prs: [pr({ round: 2, size: 'm' })] }, reviewStub({ lens: high, domain: high }))
  check('review: round 2 never repairs', byType(r.calls, 'todo-worker').length === 0)
  check('review: the same blocking finding from every reviewer counts once and is refuted once',
    r.result.results[0].blocking.length === 1 && r.result.results[0].findings.length === 5
    && refuteCalls(r.calls).length === 2, r.result)

  // --- review: one bug phrased differently by different reviewers is refuted once
  const phrased = n => ({ reviewed_range: 'x', findings: [{ severity: n === 'drf' ? 'critical' : 'high', file: 'a.py', line: 1,
    summary: `bug as seen by ${n}`, suggested_fix: '' }] })
  r = await run('todo-review', { round: 2, prs: [pr({ round: 2 })] },
    reviewStub({ lens: (p, o) => phrased(o.label.split(':')[0]), domain: (p, o) => phrased(o.agentType === 'django-drf-reviewer' ? 'drf' : 'cc') }))
  const one = r.result.results[0].blocking
  check('review: blocking findings on one line collapse to one, keeping every phrasing, refuted once',
    one.length === 1 && one[0].also.length === 4 && refuteCalls(r.calls).length === 2, one)
  check('review: the collapsed finding keeps the most severe representative',
    one[0].severity === 'critical' && one[0].summary === 'bug as seen by drf', one)
  const refP = refuteCalls(r.calls)[0].prompt
  check('review: the refuters get every phrasing and must refute each one',
    ['drf', 'cc', 'bugs-correctness', 'bugs-security-data', 'bugs-contracts-tests'].every(n => refP.includes(`bug as seen by ${n}`))
    && refP.includes('only if you can show EVERY one is wrong'), refP)
  r = await run('todo-review', { round: 2, prs: [pr({ round: 2 })] }, reviewStub({ lens: high,
    domain: { reviewed_range: 'x', findings: [{ ...high.findings[0], file: '/wt/g1/a.py', summary: 'abs path' }] } }))
  check('review: a worktree-absolute path and the repo-relative one are the same location',
    r.result.results[0].blocking.length === 1 && r.result.results[0].blocking[0].file === 'a.py'
    && refuteCalls(r.calls).length === 2, r.result.results[0].blocking)

  // --- review: refutation
  r = await run('todo-review', { round: 1, prs: [pr()] }, reviewStub({ lens: high, refute: wrong }))
  check('review: a finding both refuters refute stops blocking, is kept in `refuted`, and is not repaired',
    r.result.results[0].blocking.length === 0 && r.result.results[0].refuted.length === 1
    && r.result.results[0].refuted[0].refutations.length === 2 && byType(r.calls, 'todo-worker').length === 0, r.result)
  let votes = 0
  r = await run('todo-review', { round: 1, prs: [pr()] }, reviewStub({ lens: high, refute: () => (++votes === 1 ? wrong : holds) }))
  check('review: one refuter upholding the finding keeps it blocking', r.result.results[0].blocking.length === 1
    && byType(r.calls, 'todo-worker').length === 1, r.result)
  votes = 0
  r = await run('todo-review', { round: 1, prs: [pr()] }, reviewStub({ lens: high, refute: () => (++votes === 1 ? wrong : null) }))
  check('review: a dead refuter refutes nothing', r.result.results[0].blocking.length === 1, r.result)
  r = await run('todo-review', { round: 1, prs: [pr()] }, reviewStub({ lens: high, refute: null }))
  check('review: two dead refuters keep the finding blocking', r.result.results[0].blocking.length === 1
    && r.result.results[0].refuted.length === 0, r.result)
  r = await run('todo-review', { round: 1, prs: [pr()] }, reviewStub({ lens: low }))
  check('review: a non-blocking finding is not sent to refuters', refuteCalls(r.calls).length === 0)

  // --- review round 1: nothing blocking, and a repair that blocks
  // Todo 478: its own run (it used to read the previous case's `r`, which happened to be the same stub).
  r = await run('todo-review', { round: 1, prs: [pr()] }, reviewStub({ lens: low }))
  check('review: round 1 with no blocking finding does not repair',
    byType(r.calls, 'todo-worker').length === 0 && r.result.results[0].repair === null
    && r.result.results[0].blocking.length === 0 && r.result.results[0].reviewers_ok, r.result)
  r = await run('todo-review', { round: 1, prs: [pr()] },
    reviewStub({ lens: high, repair: worker({ status: 'blocked', blockers: 'needs the deps lane' }) }))
  check('review: a blocked repair carries its blockers and is not verified',
    r.result.results[0].repair_blockers === 'needs the deps lane' && r.result.results[0].verdict === null
    && byType(r.calls, 'todo-verifier').length === 0, r.result)

  // --- review: residue (todo 480). The repair's `git add -A` would commit what a reviewer left in the worktree.
  r = await run('todo-review', { round: 1, prs: [pr()] }, reviewStub({ lens: high }))
  const chk = residueCalls(r.calls)
  check('review 480: an unchanged worktree is checked, then repaired as before', chk.length === 1
    && chk[0].opts.agentType === 'todo-reviewer' && chk[0].prompt.includes(`Run exactly this command, once, and nothing else: ${pr().residue_check}`)
    && byType(r.calls, 'todo-worker').length === 1 && r.result.results[0].reviewers_ok
    && JSON.stringify(r.result.results[0].residue) === '[]', r.result)
  check('review 480: the residue check runs after every reviewer and refuter, before the repair',
    r.calls.findIndex(c => isResidue(c.opts)) > Math.max(...r.calls.map((c, i) => (c.opts.agentType !== 'todo-worker'
      && c.opts.agentType !== 'todo-verifier' && !isResidue(c.opts) ? i : -1)))
    && r.calls.findIndex(c => isResidue(c.opts)) < r.calls.findIndex(c => c.opts.agentType === 'todo-worker'))
  r = await run('todo-review', { round: 1, prs: [pr()] },
    reviewStub({ lens: high, residue: { changed: ['backend/probe.py', 'backend/apps/x/views.py'], error: '' } }))
  check('review 480: a file a reviewer left stops the repair, names the paths, and marks the round incomplete',
    byType(r.calls, 'todo-worker').length === 0 && byType(r.calls, 'todo-verifier').length === 0
    && r.result.results[0].reviewers_ok === false && r.result.results[0].repair === null
    && r.result.results[0].residue.join() === 'backend/probe.py,backend/apps/x/views.py', r.result)
  r = await run('todo-review', { round: 1, prs: [pr()] }, reviewStub({ lens: high, residue: null }))
  check('review 480: a dead residue check stops the repair (fails closed)',
    byType(r.calls, 'todo-worker').length === 0 && r.result.results[0].reviewers_ok === false
    && r.result.results[0].residue.length === 1, r.result)
  r = await run('todo-review', { round: 1, prs: [pr()] }, reviewStub({ lens: high, residue: { changed: [], error: 'state: no such group' } }))
  check('review 480: a check that reports an error stops the repair, even with an empty list',
    byType(r.calls, 'todo-worker').length === 0 && r.result.results[0].reviewers_ok === false
    && /residue check failed: state: no such group/.test(r.result.results[0].residue[0]), r.result)
  r = await run('todo-review', { round: 2, prs: [pr({ round: 2 })] }, reviewStub({ lens: high }))
  check('review 480: with no repair (round 2) the workflow leaves the check to ingest-review (residue null)',
    residueCalls(r.calls).length === 0 && r.result.results[0].residue === null, r.result)

  // --- review: routing (todo 478). The path rules decide who must review; the router can only add.
  r = await run('todo-review', { round: 1, prs: [pr({ changed_files: ['docs/x.md'] })] }, reviewStub({ route: routed() }))
  check('review: a docs-only change that routes to no domain reviewer is still complete',
    r.result.results[0].reviewers_ok === true && r.result.results[0].routed.length === 0, r.result)
  const dispatched = calls => new Set(calls.map(c => c.opts.agentType).filter(t => !['todo-reviewer',
    'code-review-orchestrator', 'todo-worker', 'todo-verifier'].includes(t)))
  for (const [label, files, want] of [
    ['an apps .py', ['backend/apps/x/views.py'], ['django-drf-reviewer', 'cross-cutting-reviewer']],
    ['a blog page', ['backend/apps/blog/models.py'], ['wagtail-reviewer', 'cross-cutting-reviewer']],
    ['a web/src .tsx', ['web/src/A.tsx'], ['react-typescript-reviewer']],
    ['a mobile .dart', ['plant_community_mobile/lib/a.dart'], ['flutter-dart-reviewer']],
    ['a mobile auth .dart', ['plant_community_mobile/lib/auth/session.dart'], ['flutter-dart-reviewer', 'flutter-firebase-reviewer']],
    ['a mobile firebase file', ['plant_community_mobile/lib/firebase_options.dart'], ['flutter-dart-reviewer', 'flutter-firebase-reviewer']],
    ['a firestore rules file', ['firebase/firestore.rules'], ['flutter-firebase-reviewer', 'cross-cutting-reviewer']],
    ['a storage rules file elsewhere', ['storage.rules'], ['flutter-firebase-reviewer', 'cross-cutting-reviewer']],
    ['a cloud function', ['firebase/functions/src/index.ts'], ['flutter-firebase-reviewer', 'cross-cutting-reviewer', 'firebase-cloudfunction-reviewer']],
    ['a celery task', ['backend/apps/x/tasks.py'], ['django-drf-reviewer', 'celery-async-reviewer', 'cross-cutting-reviewer']],
    ['an api module', ['web/src/api/client.ts'], ['react-typescript-reviewer', 'cross-cutting-reviewer']],
    ['a web test', ['web/src/A.test.tsx'], ['react-typescript-reviewer', 'cross-cutting-reviewer']],
    ['a script .py', ['scripts/todos/state.py'], ['cross-cutting-reviewer']],
  ]) {
    r = await run('todo-review', { round: 1, prs: [pr({ changed_files: files })] }, reviewStub({ route: routed() }))
    const got = dispatched(r.calls)
    check(`review: path rules dispatch ${want.join(' + ')} for ${label}, though the router chose none`,
      got.size === want.length && want.every(id => got.has(id)) && r.result.results[0].reviewers_ok === true
      && r.result.results[0].floor_added.length === want.length, [...got])
  }
  const mixed = ['backend/apps/x/views.py', 'plant_community_mobile/lib/a.dart', 'web/src/A.tsx']
  r = await run('todo-review', { round: 1, prs: [pr({ changed_files: mixed })] },
    reviewStub({ route: routed('wagtail-reviewer') }))
  const promptOf = id => byType(r.calls, id)[0].prompt
  check('review: each reviewer only the path rules chose gets only its own files',
    promptOf('flutter-dart-reviewer').includes('  - plant_community_mobile/lib/a.dart')
    && !promptOf('flutter-dart-reviewer').includes('views.py') && !promptOf('react-typescript-reviewer').includes('.dart')
    && !promptOf('cross-cutting-reviewer').includes('A.tsx'), promptOf('flutter-dart-reviewer'))
  check('review: a reviewer only the router chose (wagtail, by content) gets every file',
    mixed.every(f => promptOf('wagtail-reviewer').includes(`  - ${f}`)), promptOf('wagtail-reviewer'))
  check('review: router choices and path rules are merged, and floor_added names only what the router missed',
    r.result.results[0].floor_added.join() ===
      'django-drf-reviewer,react-typescript-reviewer,flutter-dart-reviewer,cross-cutting-reviewer'
    && dispatched(r.calls).size === 5, r.result.results[0])
  const blogPlus = ['backend/apps/blog/models.py', 'backend/packages/wagtail_forum/models.py']
  r = await run('todo-review', { round: 1, prs: [pr({ changed_files: blogPlus })] }, reviewStub({ route: routed('wagtail-reviewer') }))
  check('review: a reviewer both the path rules and the router chose gets every file, not just its path matches',
    blogPlus.every(f => byType(r.calls, 'wagtail-reviewer')[0].prompt.includes(`  - ${f}`)), byType(r.calls, 'wagtail-reviewer')[0].prompt)

  // --- review: the path rules mirror code-review-orchestrator.md's routing table, row for row
  const table = fs.readFileSync(path.join(ROOT, '.claude', 'agents', 'code-review-orchestrator.md'), 'utf8')
    .split('\n').filter(l => /^\| `|^\| Any /.test(l))
    .map(l => { const [, pat, agents] = l.split(/\s*(?<!\\)\|\s*/); return { pat, agents: [...agents.matchAll(/`([a-z-]+-reviewer)`/g)].map(m => m[1]) } })
  const src = source('todo-review')
  const rows = [...src.matchAll(/\{ row: '((?:[^'\\]|\\.)*)',\s*agents: \[([^\]]*)\]/g)]
    .map(m => ({ pat: m[1].replace(/\\\\/g, '\\'), agents: [...m[2].matchAll(/'([a-z-]+)'/g)].map(x => x[1]) }))
  check('review: the routing table has 12 rows and the workflow mirrors each one (pattern and agents)',
    table.length === 12 && rows.length === table.length
    && table.every((t, i) => rows[i].pat === t.pat && rows[i].agents.join() === t.agents.join()),
    { table, rows })

  r = await run('todo-review', { round: 1, prs: [pr()] },
    reviewStub({ route: routed('cross-cutting-reviewer', 'cross-cutting-reviewer') }))
  check('review: a reviewer routed twice runs once', byType(r.calls, 'cross-cutting-reviewer').length === 1)

  // --- review: any dead reviewer leaves part of the diff unreviewed, so the review is incomplete
  for (const [label, stub] of [
    ['a dead bug lens', reviewStub({ lens: (p, o) => (o.label.startsWith('bugs-security') ? null : high) })],
    ['a dead orchestrator', reviewStub({ lens: high, route: null })],
    ['a dead domain reviewer', reviewStub({ lens: high, domain: (p, o) => (o.agentType === 'cross-cutting-reviewer' ? null : none) })],
  ]) {
    r = await run('todo-review', { round: 1, prs: [pr()] }, stub)
    check(`review: ${label} marks the review incomplete, with no refute or repair`,
      r.result.results[0].reviewers_ok === false && byType(r.calls, 'todo-worker').length === 0
      && refuteCalls(r.calls).length === 0 && r.result.results[0].blocking.length === 0, r.result)
  }
  r = await run('todo-review', { round: 1, prs: [pr()] }, () => null)
  check('review: every reviewer dead marks the review incomplete', r.result.results[0].reviewers_ok === false, r.result)

  // --- todo 478: each reviewer's own range is relayed (replaces a range check the stubs could never fail)
  r = await run('todo-review', { round: 2, prs: [pr({ round: 2 })] }, reviewStub({
    lens: (p, o) => ({ ...none, reviewed_range: `range of ${o.label}` }),
    domain: (p, o) => ({ ...none, reviewed_range: `range of ${o.label}` }) }))
  const labels = r.calls.filter(c => c.opts.schema && c.opts.schema.properties.findings).map(c => c.opts.label)
  check('478: the result relays every reviewer\'s own reviewed_range, once each',
    labels.length === 5 && labels.every(l => r.result.results[0].ranges.filter(x => x === `range of ${l}`).length === 1),
    { labels, ranges: r.result.results[0].ranges })

  // --- todo 478 AC: a refute judgment that is null as a whole keeps ITS finding blocking. Two candidates:
  // a.py:1's inner parallel throws (null judgment), a.py:2 is refuted by both. Dropping nulls
  // (judged.filter(Boolean)) would shift a.py:2's votes onto a.py:1 and refute the wrong finding.
  const two = { reviewed_range: 'x', findings: [{ severity: 'high', file: 'a.py', line: 1, summary: 'one', suggested_fix: '' },
    { severity: 'high', file: 'a.py', line: 2, summary: 'two', suggested_fix: '' }] }
  const nullJudgment = mutate => run('todo-review', { round: 2, prs: [pr({ round: 2 })] },
    reviewStub({ lens: two, refute: (p, o) => (o.label.endsWith(':a.py:1') ? { refuted: true, reason: 'THROW' } : wrong) }),
    { allowErrors: true, parallelThrows: out => out.length === 2 && out.every(v => v && v.reason === 'THROW'), mutate })
  // The case's own verdict, so the same check can be run on the real workflow and on a known-bad one.
  const keepsNullBlocking = rr => rr.errors.length === 1 && rr.result.results[0].blocking.map(f => f.line).join() === '1'
    && rr.result.results[0].refuted.map(f => f.line).join() === '2'
  r = await nullJudgment(null)
  const res478 = r.result.results[0]
  check('478 AC2: a null refute judgment keeps its own finding blocking, and the other is still refuted',
    keepsNullBlocking(r), { errors: r.errors, blocking: res478.blocking, refuted: res478.refuted })
  const dropped = await nullJudgment(['const votes = judged[i] || []', 'const votes = judged.filter(Boolean)[i] || []'])
  check('478 AC2: that test fails when null judgments are dropped (judged.filter(Boolean))',
    !keepsNullBlocking(dropped) && dropped.result.results[0].refuted.map(f => f.line).join() === '1',
    dropped.result.results[0])

  // --- todo 478: the critical that takes over as representative does not repeat its own words in `also`
  const swap = (p, o) => ({ reviewed_range: 'x', findings: [{ severity: o.label.startsWith('bugs-correctness') ? 'critical' : 'high',
    file: 'a.py', line: 1, summary: o.label.startsWith('bugs-security') || o.label.startsWith('bugs-correctness') ? 'same words' : 'first words',
    suggested_fix: '' }] })
  r = await run('todo-review', { round: 2, prs: [pr({ round: 2, changed_files: ['docs/x.md'] })] },
    reviewStub({ lens: swap, route: routed() }))
  const rep478 = r.result.results[0].blocking[0]
  check('478: the critical representative never repeats its own summary in also',
    rep478.severity === 'critical' && rep478.summary === 'same words' && !rep478.also.includes('same words')
    && rep478.also.includes('first words'), rep478)

  // --- todo 478: the /private/tmp alias of the worktree is the same location
  r = await run('todo-review', { round: 2, prs: [pr({ round: 2, worktree: '/tmp/sweep/g1' })] }, reviewStub({ lens: high,
    domain: { reviewed_range: 'x', findings: [{ ...high.findings[0], file: '/private/tmp/sweep/g1/a.py', summary: 'alias' }] } }))
  check('478: a /private/tmp path and the /tmp worktree are one location',
    r.result.results[0].blocking.length === 1 && r.result.results[0].blocking[0].file === 'a.py', r.result.results[0].blocking)

  // --- todo 478: a style-level checklist finding is capped at medium unless it names what breaks
  r = await run('todo-review', { round: 1, prs: [pr()] }, reviewStub())
  check('478: domain reviewers are told a pattern deviation is at most medium without a concrete failure',
    byType(r.calls, 'django-drf-reviewer')[0].prompt.includes('A checklist or pattern-library deviation is at most medium'))

  // --- todo 478: every agent the workflow dispatches in the PR worktree is one the git guard limits
  const guardSrc = fs.readFileSync(path.join(ROOT, 'scripts', 'todos', 'worker_git_guard.py'), 'utf8')
  const guarded = new Set([...(guardSrc.match(/REVIEW_AGENTS = \(([^)]*)\)/) || ['', ''])[1].matchAll(/"([a-z-]+)"/g)]
    .map(m => m[1]).concat(['todo-worker', 'todo-verifier', 'todo-reviewer']))
  const reviewSrc = source('todo-review')
  const declared = [...(reviewSrc.match(/const DOMAIN_REVIEWERS = \[([^\]]*)\]/) || ['', ''])[1].matchAll(/'([a-z-]+)'/g)].map(m => m[1])
  const typed = [...reviewSrc.matchAll(/agentType: '([a-z-]+)'/g)].map(m => m[1])
  check('478: DOMAIN_REVIEWERS, the orchestrator and every agentType in todo-review.js are guarded',
    declared.length === 8 && [...declared, ...typed].every(id => guarded.has(id)) && guarded.size === 12,
    { missing: [...declared, ...typed].filter(id => !guarded.has(id)), guarded: [...guarded] })

  // --- todo 481: a dead router still dispatches the path-routed reviewers
  r = await run('todo-review', { round: 1, prs: [pr({ changed_files: ['web/src/A.tsx', 'docs/x.md'] })] },
    reviewStub({ route: null }))
  check('481 AC1: a dead router still dispatches the path-routed reviewers, and records routing_failed',
    byType(r.calls, 'react-typescript-reviewer').length === 1 && r.result.results[0].routing_failed === true, r.result.results[0])
  check('481 AC1: with no .py changed, the round is complete without the router',
    r.result.results[0].reviewers_ok === true, r.result.results[0])
  r = await run('todo-review', { round: 1, prs: [pr({ changed_files: ['backend/apps/blog/models.py'] })] },
    reviewStub({ route: null }))
  check('481: a .py inside apps/blog/ is already wagtail\'s by path, so the round is complete',
    r.result.results[0].reviewers_ok === true && byType(r.calls, 'wagtail-reviewer').length === 1, r.result.results[0])
  r = await run('todo-review', { round: 1, prs: [pr({ changed_files: ['backend/packages/wagtail_forum/models.py'] })] },
    reviewStub({ lens: high, route: null }))
  check('481: a .py outside apps/blog/ could need wagtail by content, so the round is incomplete (no refute or repair)',
    r.result.results[0].reviewers_ok === false && byType(r.calls, 'cross-cutting-reviewer').length === 1
    && refuteCalls(r.calls).length === 0 && byType(r.calls, 'todo-worker').length === 0, r.result.results[0])
  r = await run('todo-review', { round: 1, prs: [pr()] }, reviewStub())
  check('481: a live router reports routing_failed false', r.result.results[0].routing_failed === false)

  // --- todo 481: a changed file's name never reaches a shell through the router
  const evil = ["backend/apps/x/a'$(touch /tmp/pwned).py", 'backend/apps/x/b`id`.py', 'backend/apps/x/c\nd.py']
  r = await run('todo-review', { round: 1, prs: [pr({ changed_files: evil })] }, reviewStub())
  const evilP = byType(r.calls, 'code-review-orchestrator')[0].prompt
  const command = (evilP.match(/exactly: (.*)$/m) || ['', ''])[1]
  check('481 AC2: the router\'s one command is a fixed git grep with no changed file name in it',
    command === "/usr/bin/git -C '/wt/g1' grep -l -e 'import wagtail' -e 'from wagtail' -e 'from .models import.*Page' -- '*.py'"
    && evil.every(f => !command.includes(f)) && evilP.includes('never put a file name into a command'), evilP)
  check('481 AC2: the names reach the router only as JSON data (quoted and escaped)',
    evilP.includes(JSON.stringify(evil)) && !evilP.includes('\nd.py'), evilP)
  const hook = path.join(ROOT, '.claude', 'hooks', 'guard-todo-worker-git.sh')
  const verdictFor = cmd => require('child_process').execFileSync('bash', [hook], {
    input: JSON.stringify({ agent_type: 'code-review-orchestrator', tool_input: { command: cmd } }) }).toString()
  check('481 AC2: the git guard allows that exact command for the router, and denies git grep -O',
    verdictFor(command) === '' && verdictFor(command.replace('grep -l', 'grep -Otouch')).includes('"deny"'))

  // --- todo 483: the repair stages only what it changed; the verifier checks nothing else is staged
  r = await run('todo-review', { round: 1, prs: [pr({ untracked_before: ['notes.txt'] })] },
    reviewStub({ lens: high, repair: worker({ files_changed: ['backend/apps/x/views.py'] }) }))
  const repair483 = byType(r.calls, 'todo-worker')[0].prompt
  const verify483 = byType(r.calls, 'todo-verifier')[0].prompt
  check('483: the repair prompt names the untracked files and says to stage only the paths it changed',
    repair483.includes('UNTRACKED_BEFORE: ["notes.txt"]') && repair483.includes('never `git add -A`')
    && repair483.includes('Never stage, edit or delete a path in UNTRACKED_BEFORE'), repair483)
  check('483: the post-repair verifier gets FILES_CHANGED and UNTRACKED_BEFORE, and fails on any other staged path',
    verify483.includes('FILES_CHANGED: ["backend/apps/x/views.py"]') && verify483.includes('UNTRACKED_BEFORE: ["notes.txt"]')
    && verify483.includes('staged paths the repair did not change'), verify483)

  // --- todo 476: the post-repair verifier re-runs once after a null verdict, tree check first
  let checks476 = 0
  r = await run('todo-review', { round: 1, prs: [pr()] },
    reviewStub({ lens: high, check: () => (++checks476 === 1 ? null : verdict('pass')) }))
  const again476 = byType(r.calls, 'todo-verifier')
  check('476 AC4: a null post-repair verdict re-runs the verifier once, telling it to check the tree first',
    again476.length === 2 && !again476[0].prompt.includes('died part-way') && again476[1].prompt.includes('Check the tree first')
    && r.result.results[0].verdict.verdict === 'pass' && byType(r.calls, 'todo-worker').length === 1, r.result.results[0])
  r = await run('todo-review', { round: 1, prs: [pr()] }, reviewStub({ lens: high, check: null }))
  check('476: two null post-repair verdicts give verdict null, with no third run',
    byType(r.calls, 'todo-verifier').length === 2 && r.result.results[0].verdict === null, r.result.results[0])

  // --- todo 476: the execute re-run that finds only a dirty tree does not retry the worker
  const dirty = verdict('fail', { ac: [{ todo: '1', index: 0, verified: false, note: 'not run' }],
    reasons: ['tree not clean before verification: out.txt'] })
  verifies = 0
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] },
    (p, o) => (o.agentType === 'todo-worker' ? worker() : ++verifies === 1 ? null : dirty))
  check('476 AC3: a re-run verdict failing only on a dirty tree is returned without a worker retry',
    byType(r.calls, 'todo-worker').length === 1 && byType(r.calls, 'todo-verifier').length === 2
    && byType(r.calls, 'todo-verifier')[1].prompt.includes('Check the tree first')
    && !r.result.results[0].retried && r.result.results[0].verdict.verdict === 'fail', r.result.results[0])
  verifies = 0
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] }, (p, o) => (o.agentType === 'todo-worker' ? worker()
    : ++verifies === 1 ? null : verifies === 2 ? { ...dirty, reasons: [...dirty.reasons, 'acceptance criteria were edited'] }
      : verdict('pass')))
  check('476: a re-run that also found a real problem still retries the worker',
    byType(r.calls, 'todo-worker').length === 2 && r.result.results[0].retried, r.result.results[0])
  verifies = 0
  r = await run('todo-execute', { run_id: 'r', briefs: [brief()] },
    (p, o) => (o.agentType === 'todo-worker' ? worker() : ++verifies === 1 ? dirty : verdict('pass')))
  check('476: a FIRST verifier that finds a dirty tree (the worker left it) still gets the worker retry',
    byType(r.calls, 'todo-worker').length === 2 && r.result.results[0].retried, r.result.results[0])

  // --- todo 476: the fixture validator itself
  check('476 AC1: an unknown schema type is reported, not thrown',
    JSON.stringify(schemaErrors(1, { type: 'weird' })) === '["$: unknown schema type \\"weird\\""]'
    && schemaErrors(1.5, { type: 'number' }).length === 0 && schemaErrors(null, { type: ['string', 'null'] }).length === 0
    && schemaErrors(3, { type: ['string', 'null'] })[0] === '$: not string or null')
  check('476 AC2: items are checked whenever present, even without type: array',
    schemaErrors(['ok', 7], { items: { type: 'string' } }).join() === '$[1]: not string'
    && schemaErrors({ a: [1] }, { properties: { a: { items: { type: 'string' } } } }).join() === '$.a[0]: not string')

  // --- todo 528: execute-args made the worktree; the worker runs there, and a dead one still names it
  const schemaOf = (src, name) => new Function(`${schemaBlock(src, name)}; return ${name}`)()
  r = await run('todo-execute', { run_id: 'r', briefs: [brief({ worktree: '/wt/made', branch: 'worktree-sweep-r-g1' })] },
    (p, o) => (o.agentType === 'todo-worker' ? worker({ worktree: '/wt/made' }) : verdict('pass')))
  const made = byType(r.calls, 'todo-worker')[0]
  check('528: a brief with a worktree runs the implementer there, without isolation, told WORKTREE',
    made.opts.isolation === undefined && made.prompt.split('\n')[1] === 'WORKTREE: /wt/made', made)
  r = await run('todo-execute', { run_id: 'r', briefs: [brief({ worktree: '/wt/made' })] }, () => null)
  check('528 AC2: a worker that returns nothing leaves the brief\'s worktree on its result',
    r.result.results[0].worker === null && r.result.results[0].worktree === '/wt/made', r.result)
  r = await run('todo-execute', { run_id: 'r', briefs: [brief({ worktree: '/wt/made' })] },
    (p, o) => { if (o.agentType === 'todo-worker') throw new Error('stage died') }, { allowErrors: true })
  check('528: ... and so does a stage that threw (the null-row fallback)',
    r.result.results[0].worktree === '/wt/made' && r.errors.length === 1, r.result)
  // AC1: the stated summary limit is below the schema's maxLength, in the agent doc and both workflows.
  const workerDoc = fs.readFileSync(path.join(ROOT, '.claude', 'agents', 'todo-worker.md'), 'utf8')
  const stated = src => Number((src.match(/summary(?:`)? (?:at most|under) (\d+) characters/) || [])[1])
  const limitsHold = srcs => ['todo-execute', 'todo-review'].every(n => {
    const max = schemaOf(srcs[n], 'WORKER').properties.summary.maxLength
    return stated(srcs[n]) > 0 && stated(srcs[n]) < max && stated(srcs.doc) > 0 && stated(srcs.doc) < max
  })
  const srcs = { 'todo-execute': source('todo-execute'), 'todo-review': source('todo-review'), doc: workerDoc }
  check('528 AC1: todo-worker.md and both workflows state a summary limit below WORKER\'s maxLength',
    limitsHold(srcs) && stated(workerDoc) === 400 && stated(srcs['todo-execute']) === 400, srcs.doc.match(/summary.{0,40}/g))
  check('528 AC1: ... and that check fails on a stated limit at the maxLength',
    !limitsHold({ ...srcs, 'todo-execute': srcs['todo-execute'].replace('summary under 400', 'summary under 600') }))
  r = await run('todo-execute', { run_id: 'r', briefs: [brief({ worktree: '/wt/made' })] }, (p, o) => (o.agentType ===
    'todo-worker' ? worker({ worktree: '/wt/made' }) : verdict('fail')))
  check('528: the implement and retry prompts carry the limits',
    byType(r.calls, 'todo-worker').length === 2
    && byType(r.calls, 'todo-worker').every(c => c.prompt.includes('Keep summary under 400 characters')))
  r = await run('todo-review', { round: 1, prs: [pr()] }, reviewStub({ lens: high }))
  check('528: the repair prompt carries the limits',
    byType(r.calls, 'todo-worker')[0].prompt.includes('Keep summary under 400 characters'))

  // --- todo 494 F17: the record reverifyWorker builds is a valid WORKER record (a missing branch would crash ingest)
  const rvOk = async mutate => {
    const rr = await run('todo-execute', { run_id: 'r', briefs: [brief({ reverify: rv })] },
      () => verdict('pass', { tree_id_before: 'T9', tree_id_after: 'T9' }), { mutate, badFixtures: true })
    const w = rr.result.results[0].worker
    return Boolean(w) && schemaErrors(w, schemaOf(source('todo-execute'), 'WORKER')).length === 0
  }
  check('494 F17: reverifyWorker\'s record matches the WORKER schema', await rvOk(null))
  check('494 F17: ... and that check fails when the record loses the brief\'s fields (no branch)',
    !(await rvOk(['status: \'staged\', ...b.reverify,', 'status: \'staged\', worktree: b.reverify.worktree,'])))
  // --- todo 494 F8: the implement stage is async, so a runtime that chains .then on it still gets the record
  r = await run('todo-execute', { run_id: 'r', briefs: [brief({ reverify: rv })] },
    () => verdict('pass', { tree_id_before: 'T9', tree_id_after: 'T9' }), { chain: true })
  check('494 F8: a re-verify still returns its record when the runtime chains .then on each stage',
    r.result.results[0].worker && r.result.results[0].worker.tree_id === 'T9', r.result)
  r = await run('todo-execute', { run_id: 'r', briefs: [brief({ reverify: rv })] },
    () => verdict('pass', { tree_id_before: 'T9', tree_id_after: 'T9' }),
    { chain: true, allowErrors: true, mutate: ['  async (plan, b) => {\n    if (b.reverify)', '  (plan, b) => {\n    if (b.reverify)'] })
  check('494 F8: ... and that check fails on a synchronous stage', r.errors.length > 0 && r.result.results[0] === null
    || r.result.results[0].worker === null, r.result)
  // --- todo 494 F4: each re-point marker is a JSON string on the REPOINTS line, in both workflows
  const odd = { 1: [{ index: 0, to: '8', marker: 'a "quoted"; marker' }] }
  r = await run('todo-execute', { run_id: 'r', briefs: [brief({ reverify: rv, repoints: odd })] },
    () => verdict('pass', { tree_id_before: 'T9', tree_id_after: 'T9' }))
  const execLine = byType(r.calls, 'todo-verifier')[0].prompt.split('\n').find(l => l.startsWith('REPOINTS:'))
  r = await run('todo-review', { round: 1, prs: [pr({ repoints: odd })] }, reviewStub({ lens: high }))
  const reviewLine = byType(r.calls, 'todo-verifier')[0].prompt.split('\n').find(l => l.startsWith('REPOINTS:'))
  check('494 F4: a marker with a quote and a semicolon is JSON-quoted on the REPOINTS line (execute and review)',
    execLine === 'REPOINTS: 1#0 "a \\"quoted\\"; marker"' && reviewLine === execLine, [execLine, reviewLine])

  // --- todo 529 item 3: todo-followups curates each PR's follow-ups, then a refuter tries to refute them
  const fg = (over = {}) => ({ run_id: 'r', group: 'g1', ids: ['1'], pr: 900, main_root: '/main',
    followups: ['medium: a.py:9 real', 'low: a.py:2 nit', 'low: b.py:30 gone'], ...over })
  const item = (over = {}) => ({ severity: 'medium', file: 'a.py', line: 9, summary: 'real', also: ['nit'],
    on_main: 'present', note: 'still there', ...over })
  const curated = { pr_on_main: true, items: [item(), item({ severity: 'low', file: 'b.py', line: 30, summary: 'gone', also: [],
    on_main: 'fixed', note: 'removed by #901' }), item({ severity: 'low', file: 'c.py', line: 4, summary: 'maybe', also: [] })] }
  const isCurator = o => Boolean(o.schema && o.schema.properties.items)
  r = await run('todo-followups', { run_id: 'r', groups: [fg()] },
    (p, o) => (isCurator(o) ? curated : { judgments: [{ index: 0, refuted: false, reason: 'holds' },
      { index: 1, refuted: true, reason: 'handled upstream' }] }))
  const fr = r.result.results[0]
  check('529 item 3: one curator, then one refuter per PR, both the guarded read-only todo-reviewer',
    r.calls.length === 2 && r.calls.every(c => c.opts.agentType === 'todo-reviewer') && isCurator(r.calls[0].opts), r.calls)
  check('529 item 3: the curator gets the follow-ups as JSON data and reads only origin/main through git',
    r.calls[0].prompt.includes(JSON.stringify(fg().followups)) && r.calls[0].prompt.includes("/usr/bin/git -C '/main' show origin/main:")
    && r.calls[0].prompt.includes('Never read files from disk'), r.calls[0].prompt)
  check('529 item 3: an item fixed on main is dropped before the refuter, and a refuted one after it',
    fr.kept.length === 1 && fr.kept[0].file === 'a.py' && fr.refuter_ok
    && fr.dropped.map(d => d.why.split(':')[0]).join() === 'fixed on main,refuted'
    && !r.calls[1].prompt.includes('b.py'), fr)
  r = await run('todo-followups', { run_id: 'r', groups: [fg()] },
    (p, o) => (isCurator(o) ? { ...curated, pr_on_main: false } : { judgments: [] }))
  check('529 repair: a PR not on origin/main drops nothing as fixed and gets no refuter (left uncurated)',
    r.result.results[0].kept === null && r.result.results[0].dropped.length === 0 && r.calls.length === 1
    && /PR #900 is not on origin\/main/.test(r.result.results[0].why), r.result)
  check('529 repair: the curator first checks the PR\'s squash commit is on origin/main',
    r.calls[0].prompt.includes("/usr/bin/git -C '/main' log -1 --format=%h --fixed-strings --grep='(#900)' origin/main")
    && !r.calls[0].prompt.includes('about to be'), r.calls[0].prompt)
  r = await run('todo-followups', { run_id: 'r', groups: [fg()] }, () => null)
  check('529 item 3: a dead curator curates nothing (kept null: the stored list stays, marked uncurated)',
    r.result.results[0].kept === null && r.calls.length === 1, r.result)
  r = await run('todo-followups', { run_id: 'r', groups: [fg()] }, (p, o) => (isCurator(o) ? curated : null))
  check('529 item 3: a dead refuter refutes nothing (every open item is kept)',
    r.result.results[0].kept.length === 2 && r.result.results[0].refuter_ok === false, r.result)
  r = await run('todo-followups', { run_id: 'r', groups: [fg({ refuted: ['critical: x.py:1 secret'] })] },
    (p, o) => (isCurator(o) ? curated : { judgments: [] }))
  check('529 item 3: a refuted line never reaches the curator or the refuter, even if passed in',
    r.calls.every(c => !c.prompt.includes('x.py:1 secret')), r.calls.map(c => c.prompt))
  const reviewerVerdict = cmd => require('child_process').execFileSync('bash', [hook], {
    input: JSON.stringify({ agent_type: 'todo-reviewer', tool_input: { command: cmd } }) }).toString()
  const curatorCmds = [`/usr/bin/git -C '${ROOT}' show origin/main:scripts/todos/state.py`,
    `/usr/bin/git -C '${ROOT}' grep -n FOLLOWUP_CAP origin/main -- scripts/todos/state.py`,
    `/usr/bin/git -C '${ROOT}' log -1 --format=%h --fixed-strings --grep='(#900)' origin/main`]
  check('529 item 3: the git guard allows the curator\'s three read commands against the main checkout',
    curatorCmds.every(c => reviewerVerdict(c) === '') && reviewerVerdict(`/usr/bin/git -C '${ROOT}' add x`).includes('"deny"'),
    curatorCmds.map(reviewerVerdict))
  const followSrc = source('todo-followups')
  const followTypes = [...followSrc.matchAll(/agentType: '([a-z-]+)'/g)].map(m => m[1])
  check('529 item 3: every agentType in todo-followups.js is one the git guard limits to read-only git',
    followTypes.length === 2 && followTypes.every(t => t === 'todo-reviewer') && guarded.has('todo-reviewer'), followTypes)

  // --- schemas stay identical across files
  for (const name of ['WORKER', 'VERDICT']) {
    check(`${name} schema is identical in execute and review`,
      schemaBlock(source('todo-execute'), name) !== '' && schemaBlock(source('todo-execute'), name) === schemaBlock(source('todo-review'), name))
  }

  console.log()
  if (failures.length) {
    console.log(`FAILED: ${failures.length} check(s): ${failures.join(', ')}`)
    process.exit(1)
  }
  console.log('All checks passed.')
}

main().catch(e => { console.error(e); process.exit(1) })
