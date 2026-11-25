# Processor register

Taken on 2026-11-10 (auth + legal audit, rows M20 and L15; todos 702 and 707).

Every outside service that receives personal information from Houseplant MD:
what it gets, what our account-deletion job already removes there, and how to
ask the service to delete what the job cannot reach. Update this file in the
same pull request as any change that sends personal information somewhere new.

"The job" is `request_account_deletion` and the steps it queues
(`backend/apps/users/deletion.py`). "Unsourced" means the service's own
documentation was looked for on 2026-11-10 and did not answer the question;
it is a gap to close by asking the service, not a guess.

## The register

| Processor | What it receives | What the job removes there | What stays, and for how long |
|-----------|------------------|----------------------------|------------------------------|
| Railway (servers, Postgres, Redis; United States) | Everything in the database | Every row of the account (steps `forum`, `email`, `django`) | Database backups: unsourced |
| Cloudflare (website, R2 file storage) | Avatars and forum images (public bucket), scan photos (private bucket), web requests | Avatar files, scan photos, and forum images no post still uses | Request logs: unsourced |
| Google Firebase (login, Firestore, push) | Email, password hash or Google sign-in, saved plants under `users/{uid}`, push token | `users/{uid}` and everything under it (step `firestore`); the login (step `firebase_auth`) | Google's own logs and backups: unsourced |
| Apple (push) | Device push token, notification text | Nothing to remove: we blank our copy of the token | Unsourced |
| Plant.id and plant.health (Kindwise; Czech Republic) | Scan photos only, as image data. No name, email or account id is sent, and we do not keep the request's access token | Nothing | The result is available for 6 months (Kindwise handbook). Whether the photo is kept as long: unsourced |
| PlantNet (France) | Scan photos only, as image data | Nothing | The API terms say photos "are not stored in the database" and are held in memory only while the request runs |
| OpenAI (United States) | Text of posts and private messages from new or not-yet-trusted members (spam screen); title and opening post of public topics (search index); text sent to an AI feature. No email address | Nothing | Abuse-monitoring logs: up to 30 days for embeddings and completions, none for moderation requests. Not used for training |
| Sentry (United States) | Error reports from the website and servers; a masked recording of a website session that hit an error. `send_default_pii` is off and request bodies are never sent | Nothing | Errors and replays: 90 days on Team and Business plans, 30 days on Developer |
| Resend (United States) | Recipient address and the content of each email we send | Nothing | Per the plan's retention window; its length is unsourced |
| Apple and Google (stores) | Purchase receipts (when in-app purchase ships) | Nothing | Held by the store under its own terms |
| Google (web sign-in) | The member's browser signs in at Google; Google returns the name and email to us. We send only the sign-in code exchange | The `SocialAccount` link row (Google uid and profile data; no OAuth token is stored), deleted with the account rows (`user.delete()` cascades) | Google's own account records: under Google's terms |
| Browser push services (Google, Mozilla, Apple, Microsoft; chosen by the member's browser) | The push endpoint the browser gave us and the notification text, signed with our VAPID key | Nothing to remove there: our `PushSubscription` rows go with the account (`user.delete()` cascades) | Unsourced |
| Anthropic (United States) | Owner-run only, never in production: the `rag_eval_judged` command sends evaluation questions and the answers built from public forum topics and blog posts | Nothing | Unsourced |

YouTube and Vimeo are not processors: a video a member embeds loads from that
service in the viewer's browser.

Wired in code but not declared in `.railway/railway.ts` (checked 2026-11-17),
so presumed unset in production; confirm on Railway. If one is set, it needs
a full row above:

- GitHub sign-in (`GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`): would receive
  the sign-in code exchange and return the member's GitHub profile and email
  (`backend/apps/users/oauth_views.py`).
- OpenWeather (`OPENWEATHER_API_KEY`, read in
  `backend/apps/garden_calendar/services/weather_service.py`): would receive a
  garden's latitude and longitude, which is precise location. No caller
  outside its tests was found.
- Unsplash (`UNSPLASH_ACCESS_KEY`): plant names only (below).

These outside services receive no personal information, so they are not
processors: Trefle (`TREFLE_API_KEY`), Pexels (`PEXELS_API_KEY`) and Unsplash
(`UNSPLASH_ACCESS_KEY`), which get a plant-name search query and the API key;
the YouTube and Vimeo oEmbed lookups (the video link a member posted); and
link-preview fetches (the page a member linked, fetched by our server with no
cookie or account detail).

## Settings key index

Each key that opens a connection to an outside service, and the row above it
belongs to. Checked on 2026-11-17 against every key in
`grep -oE 'config\("[A-Z0-9_]+' backend/plant_community_backend/settings.py`
and every `config(`, `os.getenv(` and `os.environ.get(` key under
`backend/apps` and `backend/packages`; the rest are switches, limits and our
own URLs.

| Key | Row |
|-----|-----|
| `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Railway |
| `USE_R2`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT_URL`, `R2_CUSTOM_DOMAIN`, `R2_BUCKET_NAME`, `R2_SCANS_BUCKET_NAME` | Cloudflare |
| `FIREBASE_CREDENTIALS_PATH`, `FIREBASE_CREDENTIALS_B64`, `FIREBASE_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS` | Google Firebase; Apple (push goes through FCM) |
| `GOOGLE_OAUTH2_CLIENT_ID`, `GOOGLE_OAUTH2_CLIENT_SECRET` | Google (web sign-in) |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | GitHub (not declared in production) |
| `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY` | Browser push services |
| `PLANT_ID_API_KEY`, `PLANT_HEALTH_API_KEY` | Plant.id and plant.health |
| `PLANTNET_API_KEY` | PlantNet |
| `OPENAI_API_KEY` | OpenAI |
| `SENTRY_DSN` | Sentry |
| `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `RESEND_WEBHOOK_SECRET` | Resend |
| `ANTHROPIC_API_KEY` | Anthropic (owner-run command only) |
| `OPENWEATHER_API_KEY` | OpenWeather (not declared in production) |
| `TREFLE_API_KEY`, `PEXELS_API_KEY`, `UNSPLASH_ACCESS_KEY` | Not processors (above) |

A new key here that reaches an outside service needs a row in the register
and in this index, in the same pull request.

## Breaches

A breach at any processor above is handled as our own breach:
`docs/operations/breach-runbook.md`, recorded in
`docs/operations/breach-register.md`.

## Deletion routes

Use these when a person asks for deletion beyond what the job does, and always
for an account deleted as under the minimum age.

- **Plant.id (Kindwise).** No route by account: nothing we send identifies the
  person, and we keep no token for the request. Kindwise's FAQ says deleting
  an identification costs no credits, so a delete call exists, but it needs
  the request's access token, which we do not store. Route: email
  `support@kindwise.com` with the API key's account and the date range, and
  ask for the images to be deleted. Otherwise the result expires in 6 months.
- **PlantNet.** Nothing to delete by its terms. For a written confirmation,
  use the contact page linked from the API terms.
- **OpenAI.** No per-request delete. Logs expire within 30 days. An
  organisation can apply for zero data retention; that is approval-based.
- **Sentry.** Delete the issue, or the replay, in the Sentry interface or
  through its API. Find it by the time of the request; reports carry no email
  address. Otherwise it expires with the plan's retention period.
- **Resend.** No per-email delete was found in its documentation. Route:
  Resend support, naming the recipient address. Turning off content storage
  is a paid add-on with eligibility rules.
- **Google Firebase and Apple.** The job removes the login and the saved
  plants. For anything further, use the provider's data-request form from the
  developer account.
- **Railway and Cloudflare.** The job removes the rows and files. Backups and
  logs age out on the provider's schedule (unsourced).

Record each request sent to a processor, and its answer, with the access or
deletion request it belongs to (`docs/operations/access-requests.md`).

## Sources

Read on 2026-11-10.

- Kindwise handbook: <https://www.kindwise.com/handbook>; FAQ:
  <https://www.kindwise.com/faq>
- Pl@ntNet API terms: <https://my.plantnet.org/terms_of_use>
- OpenAI, "Your data": <https://developers.openai.com/api/docs/guides/your-data>
- Sentry retention periods:
  <https://docs.sentry.io/security-legal-pii/security/data-retention-periods/>;
  security page: <https://sentry.io/security>
- Resend, regions (read 2026-11-25):
  <https://resend.com/docs/dashboard/domains/regions>
- Cloudflare R2, data location (read 2026-11-25):
  <https://developers.cloudflare.com/r2/reference/data-location/>
- Resend, message content storage:
  <https://resend.com/docs/knowledge-base/how-do-i-ensure-sensitive-data-isnt-stored-on-resend>

## Open

- Agreement (data-processing terms) link for each processor: not collected.
- Storage region, read 2026-11-11: Sentry ingests at `ingest.us.sentry.io`
  (United States); both R2 buckets are `WNAM` (western North America) with
  jurisdiction `default`; Railway `us-west2`; Firestore `nam5`. Read
  2026-11-25: Resend stores account data, email metadata, logs and API records
  in the United States whatever the sending region; the R2 `WNAM` hint is best
  effort, not a guarantee. Still not sourced: PlantNet's hosting country and
  whether OpenAI processes outside the United States.
- Every "unsourced" cell above.
