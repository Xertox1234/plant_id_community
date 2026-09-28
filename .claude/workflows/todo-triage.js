export const meta = {
  name: 'todo-triage',
  description: 'Todo sweep Stage A: classify each selected todo read-only and return one triage record per todo',
  whenToUse: 'Called by the completing-todos engine with args {todos: [{id, path}]} from `state.py triage-args`',
  phases: [{ title: 'Triage', detail: 'one todo-triager per todo' }],
}

const TRIAGE = {
  type: 'object',
  properties: {
    id: { type: 'string' },
    class: {
      type: 'string',
      enum: ['ready', 'blocked-owner', 'blocked-prod', 'blocked-device', 'blocked-external',
        'needs-design', 'needs-research', 'already-done', 'stale'],
    },
    evidence: { type: 'string', maxLength: 400 },
    blocked_on: { type: 'string', maxLength: 200 },
    owner_question: { type: 'string', maxLength: 300 },
    predicted_files: { type: 'array', items: { type: 'string' }, maxItems: 30 },
    size: { type: 'string', enum: ['xs', 's', 'm', 'l'] },
    needs_e2e: { type: 'boolean' },
    notes_for_siblings: { type: 'string', maxLength: 200 },
  },
  required: ['id', 'class', 'evidence', 'blocked_on', 'owner_question', 'predicted_files', 'size',
    'needs_e2e', 'notes_for_siblings'],
}

const todos = (args && args.todos) || []
// A fresh origin/main checkout: the main checkout can sit on another branch or behind (todo 468)
const rootLine = args && args.root ? `root: ${args.root}\n` : ''
phase('Triage')
const results = await pipeline(todos, t =>
  agent(`Triage todo ${t.id}.\nid: ${t.id}\npath: ${t.path}\n${rootLine}Return the TRIAGE record.`,
    { label: `triage:${t.id}`, phase: 'Triage', agentType: 'todo-triager', schema: TRIAGE }))
const records = results.map((r, i) => (r ? { ...r, id: todos[i].id } : null))
const missing = todos.filter((t, i) => !records[i]).map(t => t.id)
if (missing.length) log(`No triage record for ${missing.join(', ')}; they stay at scanned`)
return { records: records.filter(Boolean), missing }
