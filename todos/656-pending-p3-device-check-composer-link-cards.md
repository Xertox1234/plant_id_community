---
status: pending
priority: p3
issue_id: "656"
tags: [forum, mobile, link-preview, device-check]
dependencies: ["654", "655"]
---

# Device check: composer link preview and split link cards

## Problem

Todos 654 (mobile composer preview) and 655 (link lines split out into card
paragraphs) shipped with unit, widget and backend tests, but nobody has seen
them on a phone. A simulator run was not possible locally: the app's Firebase
→ Django token exchange needs `GOOGLE_APPLICATION_CREDENTIALS` in
`backend/.env`, which the dev setup doesn't have. So the device criterion
was moved here, to be checked on the next TestFlight build.

## Findings

- Moved out of todo 654's acceptance criteria (owner decision 2026-10-17:
  "Move it to a todo").
- The code is on main once the 654/655 PR merges; it reaches a phone only
  with the next TestFlight build (`run_archive.sh` / `run_upload.sh`, owner
  runs the upload).

## Recommended Action

1. After the next TestFlight build containing 654/655 is installed:
   - paste a Wikipedia link alone into the app composer and check the card
     appears before posting;
   - write a post with text, then two links each on their own line, then
     text; check the composer shows one card plus "+1 more", and that after
     posting both platforms show two cards between the text paragraphs;
   - edit that post in the app: it must open fully editable (no warning), and
     saving it unchanged must keep both cards.
2. Record the date and what you saw below, then archive.

## Technical Details

- Production: `spam_max_links` in the CMS Forum settings must be 5 or more
  (or unset), or the 4–5 link case is refused as spam (todo 655's owner
  note).

## Acceptance Criteria

- [ ] On a device: pasting a Wikipedia link in the app composer shows the
      card before posting. (Moved from todo 654.)
- [ ] On a device: a post with text and two link lines shows one composer
      card plus "+1 more", and readers on both platforms see two cards.
- [ ] On a device: editing that post opens fully editable, and an unchanged
      save keeps both cards.

## Work Log

### 2026-10-17 - Filed from todo 654's device criterion

- The owner moved todo 654's "on a device" criterion here, rather than hold
  the 654/655 PR for a simulator setup the local backend can't support yet.
