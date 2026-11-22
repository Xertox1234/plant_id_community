---
status: pending
priority: p2
issue_id: "716"
tags: [web, security, headers, cloudflare, prod-check, owner]
dependencies: ["706"]
triage: blocked-prod
triaged: 2026-11-22
blocked_on: "Owner turns off the Cloudflare zone HSTS, then the live curl, CMS-preview and Sentry checks run on production."
owner_decision: "Cloudflare zone HSTS not yet turned off (owner 2026-11-22)"
---

# Web: Cloudflare HSTS and the post-deploy header checks

## Problem

Split out of todo 706 on 2026-11-17. Todo 706 ships the code (report-only CSP
and `Referrer-Policy` in `web/public/_headers`, the token `replaceState`, the
OAuth origin check). What is left is a Cloudflare console change and checks
that can only run on the live site.

## Findings

Source: `docs/audits/2026-11-10-auth-legal.md`; detail in todo 706.

- **M1** `houseplant-md.com` and `api.houseplant-md.com` both answer
  `strict-transport-security: max-age=0; includeSubDomains` (`curl -sI`,
  2026-11-10), although Django sets one year (`settings.py:1528`).
  Hypothesis, not verified: the Cloudflare zone's HSTS setting overrides the
  origin.

## Recommended Action

1. Owner: in the Cloudflare zone, set HSTS max-age to at least six months, or
   turn the zone setting off so the origin's header passes.
2. After 706 deploys, run the checks below. Once the report-only CSP shows no
   breakage, a later change can enforce it.

## Acceptance Criteria

- [ ] `curl -sI https://houseplant-md.com` and the API host show an HSTS
      max-age of at least 15552000 — record the date and both header lines.
- [ ] `curl -sI https://houseplant-md.com/settings` shows the CSP and
      `Referrer-Policy`, and the CMS blog preview still renders — record the
      date and result.
- [ ] A Sentry event from production carries no query string — record the
      date and event id.

## Work Log

### 2026-11-17 - Split out of todo 706

- Owner decision: 706 ships the code slice; the console change and the live
  checks stay here.
