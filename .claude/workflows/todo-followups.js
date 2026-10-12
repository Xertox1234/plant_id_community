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
    also: { type: 'array', items: { type: 'string', maxLength: 600 }, maxItems: 50 },
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
          // Todo 551 (owner decision 2026-10-10): each merged phrasing is judged on its own; these are the
          // positions in the item's `also` that are refuted. `refuted` judges the summary alone.
          also_refuted: { type: 'array', items: { type: 'integer' }, maxItems: 50 },
          reason: { type: 'string', maxLength: 600 },
        },
        required: ['index', 'refuted', 'also_refuted', 'reason'],
      },
    },
  },
  required: ['judgments'],
}

const groups = (args && args.groups) || []

// Todo 577 #4: where each stored phrasing came from. A stored line is `<severity>: <file>:<line> <summary>` with
// any merged phrasings after ` | also: `, joined by ` | ` (state.py FOLLOWUP_LINE). A phrasing found at its own
// line's head wins over one found in another line's `also`, and the first such line wins over later ones.
const STORED = /^(critical|high|medium|low): (.+?):(\d+) ([\s\S]*)$/
function origins(followups) {
  const heads = new Map()
  const merged = new Map()
  for (const line of followups || []) {
    const m = STORED.exec(line)
    if (!m) continue
    const [head, ...also] = m[4].split(' | also: ').flatMap((part, n) => (n ? part.split(' | ') : [part]))
    const at = { severity: m[1], file: m[2], line: Number(m[3]) }
    if (!heads.has(head)) heads.set(head, at)
    for (const p of also) if (!merged.has(p)) merged.set(p, at)
  }
  return phrasing => heads.get(phrasing) || merged.get(phrasing) || null
}

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
      'at one of their own file:line locations, with the most severe of their severities and the other phrasings in `also`. ' +
      // Todo 596 #2: ingest-followups counts phrasings, one stored item each, so two identical items merged and
      // listed once would leave the second uncovered, and it would be filed again as a duplicate.
      'Put every merged item\'s phrasing in `also` once per merged item, even when it reads the same as the summary, ' +
      'as another `also` entry, or as one already in the kept item\'s own ` | also: ` list: each listed phrasing ' +
      'accounts for exactly one item of the list above.',
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
        file: i.file, line: i.line, summary: i.summary, also: i.also, curator: i.on_main, curator_note: i.note })))}`,
    mainReads(g),
    'An item\'s `also` holds other phrasings the curator merged into it; each may be a different problem, perhaps ' +
      'at another location. Judge the summary and every `also` phrasing separately. A phrasing is refuted only if ' +
      'you can show it is wrong on origin/main: the code does not do that, the input cannot reach it, something ' +
      'already handles it, or (for an item whose `curator` is `fixed`) the code no longer has the problem. The ' +
      'curator\'s claim is not evidence: check it yourself. If it holds, or you cannot tell, it is not refuted. ' +
      'Set refuted=true when the summary is refuted, and list in also_refuted the 0-based positions in `also` of ' +
      'the phrasings you refuted ([] for none); a phrasing you do not list stays a follow-up. Give one judgment ' +
      'per index, each reason under 300 characters. Return JUDGED.',
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
    // Todo 541 (#982-3): an item the curator calls `fixed` goes to the refuter with that claim, like every other
    // item, and is dropped only when the refuter confirms it. One wrong verdict never deletes a real follow-up.
    const items = curated.items
    if (!items.length) return { ...base, kept: [], dropped: [], refuter_ok: true }
    const judged = await agent(refutePrompt(g, items),
      { label: `refute:${g.group}`, phase: 'Refute', agentType: 'todo-reviewer', schema: JUDGED })
    // A dead refuter refutes nothing: every item is kept, a `fixed` one too.
    const verdicts = new Map((judged ? judged.judgments : []).map(j => [j.index, j]))
    const kept = []
    const dropped = []
    const originOf = origins(g.followups)
    let gone = 0
    items.forEach((i, n) => {
      const j = verdicts.get(n)
      const also = i.also || []
      // Todo 551 (owner decision 2026-10-10): only the phrasings the refuter refuted drop; the rest of the item
      // stays a follow-up. Before, refuting the summary dropped every merged phrasing with it, a different problem
      // the refuter never judged among them.
      const alsoGone = new Set(((j && j.also_refuted) || []).filter(k => Number.isInteger(k) && k >= 0 && k < also.length))
      // PR #1061 review: the curator repeats an identical phrasing once per merged item (todo 596 #2), but the
      // refuter judges each position on its own. A text refuted anywhere is refuted everywhere in the item, so an
      // unlisted identical copy cannot survive in `stay` and be refiled as a kept follow-up.
      const norm = t => String(t).trim()
      const refutedText = new Set([...(j && j.refuted ? [norm(i.summary)] : []), ...[...alsoGone].map(k => norm(also[k]))])
      also.forEach((t, k) => { if (refutedText.has(norm(t))) alsoGone.add(k) })
      const summaryGone = refutedText.has(norm(i.summary))
      // Todo 614 #2: gone only through a refuted identical `also` copy is not the refuter agreeing with the
      // curator's "fixed on main": it judged the summary itself not refuted. Such a drop reads `refuted:`.
      const summaryRefuted = Boolean(j && j.refuted)
      const stay = [...(summaryGone ? [] : [i.summary]), ...also.filter((_, k) => !alsoGone.has(k))]
      if (stay.length) {
        // Todo 577 #4: with its summary refuted, the item is led by a merged phrasing, which goes back to its OWN
        // stored location and severity: a low nit merged in from a.py:2 is not a medium at a.py:9. A phrasing the
        // curator reworded, found on no stored line, keeps the item's location and severity, as before.
        const at = (summaryGone && originOf(stay[0])) || null
        const home = at && ['medium', 'low'].includes(at.severity) ? at : { severity: i.severity, file: i.file, line: i.line }
        kept.push({ ...i, ...home, summary: stay[0], also: stay.slice(1) })
      }
      const refutedAlso = also.filter((_, k) => alsoGone.has(k))
      if (!summaryGone && !refutedAlso.length) return
      gone += (summaryGone ? 1 : 0) + refutedAlso.length
      const at = `${i.severity}: ${i.file}:${i.line}`
      const refutedWhy = `refuted: ${j.reason}`
      // Todo 577 #7: "fixed on main" is the curator's claim about the item's summary. It names only the summary's
      // own drop; a merged phrasing refuted alongside it, or alone, was judged separately and reads `refuted:`.
      if (summaryRefuted && i.on_main === 'fixed') {
        dropped.push({ line: `${at} ${i.summary}`, why: `fixed on main: ${i.note}; the refuter agreed: ${j.reason}` })
        if (refutedAlso.length) {
          const more = refutedAlso.length > 1 ? ` | also: ${refutedAlso.slice(1).join(' | ')}` : ''
          dropped.push({ line: `${at} ${refutedAlso[0]}${more}`, why: refutedWhy })
        }
        return
      }
      const refuted = [...(summaryGone ? [i.summary] : []), ...refutedAlso]
      // Todo 546: with the refuted merged phrasings, so ingest-followups knows those duplicates are refuted too.
      const more = refuted.length > 1 ? ` | also: ${refuted.slice(1).join(' | ')}` : ''
      dropped.push({ line: `${at} ${refuted[0]}${more}`, why: refutedWhy })
    })
    if (gone) log(`${g.group}: the refuter dismissed ${gone} phrasing(s) in ${dropped.length} drop(s) across ${items.length} follow-up(s)`)
    return { ...base, kept, dropped, refuter_ok: Boolean(judged) }
  },
)

return {
  results: results.map((r, i) => r || { group: groups[i].group, ids: groups[i].ids, kept: null, dropped: [],
    refuter_ok: false, why: 'the curation stage threw' }),
}
