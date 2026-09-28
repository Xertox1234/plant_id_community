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

// The subset of JSON Schema the workflows use: type, properties, required, enum, maxLength, items,
// maxItems. Returns a list of problems, empty when `value` matches (todo 468).
const IS = { object: v => v !== null && typeof v === 'object' && !Array.isArray(v), array: Array.isArray,
  string: v => typeof v === 'string', integer: Number.isInteger, boolean: v => typeof v === 'boolean' }
function schemaErrors(value, schema, at = '$') {
  if (schema.type && !IS[schema.type](value)) return [`${at}: not ${schema.type}`]
  const errs = []
  if (schema.enum && !schema.enum.includes(value)) errs.push(`${at}: ${JSON.stringify(value)} not in enum`)
  if (schema.maxLength !== undefined && value.length > schema.maxLength) errs.push(`${at}: longer than ${schema.maxLength}`)
  if (schema.type === 'array') {
    if (schema.maxItems !== undefined && value.length > schema.maxItems) errs.push(`${at}: more than ${schema.maxItems} items`)
    if (schema.items) value.forEach((v, i) => errs.push(...schemaErrors(v, schema.items, `${at}[${i}]`)))
  }
  if (schema.type === 'object') {
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
async function run(name, args, respond, { allowErrors = false, badFixtures = false } = {}) {
  const body = source(name).replace(/^export const meta/m, 'const meta')
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
        for (const stage of stages) value = await stage(value, item, i)
        return value
      } catch (e) {
        errors.push(String(e))
        return null
      }
    }))
  const parallel = async thunks => Promise.all(thunks.map(t => t().catch(e => { errors.push(String(e)); return null })))
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
  todo_paths: ['todos/archive/1-completed-p3-x.md'], origin_paths: ['todos/1-pending-p3-x.md'], ...over })
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

  // --- review round 1, size s, blocking finding
  const high = { reviewed_range: 'skill:code-review', findings: [{ severity: 'high', file: 'a.py', line: 1, summary: 'bug', suggested_fix: '' }] }
  r = await run('todo-review', { round: 1, prs: [pr()] },
    (p, o) => (o.agentType === 'general-purpose' ? high : o.agentType === 'todo-worker' ? worker() : verdict('pass')))
  check('review: size s gets only the bug reviewer', byType(r.calls, 'code-review-orchestrator').length === 0)
  const rep = byType(r.calls, 'todo-worker')
  check('review: round 1 repairs in the PR worktree', rep.length === 1 && rep[0].opts.isolation === undefined
    && rep[0].prompt.startsWith('MODE: repair') && rep[0].prompt.includes('/wt/g1'))
  check('review: the repair is re-verified', byType(r.calls, 'todo-verifier').length === 1)
  check('review: reviewer prompts name the explicit diff range',
    byType(r.calls, 'general-purpose')[0].prompt.includes('diff origin/main...HEAD'))
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
  check('review: the post-repair verifier ignores box state and knows Land ran',
    repairV.prompt.includes('Ignore `[ ]` vs `[x]`') && repairV.prompt.includes('Land has already flipped'), repairV.prompt)
  check('review: the post-repair verifier requires a command on every open criterion and re-runs each',
    repairV.prompt.includes('not already-checked-at-merge-base or re-pointed must carry a non-empty `command`; ' +
      're-run each yourself') && !repairV.prompt.includes('must have been re-run'), repairV.prompt)
  const bugP = byType(r.calls, 'general-purpose')[0].prompt
  check('review: the bug reviewer reviews the local diff, single-quoted, never via gh',
    bugP.includes("/usr/bin/git -C '/wt/g1' diff origin/main...HEAD") && bugP.includes('do not use gh')
    && !/Skill|against PR|gh pr/.test(bugP), bugP)

  // --- review round 2, size m, blocking finding
  r = await run('todo-review', { round: 2, prs: [pr({ round: 2, size: 'm' })] }, () => high)
  check('review: size m adds the checklist reviewer', byType(r.calls, 'code-review-orchestrator').length === 1)
  check('review: the checklist reviewer gets the single-quoted diff range',
    byType(r.calls, 'code-review-orchestrator')[0].prompt.includes("/usr/bin/git -C '/wt/g1' diff origin/main...HEAD"))
  check('review: round 2 never repairs', byType(r.calls, 'todo-worker').length === 0)
  check('review: the same blocking finding from both reviewers counts once',
    r.result.results[0].blocking.length === 1 && r.result.results[0].findings.length === 2, r.result)

  // --- review round 1: nothing blocking, and a repair that blocks
  const low = { reviewed_range: 'x', findings: [{ severity: 'low', file: 'a.py', line: 2, summary: 'nit', suggested_fix: '' }] }
  r = await run('todo-review', { round: 1, prs: [pr()] }, () => low)
  check('review: round 1 with no blocking finding does not repair',
    byType(r.calls, 'todo-worker').length === 0 && r.result.results[0].repair === null
    && r.result.results[0].blocking.length === 0 && r.result.results[0].reviewers_ok, r.result)
  r = await run('todo-review', { round: 1, prs: [pr()] }, (p, o) => (o.agentType === 'general-purpose' ? high
    : o.agentType === 'todo-worker' ? worker({ status: 'blocked', blockers: 'needs the deps lane' }) : verdict('pass')))
  check('review: a blocked repair carries its blockers and is not verified',
    r.result.results[0].repair_blockers === 'needs the deps lane' && r.result.results[0].verdict === null
    && byType(r.calls, 'todo-verifier').length === 0, r.result)

  r = await run('todo-review', { round: 2, prs: [pr({ round: 2, size: 'm' })] },
    (p, o) => (o.agentType === 'code-review-orchestrator' ? null : { reviewed_range: 'x', findings: [] }))
  check('review: a dead checklist reviewer is flagged, not blocking',
    r.result.results[0].reviewers_ok === true && r.result.results[0].checklist_skipped === true, r.result)

  r = await run('todo-review', { round: 1, prs: [pr()] }, () => null)
  check('review: a dead bug reviewer marks the review incomplete', r.result.results[0].reviewers_ok === false, r.result)
  check('review: an incomplete review never repairs', byType(r.calls, 'todo-worker').length === 0)

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
