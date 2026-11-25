# Breach register

Started on 2026-11-17 (auth + legal audit, row H4; todo 702).

One row for every breach of security safeguards involving personal
information that Houseplant MD holds, **including every one judged not
notifiable**. The procedure is `docs/operations/breach-runbook.md`; open the
row in its first step, on the day the breach is found.

Rules for this file:

- Keep each row for at least **24 months** after the day we determined the
  breach happened (PIPEDA s. 10.3; Breach of Security Safeguards Regulations
  s. 6). Do not delete a row before then. Older rows may stay.
- The row must hold enough for the OPC to check whether notices were
  required and were sent; it is handed over if the OPC asks.
- This file is in a **public repository**. Write no names, email addresses,
  usernames or other details that identify a person. Where a list of the
  people affected is needed, keep it outside the repository and say in
  "Notes" where it is.
- Commit a row only after the breach is contained and its fix has merged.
  Until then the live record stays private: a row naming the cause would
  publish an unfixed hole.
- Change a row by adding to it (a dated line in "Notes"), never by rewriting
  what an earlier entry said.

## Columns

- **No.**: `B-YYYY-NN`, numbered in order within the year.
- **Found**: the date we knew, or reasonably believed, a breach happened.
  The deadlines run from here.
- **Period**: when the breach happened, or the best estimate.
- **What happened**: the cause and how it was found, in a sentence or two.
- **Information**: the kinds of personal information involved.
- **People**: how many, or an estimate; and where they are (Alberta, rest of
  Canada, California, Mexico, elsewhere).
- **Assessment**: real risk of significant harm, yes or no, and why
  (sensitivity, likelihood of misuse; runbook section 1).
- **Notices sent**: each one with its date: OIPC, OPC, people affected (and
  how), California Attorney General, others told under PIPEDA s. 10.2. Write
  "none" when the assessment is no.
- **Notes**: containment, the fix (pull request), dated updates.

## Register

| No. | Found | Period | What happened | Information | People | Assessment | Notices sent | Notes |
|-----|-------|--------|---------------|-------------|--------|------------|--------------|-------|

No breach has been recorded as of 2026-11-17.
