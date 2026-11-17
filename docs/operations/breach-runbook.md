# Personal-data breach runbook

Written on 2026-11-17 (auth + legal audit, row H4; todo 702).

What to do when personal information Houseplant MD holds is lost, or someone
who should not have it reads, copies, changes or receives it. This covers a
leaked database or backup, a leaked key that opens one, a bug that shows one
member's data to another, an email sent to the wrong people, and a breach at a
processor (`docs/operations/processors.md`) that touches our data.

This is a reading of the statute text, not legal advice. Where the laws below
differ, follow the strictest. A citation marked *(not re-read)* was not
checked against the statute on 2026-11-17 (see Sources): confirm it before
relying on it. The owner should read this file before it is
relied on, and a lawyer should check the thresholds before launch.

The person who runs this procedure, signs the notices and answers the
regulators is `[[PRIVACY_OFFICER_NAME]]`, at `[[CONTACT_EMAIL]]`, for
`[[COMPANY_NAME]]`, `[[COMPANY_ADDRESS]]`. These are filled in at launch with
the other operator fields (owner decision 2026-11-17).

## 0. The first hour

1. **Write it down.** Open a row in `docs/operations/breach-register.md` now,
   with the time you found out. Every deadline below runs from the day you
   knew, or reasonably believed, that a breach happened, not from the day the
   cause was found.
