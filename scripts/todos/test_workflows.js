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

async function run(name, args, respond) {
  const body = source(name).replace(/^export const meta/m, 'const meta')
  const calls = []
  const errors = []
  const agent = async (prompt, opts = {}) => {
    calls.push({ prompt, opts })
    return respond(prompt, opts, calls)
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
  const result = await fn(agent, pipeline, parallel, () => {}, () => {}, args, { total: null }, async () => null)
  return { result, calls, errors }
}

const worker = (over = {}) => ({ ids: ['1'], status: 'staged', worktree: '/wt/g1', branch: 'b', tree_id: 'T',
  files_changed: [], ac_file: '.sweep-evidence/g1/ac.json', tests_run: [], blockers: '', discoveries: '', summary: '', ...over })
const verdict = v => ({ ids: ['1'], verdict: v, ac: [{ todo: '1', index: 0, verified: v === 'pass', note: 'n' }],
  test_edits_flagged: [], commands_rerun: 1, tree_id_before: 'T', tree_id_after: 'T', clean_after: true })
const brief = (over = {}) => ({ run_id: 'r', group: 'g1', ids: ['1'], todo_paths: ['todos/1-pending-p3-x.md'],
  owner_decisions: {}, plan_needed: false, verify_only: false, in_scope_files: [], lanes_held: [], lanes_forbidden: [],
  slot: 1, evidence_dir: '.sweep-evidence/g1', main_root: '/main', ...over })
const pr = (over = {}) => ({ run_id: 'r', round: 1, group: 'g1', ids: ['1'], worktree: '/wt/g1', branch: 'b', pr: 861,
  size: 's', slot: 1, evidence_dir: '.sweep-evidence/g1', main_root: '/main', test_edits: [], ...over })
const byType = (calls, type) => calls.filter(c => c.opts.agentType === type)

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
    (p, o) => (p.includes('id: 2') ? null : { id: 'WRONG', class: 'ready' }))
  check('triage: one todo-triager per todo', byType(r.calls, 'todo-triager').length === 2)
  check('triage: record ids are forced to the input id', r.result.records[0].id === '1', r.result)
  check('triage: a dead agent is reported missing', r.result.missing.join() === '2', r.result)
  check('triage: no script errors', r.errors.length === 0, r.errors)

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

  // --- review round 2, size m, blocking finding
  r = await run('todo-review', { round: 2, prs: [pr({ round: 2, size: 'm' })] }, () => high)
  check('review: size m adds the checklist reviewer', byType(r.calls, 'code-review-orchestrator').length === 1)
  check('review: round 2 never repairs', byType(r.calls, 'todo-worker').length === 0)
  check('review: blocking findings are reported', r.result.results[0].blocking.length === 2, r.result)

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
