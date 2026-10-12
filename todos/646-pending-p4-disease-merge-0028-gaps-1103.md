---
status: pending
priority: p4
issue_id: "646"
tags: [plant-id, migrations, follow-ups]
dependencies: []
triage: ready
triaged: 2026-10-12
owner_decision: "Findings 1-4 declined in the Work Log: prod already applied 0028, the deleted rows are unrecoverable, and editing an applied migration again only reaches fresh DBs. Fix findings 5-7 (service/test) (2026-10-12)"
---

# Follow-ups from PR #1103 (todo 636, disease merge migration)

## Problem

Todo-sweep run 2026-10-12-1724 merged PR #1103 (todo 636, disease merge migration). The non-blocking review findings are
below. The curator merged duplicates and checked each item against main, and the refuter tried to refute what was
left; the items that survived are listed. Owner decision 2026-10-11: these follow-ups are the end state of the
one extra pass, so this todo is filed, not swept.

## Findings

PR #1103 (todo sweep run 2026-10-12-1724, group g9, todos 636); follow-ups: verified.

1. **medium** `backend/apps/plant_identification/migrations/0028_merge_case_variant_diseases.py:1` 0028 was merged to main today (#1081, 10:43) and is edited in place. Any DB that already applied it (prod auto-deploys main, dev DBs) never re-runs it, so the field and care-text merge only reaches fresh DBs. Prod data merged by the old 0028 stays lossy. | also: 0028 is already on main (#1081, merged 2026-10-12, 18 commits ago) and has probably been applied wherever main auto-deploys. Editing it does nothing on those databases: the lossy merge has already run, and the deleted variant rows cannot be recovered.
2. **low** `backend/apps/plant_identification/migrations/0028_merge_case_variant_diseases.py:57` expert_reviewed/community_confirmed become any() of the group, but the keeper's non-blank description/tips still win. A reviewed extra's content is discarded while its flag now certifies the keeper's unreviewed text. | also: OR-ing expert_reviewed/community_confirmed across variants marks the keeper reviewed even though its own description and fields (which win over the extras') were never reviewed. No API exposes the disease flags today, so the impact is contained.
3. **low** `backend/apps/plant_identification/migrations/0028_merge_case_variant_diseases.py:134` For a same-name duplicate care instruction, only the text is appended. Its community/positive/negative votes, materials_needed, application_timing and effectiveness/success scores are deleted with the row, so finding 5 is only partly fixed. | also: For a dropped same-name care instruction, only its `instructions` text is appended. Its other fields, such as application_timing, are deleted with the row, so part of the advice the change sets out to preserve is still lost.
4. **low** `backend/apps/plant_identification/migrations/0028_merge_case_variant_diseases.py:71` When the keeper's symptoms is not a dict (legacy list or string JSON), it is replaced with {} plus the extras' keys and its data is lost. An 'identified' value that is a string gets iterated character by character. | also: _merged_fields always writes `symptoms`. If the keeper's symptoms is not a dict (e.g. a legacy list), it starts from {} and the update overwrites the keeper's value, losing it. A non-list 'identified' (e.g. a string) is also split into characters by list(). | When keeper.symptoms is not a dict (for example a legacy JSON list), the merge replaces it with {} plus the extras' keys, so the keeper's own symptom data is overwritten. Before this change the keeper's symptoms were never touched. | _merged_fields always writes `symptoms`; a keeper whose symptoms JSON is not a dict (e.g. a legacy or admin-entered list) is replaced by {} or the extras' dict, so its own data is lost. The migration is irreversible and on main this column was never touched.
5. **low** `backend/apps/plant_identification/services/disease_diagnosis_service.py:156` On Postgres, an IntegrityError whose diag.constraint_name is None (e.g. NOT NULL) falls back to a substring match on str(exc), whose 'Failing row contains (...)' echoes API values; a crafted name could be misread as a collision. Effect: one extra create, then re-raise. | also: The message fallback also runs when psycopg diag exists but constraint_name is None (for example NOT NULL errors, whose DETAIL echoes row values). A disease name containing the constraint name would then be misread as a collision. The effect is bounded: the retry create raises the same error again. | The message fallback also runs when psycopg diag exists but constraint_name is None (e.g. NOT NULL). That DETAIL echoes row values, including the API-supplied disease name, so a substring match could misclassify the error. The only harm is one extra create attempt before it surfaces.
6. **low** `backend/apps/plant_identification/tests/test_disease_diagnosis_count.py:546` test_second_collision_surfaces passes on the pre-change code too: the old path re-raised on the first collision and also returned None. It never checks that a retry happened, so it does not pin the new 'second collision surfaces' contract. | also: test_second_collision_surfaces mocks every create to raise and asserts only that the result is None and not stored. It does not check that the fallback retried exactly once, so a second-collision retry loop would still pass. | test_second_collision_surfaces does not check that a retry happened. If the code re-raised on the first collision with no retry, it would still pass: None is returned and nothing is stored. It does not pin the 'create once more, then surface' contract.
7. **low** `todos/archive/636-completed-p4-disease-merge-fields-1081.md:55` The verification evidence is a test run under environment drift (pyjwt and urllib3 differ from requirements.txt), and the evidence file is not committed. CI is the real check.

5 more location(s) were dropped by the cap of 10 (the most severe are kept).

## Acceptance Criteria

- [ ] Each finding above is fixed with a test where it is a behaviour change, or recorded in the Work Log as
      declined with a reason (or as already fixed on main, with the evidence).

## Work Log

### 2026-10-12 - Filed from the PR #1103 review (todo sweep run 2026-10-12-1724)

Filed by the closing step of the run from `state.py followups-md g9`.
