# Handoff: add a capture step to the `/codify` skill

`.claude/skills/codify/SKILL.md` is blocked by the self-mod classifier, so this
change is applied by hand. Two edits — insert a new **Step 5b**, and amend the
**Step 6** `git add` line.

This is the manual half of the JIT-injection capture loop ("Both"): when codify
writes a rule/learning that has a textual signature, it also registers a
write-time trigger so the mistake is caught in the editor next time, not only in
review.

---

## 1. Insert this as a new step, after "Step 5 — Write the codification" and before "Step 6 — Commit"

```markdown
## Step 5b — Emit a write-time trigger (only if the finding has a textual signature)

For any rule/learning you just codified that has a **clear, regex-matchable
signature** — a specific decorator, import, function call, or code shape that
appears in the code being written — also register a just-in-time trigger so it
fires at write-time, not only in review:

\```bash
python3 scripts/inject/capture_trigger.py \
  --id <kebab-id> \
  --domains <d1,d2> \
  --path-glob '<repo-relative fnmatch glob>' \
  --content-present '<regex matched against the NEW edit fragment>' \
  --content-absent '<regex on the RESULTING file that suppresses when the fix is present>' \
  --message '<one-line warning + the fix>' \
  --pattern-ref <path/to/pattern-doc.md> \
  --source "codify: $(git branch --show-current)" \
  --severity warn
\```

Rules:
- Use `--severity warn` here (human-curated). Leave `candidate` for review automation.
- Do this ONLY when a real signature exists. A signature-less lesson stays prose —
  forcing it into a trigger manufactures false positives and erodes trust in the
  whole system (per the spec's seeding rule).
- `--content-present` matches the new fragment ("are you introducing X?");
  `--content-absent` matches the resulting file ("...and is the fix missing?").
  Omit `--content-absent` if there is no clean "already-fixed" marker.
- `--pattern-ref` must resolve to a real file; capture_trigger drops it with a
  warning if it doesn't (no dangling pointers).
- After capturing, run `python3 scripts/inject/test_match_triggers.py` to confirm
  the index still validates. For a high-traffic trigger, add a positive AND a
  negative fixture to `scripts/inject/test_match_triggers.py` before committing.
```

---

## 2. Amend "Step 6 — Commit"

Add `docs/rules/triggers.json` to the staged files whenever Step 5b captured a
trigger:

```bash
git add docs/rules/<domain>.md docs/LEARNINGS.md docs/rules/triggers.json .claude/agents/<agent>.md
```

---

## Notes

- The automatic half of "Both" (review automation calling `capture_trigger.py`
  with `--severity candidate`) is the fast-follow — the script already supports it
  via the default severity; only the wiring into the review path remains.
- `capture_trigger.py` is dedup-safe on `id` (idempotent) and rejects invalid
  regex / missing required fields, so a bad codify invocation fails loudly rather
  than corrupting the index.