2. **Stop it.** Contain before you investigate:
   - Leaked secret: rotate it where it lives (Railway variables for the
     backend, the provider's console for an API key). Set the new value on
     **every** service that declares it in `.railway/railway.ts`:
     `SECRET_KEY`, `JWT_SECRET_KEY` and the `R2_*` keys are on both
     `plant_id_community` and `forum-prune-cron`. Redeploy both.
     - Only `JWT_SECRET_KEY` signs members out: JWTs are signed with it
       (`SIMPLE_JWT["SIGNING_KEY"]`), not with `SECRET_KEY`. The mobile app
       can still trade its Firebase session for a new JWT, so for an
       account known to be compromised also revoke its refresh tokens
       (`apps.users.account_links.revoke_refresh_tokens`).
     - Rotating `SECRET_KEY` voids every signed link already emailed
       (unsubscribe, click redirect, account deletion, email verification).
       That is expected; say so if people ask.
   - Leaked database or Redis credentials: rotate them in Railway, then
     redeploy both services (`plant_id_community` and `forum-prune-cron`).
   - Bug exposing data: revert the change (`git revert`, a pull request, the
     normal deploy) or turn its feature flag off.
   - Public file that should be private: remove the object from R2 (and any
     rendition or derived keys made from it), then purge its URL from the
     Cloudflare cache for the `R2_CUSTOM_DOMAIN` zone. Deleting the object
     alone leaves cached copies reachable. Confirm a fetch of the URL now
     returns 404.
3. **Keep the evidence.** Save the Railway and Sentry logs for the window
   before they age out. Do not delete rows or logs that show what happened.
4. **Find the scope.** Which tables, files or emails; which accounts; from
   when to when. Count the people, and note which country or province each is
   in (the account's country, where known, or the IP country in the logs).

## 1. Is there a real risk of significant harm?

Both Canadian laws below use the same test: notify when a reasonable person
would consider that the breach creates a **real risk of significant harm** to
someone. Weigh two things together (PIPEDA s. 10.1(8)):

- **How sensitive is the information?** High: passwords or password hashes,
  login tokens, private messages, precise location, payment details, anything
  about a child. Lower: a username or a public forum post that was already
  public.
- **How likely is misuse?** Higher: taken by an outsider on purpose, seen on
  a public page or a paste site, not encrypted, still out there. Lower: sent
  to one trusted person who confirms in writing that they deleted it,
  recovered before anyone opened it, or encrypted with a key that was not
  taken.

"Significant harm" includes bodily harm, humiliation, damage to reputation or
relationships, loss of a job or of business opportunities, financial loss,
identity theft, harm to a credit record, and loss of or damage to property
(PIPEDA s. 10.1(7)).

When in doubt, treat it as notifiable. Write the reasoning in the register
row either way: a "not notifiable" decision must show why.

## 2. Who is told, when, and what each notice says

Every breach, notifiable or not, is recorded in the register (section 3).

### Alberta: the Information and Privacy Commissioner (OIPC)

Alberta PIPA governs the personal information this Alberta business collects
and holds.

- **When:** without unreasonable delay, for any loss of, or unauthorized
  access to or disclosure of, personal information where a reasonable person
  would consider there is a real risk of significant harm (PIPA s. 34.1)
  *(not re-read)*.
- **How:** in writing, using the OIPC breach report form on
  <https://oipc.ab.ca>.
- **What it contains** (PIPA Regulation s. 19) *(not re-read)*:
  1. what happened, and how;
  2. the date or period of the breach;
  3. the personal information involved;
  4. our assessment of the risk of harm;
  5. the estimated number of people affected;
  6. what we did to reduce the risk of harm;
  7. what we did, or will do, to notify the people affected;
  8. the name and contact of the person who can answer the Commissioner's
     questions about it.
- **People affected:** the Commissioner may require us to notify them
  (PIPA s. 37.1). Do not wait to be told: notify them as in the PIPEDA
  section below, which requires it anyway.
- Failing to notify is an offence (PIPA s. 59) *(not re-read)*.

### Canada: the Office of the Privacy Commissioner (OPC)

PIPEDA applies to personal information that crosses a provincial or national
border in commercial activity, which ours does: it is stored by Railway in the
United States and sent to the other processors in the register. So a
notifiable breach is reported to the OPC as well as the OIPC.

- **When:** as soon as feasible after we determine the breach happened
  (PIPEDA s. 10.1(1) and (2)).
- **How:** the OPC's online breach report form on <https://www.priv.gc.ca>.
  New facts found later are sent as an update to the same report.
- **What it contains** (Breach of Security Safeguards Regulations s. 2):
  1. what happened and, if known, the cause;
  2. the day or period of the breach (or an approximation);
  3. the personal information involved, as far as known;
  4. the number of people affected (or an approximation);
  5. what we did to reduce the risk of harm or to mitigate it;
  6. what we did, or will do, to notify the people affected;
  7. the name and contact of the person who can answer the OPC's questions.
- **People affected — when:** as soon as feasible after we determine the
  breach happened (s. 10.1(3), (6)). The notice must be conspicuous and give
  enough for the person to understand what it means for them and to act on it
  (s. 10.1(4), (5)).
- **People affected — what the notice says** (Regulations s. 3):
  1. what happened;
  2. the day or period of the breach;
  3. the personal information involved;
  4. what we did to reduce the risk of harm;
  5. what they can do to reduce the risk, or mitigate it (for example change
     the password, watch for phishing emails that use their name);
  6. contact information they can use to find out more
     (`[[CONTACT_EMAIL]]`).
- **How people are told:** directly, by email to the account's address
  (Regulations s. 4). An indirect notice (a public notice, such as a banner
  in the apps and on the website, that could reasonably be expected to reach
  them) is allowed only when direct notice would likely cause further harm,
  would likely cause undue hardship for us, or we have no contact details for
  them (Regulations s. 5).
- **Others who can reduce the harm** (s. 10.2(1)): tell any organisation or
  government body that can reduce the risk, for example a processor whose key
  leaked, or the police for a theft. Record each one in the register.
- Knowingly failing to report, notify or keep the record is an offence with a
  fine of up to $100,000 (PIPEDA s. 28) *(not re-read)*.

### California: affected residents, and the Attorney General

Applies when a California resident's **unencrypted** "personal information"
as the statute defines it was, or is reasonably believed to have been,
acquired by an unauthorized person (Civil Code s. 1798.82) *(not re-read:
the statute and the Attorney General's site refused or did not answer on
2026-11-17)*. For us the
definition is met mainly by **a username or email address together with a
password or security answer that would let someone into the account**.
Plant photos, posts and display names alone do not trigger it.

- **When:** in the most expedient time possible and without unreasonable
  delay. SB 446 (2025) is understood to add an outer limit of **30 calendar
  days** after the breach was found, from 2026-01-01; work to 30 days until
  the current text of s. 1798.82(a) says otherwise. A law-enforcement request
  is the only allowed reason to delay.
- **What it contains:** title "Notice of Data Breach", with the headings
  "What Happened", "What Information Was Involved", "What We Are Doing",
  "What You Can Do" and "For More Information", in type no smaller than
  10-point. It gives our name and contact, the types of information involved,
  the date or estimated date or period of the breach, the date of the notice,
  whether the notice was delayed for law enforcement, and a general
  description of what happened.
- **Login details only:** when only a username or email and password leaked,
  the notice may be sent by email and must tell the person to change their
  password and security answers here and anywhere else they use the same
  ones (s. 1798.82(d)(4)).
- **Attorney General — when:** if more than 500 California residents are
  notified for one breach, send a sample copy of the notice, with personal
  details removed, through the Attorney General's online form
  (s. 1798.82(f); oag.ca.gov, read 2026-11-17, gives no deadline). SB 446 is
  understood to require it within **15 calendar days** of notifying the
  residents; send it the same day as the residents' notice and the question
  does not arise.
- **Attorney General — what it contains:** a copy of the notice sent to the
  residents.

Other US states have their own breach laws, with different definitions and
deadlines. The California rules above are among the strictest; if people in
another state are affected, read that state's statute before sending.

### Mexico: affected people

Applies when the breach affects people in Mexico (LFPDPPP, DOF 20-03-2025,
last reform 14-11-2025).

- **When:** "de forma inmediata" (immediately), for a breach at any stage of
  processing that significantly affects the property or moral rights of the
  people concerned, so that they can take steps to defend their rights
  (art. 19, read 2026-11-17).
- **What it contains:** art. 19 lists no contents. Give at least what the
  PIPEDA notice above gives: what happened, the personal information
  involved, what they can do to protect themselves, what we did straight away
  to fix it, and where to find out more. The law's Regulation may list
  contents *(not re-read)*.
- **Regulator:** the authority is the Secretaría Anticorrupción y Buen
  Gobierno. Art. 19 requires notice to the people affected only, not to the
  authority. Record the breach in the register as for every other one.

### A breach at a processor

If a processor tells us of a breach (Railway, Cloudflare, Google, Sentry,
Resend, OpenAI, Kindwise, PlantNet, or another listed in
`docs/operations/processors.md`), it is our breach to assess and report: we
are the organisation the information belongs to. Start at section 0 on the
day their notice arrives.

## 3. The record

Every breach goes in `docs/operations/breach-register.md`, including ones
judged not notifiable. Keep each row for at least **24 months** after the day
we determined the breach happened (PIPEDA s. 10.3; Regulations s. 6), and
give a copy to the OPC if it asks. The row must hold enough to show whether
the notices were required and were sent.

The register is in a public repository. Write the row without names, email
addresses or other details that identify a person; keep any list of the
people affected outside the repository, where the register row says.

## 4. Afterwards

- Fix the cause, with a test where one can be written, and file a todo for
  anything not fixed in the same pull request.
- Add a `docs/LEARNINGS.md` entry if the cause is something the next change
  could repeat.
- Update `docs/operations/processors.md` if a processor was involved.

## Sources

Read on 2026-11-17:

- PIPEDA, ss. 10.1 to 10.3:
  <https://laws-lois.justice.gc.ca/eng/acts/P-8.6/page-3.html>
- Breach of Security Safeguards Regulations (SOR/2018-64), ss. 2 to 6:
  <https://laws-lois.justice.gc.ca/eng/regulations/SOR-2018-64/FullText.html>
- Mexico, LFPDPPP art. 19:
  <https://www.diputados.gob.mx/LeyesBiblio/pdf/LFPDPPP.pdf>
- California Attorney General, data breach reporting:
  <https://www.oag.ca.gov/privacy/databreach/reporting>

Not re-read on 2026-11-17 (marked *(not re-read)* above; confirm before
relying on them):

- PIPEDA s. 28 (offence and fine).
- Alberta Personal Information Protection Act, ss. 34.1, 37.1 and 59, and
  its Regulation, s. 19: <https://kings-printer.alberta.ca>
- California Civil Code s. 1798.82 and SB 446 (2025): leginfo refused the
  fetch.
  <https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1798.82>
