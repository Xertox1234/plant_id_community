---
status: completed
priority: p3
issue_id: "406"
tags: [blog, wagtail, ops, verification]
dependencies: []
source_review: "docs/audits/2026-09-23-web-dead-code.md"
source_finding: "M2"
---

# Verify the Wagtail blog Preview end to end in production

## Problem

The web dead-code audit (M2) rebuilt the headless blog preview:

- the settings moved to the 0.9 name `WAGTAIL_HEADLESS_PREVIEW`, with
  `REDIRECT_ON_PREVIEW`;
- `frame-src` now allows the preview origin;
- the backend serves drafts at `GET /api/v2/page_preview/`;
- the web `/blog/preview?content_type=…&token=…` page renders them.

Tests cover each piece, but three production facts cannot be checked from a
test run.

## Findings

- **`HEADLESS_PREVIEW_CLIENT_URL` must be set on Railway** to the web app's
  public preview root (`https://<web host>/blog/preview`). The default is
  `http://localhost:5174/blog/preview`. Unset in production, editors are sent to
  localhost. Whether it is set is not verified.
- **The editor's side-by-side preview panel frames the web app.** The backend
  CSP now includes `frame-src 'self' <preview origin>`. The web app must also
  not refuse to be framed by the CMS origin: no `X-Frame-Options`, and no
  `frame-ancestors` that excludes it. No such header was found in
  `wrangler.jsonc` or `web/public`. The live Cloudflare response is not
  verified.
- **Cross-origin fetch:** the web app calls `api.<host>/api/v2/page_preview/`,
  so the CORS allowlist must include the web origin. It already does for the
  other v2 calls; this is noted for completeness.

## Recommended Action

1. Set (or confirm) `HEADLESS_PREVIEW_CLIENT_URL` on the Railway web service.
2. In production `/cms/`, open a blog post, make an unsaved edit, and click:
   - **Preview in new tab**, which should land on `/blog/preview?…` and show
     the draft;
   - the **side panel preview**, which should render inside the editor.
3. Record the date and what was seen for each, per completing-todos Safety
   Rail 5.

## Technical Details

- `backend/plant_community_backend/settings.py` (`HEADLESS_PREVIEW_CLIENT_URL`,
  `WAGTAIL_HEADLESS_PREVIEW`, CSP `frame-src`)
- `backend/apps/blog/api/viewsets.py` (`BlogPostPreviewAPIViewSet`)
- `web/src/pages/BlogPreview.tsx`

## Acceptance Criteria

- [x] `HEADLESS_PREVIEW_CLIENT_URL` is confirmed on Railway (the variable name
      and host only; never paste a secret).
- [x] "Preview in new tab" shows an unsaved draft in production. Record the
      date and what was observed.
- [x] The editor's preview panel renders the draft in production, or a
      follow-up is filed with the blocking header quoted.

## Work Log

### 2026-09-23 - Filed from the web dead-code audit (M2)

The code shipped in the audit PR; these are the production checks it could not
make.

### 2026-09-24 - HEADLESS_PREVIEW_CLIENT_URL set on Railway

Set `HEADLESS_PREVIEW_CLIENT_URL=https://houseplant-md.com/blog/preview` on the
`plant_id_community` service on 2026-09-24 (Railway MCP, owner approved; the web
origin was confirmed by `GET https://houseplant-md.com/blog/preview` → 200).
Remaining (owner, in production `/cms/`): AC 2 "Preview in new tab" and AC 3
the side-panel preview, each recorded here with the date.

### 2026-09-24 - Verified in production, in a browser (all criteria)

- **AC 1:** `HEADLESS_PREVIEW_CLIENT_URL` host is `houseplant-md.com`
  (`/blog/preview`), set on `plant_id_community` and declared in
  `.railway/railway.ts` (#828).
- **HTTP level first:** the preview API returned an unsaved title change with
  `cache-control: ... no-store ...`; `GET https://houseplant-md.com/blog/preview`
  → 200; the CMS CSP carries `frame-src 'self' https://houseplant-md.com`; the web
  sends no `X-Frame-Options`.
- **AC 3, preview panel:** in production `/cms/pages/17/edit/` the title was
  changed to "Killed by kindness [browser preview check]" WITHOUT saving; the side
  panel rendered the web app with that title under the banner "Preview: this
  draft is not published."
- **AC 2, new tab:** "Preview in new tab" opened
  `https://houseplant-md.com/blog/preview?content_type=blog.blogpostpage&token=…`,
  titled "Preview: Killed by kindness [browser preview check] — Houseplant MD".
- The live post still reads "Killed by kindness" (`/api/v2/blog-posts/`). The
  editor showed a "Saved" indicator after the edit; if Wagtail autosaved a draft
  revision carrying the test title, discard it from the page's History.
