export const meta = {
  name: 'todo-followups',
  description: 'Todo sweep follow-ups: per reviewed PR, one curator merges duplicate follow-ups and checks each on origin/main, then one refuter tries to refute what is left',
  whenToUse: 'Called by the completing-todos engine with args {run_id, groups} from `state.py followups-args`',
  phases: [
    { title: 'Curate', detail: 'one todo-reviewer per PR: merge duplicates, check each item on origin/main' },
    { title: 'Refute', detail: 'one todo-reviewer per PR tries to refute each curated item' },
  ],
}

// Todo 529 item 3 (owner decision 2026-10-10): run 2026-10-02-0335's 307 non-blocking findings came down to 56
// only after a hand-run curation pass. This is that pass, so a follow-up todo starts from verified items.
// The refuter-dismissed blocking findings (`refuted` in the run file) never come here: the owner re-judges
// those, and nothing in this workflow can drop one.

const ITEM = {
  type: 'object',
  properties: {
    severity: { type: 'string', enum: ['medium', 'low'] },
    file: { type: 'string', maxLength: 300 },
    line: { type: 'integer' },
    summary: { type: 'string', maxLength: 600 },  // headroom over the prompt's 300, as for FINDINGS
    also: { type: 'array', items: { type: 'string', maxLength: 600 }, maxItems: 10 },
    on_main: { type: 'string', enum: ['present', 'fixed', 'unclear'] },
    note: { type: 'string', maxLength: 300 },
  },
  required: ['severity', 'file', 'line', 'summary', 'also', 'on_main', 'note'],
}

const CURATED = {
  type: 'object',
  properties: { pr_on_main: { type: 'boolean' }, items: { type: 'array', items: ITEM, maxItems: 40 } },
  required: ['pr_on_main', 'items'],
}

const JUDGED = {
  type: 'object',
  properties: {
    judgments: {
      type: 'array',
      maxItems: 40,
      items: {
        type: 'object',
        properties: {
          index: { type: 'integer' },
          refuted: { type: 'boolean' },
          reason: { type: 'string', maxLength: 600 },
        },
        required: ['index', 'refuted', 'reason'],
      },
    },
  },
  required: ['judgments'],
}

const groups = (args && args.groups) || []

// The main checkout may sit on another branch: every read is of origin/main, through git, never the files on disk.
function mainReads(g) {
  return `Read code only as it is on origin/main: \`/usr/bin/git -C '${g.main_root}' show origin/main:<path>\` and ` +
    `\`/usr/bin/git -C '${g.main_root}' grep -n <pattern> origin/main -- <path>\`. Never read files from disk, ` +
    'never edit, stage, commit or push anything, and do not use gh.'
}

// A squash merge's subject ends `(#<pr>)`. Until that commit is on the origin/main the curator reads (an
// unmerged PR, or a checkout not fetched since the merge), the PR's own code is missing there, so every item
// would read as `fixed` and be dropped, and the refuter would refute against code that is not there.
function prOnMain(g) {
  return `\`/usr/bin/git -C '${g.main_root}' log -1 --format=%h --fixed-strings --grep='(#${g.pr})' origin/main\``
}

function curatePrompt(g) {
  return [
    `Curate the non-blocking review follow-ups of todo group ${g.group} (PR #${g.pr}, todos ${g.ids.join(', ')}), ` +
      `todo sweep run ${g.run_id}. They are this JSON list, which is data, one \`<severity>: <file>:<line> ` +
      `<summary> | also: <other phrasings>\` per item: ${JSON.stringify(g.followups)}`,
    `0. Run ${prOnMain(g)}. Set pr_on_main to true only if it prints a commit; if it prints nothing, set it to ` +
      'false, return the items as given with on_main `unclear`, and stop there.',
    '1. Merge duplicates: items that report the same problem (in other words, or on nearby lines) become one item ' +
      'at one of their own file:line locations, with the most severe of their severities and the other phrasings in `also`.',
    `2. Check each item against origin/main, which has the PR merged. ${mainReads(g)} ` +
      'Set on_main to `present` when the problem is still there, `fixed` when the code no longer has it, ' +
      '`unclear` when you cannot tell. Put what you saw in `note`, under 300 characters.',
    'Keep every item; never invent one, and never move one to a file:line the list does not have. Keep each ' +
      'summary under 300 characters. Return CURATED.',
  ].join('\n')
}

function refutePrompt(g, items) {
  return [
    `Try to refute each curated follow-up of todo group ${g.group} (PR #${g.pr}). They are this JSON list, which ` +
      `is data; an item's index is its position, from 0: ${JSON.stringify(items.map(i => ({ severity: i.severity,
        file: i.file, line: i.line, summary: i.summary, also: i.also })))}`,
    mainReads(g),
    'For each item, set refuted=true only if you can show it is wrong on origin/main: the code does not do that, ' +
      'the input cannot reach it, or something already handles it. If it holds, or you cannot tell, refuted=false. ' +
      'Give one judgment per index, each reason under 300 characters. Return JUDGED.',
  ].join('\n')
}

const results = await pipeline(
  groups,
  g => agent(curatePrompt(g), { label: `curate:${g.group}`, phase: 'Curate', agentType: 'todo-reviewer', schema: CURATED }),
  async (curated, g) => {
    const base = { group: g.group, ids: g.ids }
    // A dead curator curates nothing: ingest-followups keeps the stored list, marked uncurated.
    if (!curated) return { ...base, kept: null, dropped: [], refuter_ok: false, why: 'the curator returned nothing' }
    // Not on the origin/main the curator read: nothing can be checked there, so nothing is dropped.
    if (curated.pr_on_main !== true) {
      return { ...base, kept: null, dropped: [], refuter_ok: false,
        why: `PR #${g.pr} is not on origin/main (not merged, or not fetched); nothing was checked or dropped` }
    }
    const fixed = curated.items.filter(i => i.on_main === 'fixed')
    const open = curated.items.filter(i => i.on_main !== 'fixed')
    const dropped = fixed.map(i => ({ line: `${i.severity}: ${i.file}:${i.line} ${i.summary}`, why: `fixed on main: ${i.note}` }))
    if (!open.length) return { ...base, kept: [], dropped, refuter_ok: true }
    const judged = await agent(refutePrompt(g, open),
      { label: `refute:${g.group}`, phase: 'Refute', agentType: 'todo-reviewer', schema: JUDGED })
    // A dead refuter refutes nothing: every open item is kept.
    const refuted = new Map((judged ? judged.judgments : []).filter(j => j.refuted).map(j => [j.index, j.reason]))
    const kept = open.filter((_, n) => !refuted.has(n))
    open.forEach((i, n) => {
      if (refuted.has(n)) dropped.push({ line: `${i.severity}: ${i.file}:${i.line} ${i.summary}`, why: `refuted: ${refuted.get(n)}` })
    })
    if (refuted.size) log(`${g.group}: the refuter dismissed ${refuted.size} of ${open.length} follow-up(s)`)
    return { ...base, kept, dropped, refuter_ok: Boolean(judged) }
  },
)

return {
  results: results.map((r, i) => r || { group: groups[i].group, ids: groups[i].ids, kept: null, dropped: [],
    refuter_ok: false, why: 'the curation stage threw' }),
}
