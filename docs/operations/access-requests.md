# Access, correction and deletion requests

Taken on 2026-11-10 (auth + legal audit, row L13; todo 707).

What to do when a person emails `[[CONTACT_EMAIL]]` asking to see, correct,
receive a copy of, or delete their personal information, or to object to a
use of it. The Privacy Policy promises all of these
(`web/src/content/legal/privacy.{en,es,fr}.md`, "Your rights").

There is no export tool. Every step below is done by hand by the operator.
This is a reading of the statute text, not legal advice.

## Deadlines

Answer within **20 business days** of receiving the request, and never later
than **30 calendar days**. If the answer is yes, carry it out within 15
business days after answering.

- Mexico, LFPDPPP art. 31: 20 business days to answer, 15 more to carry it
  out; each can be extended once, for the same length, with a reason.
- The Privacy Policy: 30 days, or sooner where the law where the person
  lives sets a shorter time.

The request is free (LFPDPPP art. 34; the policy says so). Log the date
received on the day it arrives: the clock starts then, not when it is read.

## 1. Confirm who is asking

Do not disclose or change anything until this is done.

- The request must come from the account's email address. Reply to that
  address, not to a different one given in the message, and ask the person to
  confirm.
- If they no longer have that address, ask for the username and two things
  only the owner would know (for example the month the account was made and
  the name of a garden bed). Collect no identity documents.
- A request made for someone else needs that person's confirmation from the
  account's address. For a child under the minimum age, the parent's request
  is enough to delete; see section 4.
- If identity cannot be confirmed, say so in the reply, within the deadline.

## 2. Access, or a portable copy

Collect from every store in `docs/legal/data-inventory.md`:

| Store | What to collect | How |
|-------|-----------------|-----|
| Postgres | Account and profile, consent record, garden data, scans and results, health checks, events, forum posts, topics, sent messages, reports filed, blocks and mutes, newsletter subscription, push-token presence | Django admin or `manage.py shell` against production, filtered by the user's id |
| Postgres, email log | Emails sent, delivery and bounce records, click records (90 days) | `EmailNotification` rows for the user and the address |
| Postgres, blog views | IP address, browser and referrer per view (90 days) | `BlogPostView` rows for the user |
| Postgres, audit log | Entries about the user or made by the user (90 days) | django-auditlog `LogEntry` rows |
| Firestore | Saved plants | `users/{firebase_uid}/identified_plants` |
| File storage | Avatar, scan photos, images in their posts | The file names on the rows above |

Leave out other people's information: the other side of a private
conversation, who reported them, and moderator notes about other members.

Send the copy as JSON files plus the image files, in one archive, to the
account's address. That is the portable format. Also name the processors and
countries in `docs/operations/processors.md`, which the policy lists.

## 3. Correction

The person can edit their profile, garden data and posts themselves. For
anything they cannot edit (username, a record with a wrong date), change it
in the admin and reply saying what was changed.

## 4. Deletion

- **Whole account.** Point them to the app's settings, the website's settings
  or `/delete-account`. If they cannot sign in, delete it for them from the
  admin's delete action. Never delete the user row directly: the action calls
  `request_account_deletion`, which also erases Firebase and the files.
- **Under the minimum age.** Use the admin's under-age delete action (the one
  that blocks re-sign-up; reason `under_13`). It reaches further: reported posts,
  messages they sent, their quoted words and the text of reports they filed.
  Then send the processor requests in `docs/operations/processors.md`.
- **One post.** Remove it in the forum's moderation tools and reply.
- **What is kept, and why,** is listed in the policy under "When you delete
  your account". Say so in the reply if any of it applies.

## 5. Objection or withdrawal of consent

- **Email.** Unsubscribe them and confirm.
- **Email click records and blog-view logging.** There is no per-person
  switch. Delete their existing rows (`EmailNotification` click records,
  `BlogPostView`) and say that new records can only be stopped by closing the
  account. This gap is recorded in todo 701.
- **A private message the spam screen refused.** The message was not kept.
  Look at the screen's log entry for the time they give, and reply with what
  happened and whether their account's standing was changed.

## 6. Reply and record

The reply says what was done, or why not, and that they can complain to the
regulator for where they live (the policy lists them).

Keep one line per request: date received, kind, how identity was confirmed,
date answered, what was done, and any processor requests sent. Do not keep
the copy that was sent. Where this record lives is decided at launch, with
the breach register (todo 702); until then, a private note.
