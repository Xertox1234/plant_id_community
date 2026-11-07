# Data inventory

<!-- version: 2026-11-06 -->

This is the source of truth the Privacy Policy is written from
(`web/src/content/legal/privacy.{en,fr,es}.md`). When the code changes what it
collects, where it sends it or how long it keeps it, update this file first,
then the three policy texts. Taken on 2026-11-06.

## What is collected

- **Account.** Email, username, first and last name, bio, free-text location,
  website, avatar (public storage, EXIF removed), Firebase UID, Google or
  GitHub sign-in, and the policy version accepted (with the time of
  acceptance, recorded by the server at sign-up).
- **Scans.** Photos are stored privately and re-encoded without EXIF.
  Undecided scans are deleted after 24 h; kept ones stay until removed or the
  account is deleted. Results go to Plant.id/Kindwise and PlantNet.
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
- **Garden data** (beds, plants, care tasks, harvests), and Firestore saved
  plants (`users/{uid}/identified_plants`).
- **Forum.** Posts, topics, private messages, reports, blocks and mutes.
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
    hardiness zone, profile visibility, show-email, trust level, active/staff
    flags, groups/permissions, following (never the password), plus plant
    collections and activity entries (`backend/apps/users/auditlog.py`);
  - plant identification requests and results, disease results, saved plants
    and care instructions (`backend/apps/plant_identification/auditlog.py`);
  - garden data (`backend/apps/garden_calendar/auditlog.py`).
- **Crash reports** (Sentry). Purpose: finding and fixing errors. On the web,
  about 10% of sessions and every session with an error are recorded, with
  text masked.

## Processors

| Processor | What it receives |
|-----------|------------------|
| Plant.id/Kindwise and PlantNet | Photos |
| Google Firebase | Login, saved plants, push |
| Apple | Push |
| OpenAI | Forum text, only while an optional forum AI feature is switched on |
| Sentry | Crash reports. On the web, about 10% of sessions and every session with an error are recorded, with text masked |
| Cloudflare | Website and file storage |
| Railway | Servers in the US |
| Resend | Email |
| YouTube/Vimeo | Embeds a user posts |
| Apple and Google | In-app purchase status from store receipts (in-app purchase is being built before launch) |

## Not done

No ads, no analytics or tracking SDKs, and no sale of data.

## Storage location

In the United States. This is the cross-border transfer disclosure.

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
    under 13, are blocked from signing up again by this hash. For a
    self-deleted account the hash is only the record that the account was
    deleted; it does not block sign-up;
  - the hashed "don't email this address" marker;
  - moderation records;
  - posts under an open abuse report, until the report is closed;
  - quoted text and mentions in other people's posts;
  - the other person's copy of private messages, shown as from "[deleted]".
