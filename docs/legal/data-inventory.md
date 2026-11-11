# Data inventory

<!-- version: 2026-11-10 -->

This is the source of truth the Privacy Policy is written from
(`web/src/content/legal/privacy.{en,fr,es}.md`). When the code changes what it
collects, where it sends it or how long it keeps it, update this file first,
then the three policy texts. Taken on 2026-11-06; brought level with policy
version 2026-11-10 on 2026-11-11.

## What is collected

- **Account.** Email, username, first and last name, bio, free-text location,
  website, avatar (public storage, EXIF removed), Firebase UID, Google or
  GitHub sign-in, and the policy version accepted (with the time of
  acceptance, recorded by the server at sign-up).
- **Scans.** Photos are stored privately and re-encoded without EXIF.
  Undecided scans are deleted after 24 h; kept ones stay until removed or the
  account is deleted. The photos go to Plant.id (FlowerChecker s.r.o., Czech
  Republic) and PlantNet (France).
- **Garden data** (beds, plants, care tasks, harvests), and Firestore saved
  plants (`users/{uid}/identified_plants`).
- **Disease-diagnosis location note.** An optional free-text `location` (max
  200 characters, e.g. "east-facing window") on a plant health check
  (`PlantDiseaseRequest.location`). Typed by the user, not device location.
  Stored with the request and visible only to its owner (the viewset filters
  by user). Not in the audit log.
- **Community events** (`CommunityEvent`, `/api/v1/calendar/events/`). An
  organizer may enter a venue name, street `address`, `latitude`/`longitude`,
  `contact_email` and `contact_phone`, all typed by the user, not device
  location. The organizer picks the visibility (`public`, `local`, `zone`,
  `friends`, `private`; default `local`). Anyone who can see an event gets the
  detail fields, address and contact details included; the code does no
  masking (the model help text says "masked", but nothing implements it), and
  a `public` event is readable by signed-out visitors.
- **Forum.** Posts, topics, private messages, reports, blocks and mutes.
  A post shows the member's forum display name or, when none is set, their
  first and last name.
- **Automated spam screen.** Posts and private messages from members who are
  new or not yet trusted can be sent to OpenAI while the screen is on
  (`WAGTAILFORUM_SPAM_BACKEND`). A refused private message is not kept.
- **Newsletter.** The subscription.
- **Push tokens.** FCM/APNs on mobile and web push.
- **Email.** Delivery and bounce records (90 days), click records (90 days),
  and a hashed suppression marker kept indefinitely. Purpose: delivering email,
  and knowing which links in our emails are used.
- **Blog page views.** IP, user agent and referrer, for 90 days. Purpose: site
  statistics and abuse prevention.
- **Rate limiting.** IP addresses held briefly in memory.
- **Audit log** (django-auditlog). 90 days. Purpose: security, and a record of
  changes to investigate problems. Records changes to:
  - account and profile: username, email, first/last name, bio, location,
    hardiness zone, trust level, active/staff
    flags, groups/permissions, following (never the password), plus plant
    collections and activity entries (`backend/apps/users/auditlog.py`);
  - plant identification requests and results, disease results, saved plants
    and care instructions (`backend/apps/plant_identification/auditlog.py`);
  - garden data (`backend/apps/garden_calendar/auditlog.py`).
- **Error reports** (Sentry), from the website and the servers; the app sends
  none. Purpose: finding and fixing errors. On the web,
  a session that hits an error is recorded, with text masked; no other
  session is.

## Processors

| Processor | What it receives |
|-----------|------------------|
| Plant.id (FlowerChecker s.r.o., Czech Republic) and PlantNet (France) | Photos |
| Google Firebase | Login, saved plants, push |
| Apple | Push |
| OpenAI | Posts and private messages from new or not-yet-trusted members, while the spam screen is on. While an optional AI feature is on: the title and opening post of public topics (search index) and the text submitted to the feature. No email address |
| Sentry | Crash reports. On the web, a session that hits an error is recorded, with text masked; no other session is |
| Cloudflare | Website and file storage |
| Railway | Servers in the US |
| Resend | Email |
| YouTube/Vimeo | Embeds a user posts |
| Apple and Google | In-app purchase status from store receipts (in-app purchase is being built before launch) |

## Not done

No ads, no analytics or tracking SDKs, and no sale of data.

## Storage location

Servers and database: United States (Railway `us-west2`; Firestore `nam5`).
Scan photos also go to Plant.id (Czech Republic) and PlantNet (France). The
other processors are United States companies; the region each account
actually uses is not sourced (todo 701). This is the cross-border transfer
disclosure, and the policy's written information about providers outside
Canada (Alberta PIPA s. 6(2), s. 13.1).

Per-processor detail and deletion routes: `docs/operations/processors.md`.

## Account deletion

From the spec (`docs/superpowers/specs/2026-11-06-legal-policies-and-account-deletion-design.md`,
decisions 9–12).

- **Erased:** account, profile and avatar; garden data; scans and their
  photos; Firestore saved plants and the Firebase login; push tokens; the
  newsletter subscription; block and mute lists; the address in the email log.
  Forum posts: the body, images and edit history go, and a "[deleted]"
  placeholder keeps each post's place. Audit-log entries are removed within
  90 days by the regular clean-up.
- **Where deletion is offered:** the app's settings, the website's settings,
  and the public `/delete-account` page.
- **Kept:**
  - a record that the account existed and was deleted, with a hashed email.
    Purpose: addresses deleted by staff for abuse, or because the user was
    under 14, are blocked from signing up again by this hash. For a
    self-deleted account the hash is only the record that the account was
    deleted; it does not block sign-up, and it is removed after 90 days
    (`PRIVACY_RETENTION_DAYS`);
  - the hashed "don't email this address" marker;
  - moderation records;
  - posts under an open abuse report, until the report is closed;
  - quoted text and mentions in other people's posts;
  - the other person's copy of private messages, shown as from "[deleted]".
- **Under the minimum age (14).** A staff deletion for this reason goes
  further: posts under a report are erased at once, the messages the person
  sent are deleted from the other side's copy, their words are removed from
  quotes made with the quote button, and the text of reports they filed is
  erased (#1296).
