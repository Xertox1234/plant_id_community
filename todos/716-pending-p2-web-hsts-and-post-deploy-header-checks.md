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

### 2026-11-23 - Live checks with the owner at the console

- **Before:** at about 20:40Z both hosts still answered
  `strict-transport-security: max-age=0; includeSubDomains`.
- **Owner's change:** in the Cloudflare zone (SSL/TLS, Edge Certificates, HSTS): enabled, max-age
  12 months, include subdomains on, preload off, no-sniff on. Set in Cloudflare, not turned off:
  `web/public/_headers` sends no HSTS, so turning the zone setting off would have left the web
  host with none.
- **Criterion 1, observed 2026-11-23T21:05:50Z (`curl -sI`):**
  - `https://houseplant-md.com`: `strict-transport-security: max-age=31536000; includeSubDomains`
  - `https://api.houseplant-md.com`: `strict-transport-security: max-age=31536000; includeSubDomains`
- **Criterion 2, observed the same minute:** `curl -sI https://houseplant-md.com/settings` shows
  `content-security-policy-report-only: default-src 'self'; …` and
  `referrer-policy: strict-origin-when-cross-origin`. The CMS blog preview still renders: page 18
  ("Variegation isn't magic, it's mutation") opened in the live `/cms/` in Chrome, and its preview
  panel showed the post's title, image and body.
- **Criterion 3, NOT met:** the owner threw a test error on `https://houseplant-md.com/?probe=716`
  and no event arrived. Cause: web Sentry was never configured in production. The Sentry
  organisation had no web project, and the deployed bundle holds no DSN (main, vendor and Sentry
  chunks searched; only the `VITE_SENTRY_DSN not configured` branch is present). The owner created
  the Sentry project `houseplant-md-web` and added `VITE_SENTRY_DSN` to the Worker's build
  variables; the check is repeated after the next production build.
- **Finding, for whoever promotes the CSP to enforcing:** the report-only policy flags
  Cloudflare's injected analytics beacon, `https://static.cloudflareinsights.com/beacon.min.js`
  (`script-src 'self' 'unsafe-inline'` does not allow it). Nothing is blocked while the policy is
  report-only; enforced as written, Cloudflare Web Analytics would stop loading. Allow that host,
  or turn the beacon off, first.
- The boxes above are not ticked here: they are ticked by the todo engine on the owner's
  confirmation.
