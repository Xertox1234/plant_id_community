import logging

from apps.core.notification_ops import log_broker_failure

logger = logging.getLogger("forum_host.notifications")


def _drop_blocked_pairs(users, actor):
    """A mention/reply notification (bell + push + email) must never fire
    between a blocked pair, either direction (todo 284/M9).

    Read-time filtering (wagtail_forum.api.notifications._visible_notifications)
    only hides an EXISTING bell row for a recipient's own list — it does
    nothing to stop the notification from being CREATED and its push/email
    enqueued in the first place. This is the fan-out-time counterpart: called
    before create_notifications() so a blocked pair produces no row and no
    delivery at all, not just a hidden one.
    """
    if actor is None or not users:
        return users
    from wagtail_forum.models import UserBlock

    ids = [u.pk for u in users]
    blocked = set(
        UserBlock.objects.filter(blocker=actor, blocked_id__in=ids).values_list(
            "blocked_id", flat=True
        )
    )
    blocked |= set(
        UserBlock.objects.filter(blocked=actor, blocker_id__in=ids).values_list(
            "blocker_id", flat=True
        )
    )
    # Mute (todo 347): a recipient who muted the actor gets nothing from
    # them either — ONE direction: the actor muting a recipient changes
    # nothing about what that recipient receives.
    from wagtail_forum.models import UserMute

    blocked |= set(
        UserMute.objects.filter(muted=actor, muter_id__in=ids).values_list(
            "muter_id", flat=True
        )
    )
    return [u for u in users if u.pk not in blocked]


def dispatch(event, **kwargs):
    """Route a forum signal event to FCM/email via background Celery tasks.

    Importing the task here (inside the function) keeps the module importable
    even before the Celery app is ready (e.g. during migrations).

    Supported events
    ----------------
    reply_added
        Notifies every subscriber to the topic (todo 253 slice 3, H2/H3) —
        auto-subscribes the reply's author for future replies, then fans out
        to the topic's subscriber list, excluding the replying author
        themselves. Also resolves @mentions in the reply (todo 253 slice 4,
        H4): a mentioned subscriber gets a "mention" notification instead of
        a "reply" one for this post, never both. Also marks the reply as
        already-read for its own author (todo 253 slice 5, H10) — otherwise
        the topic's last_post_at, about to be bumped to this reply's own
        timestamp, would outrun their prior TopicRead/watermark and badge
        their own topic "unread" to themselves. kwargs: topic (Topic), post
        (Post). Persists one Notification row per recipient (todo 253 slice
        1) synchronously in the ambient (publish) transaction — it rolls
        back cleanly if the publish does — and defers the push AND email
        enqueue (one per recipient) to transaction.on_commit so neither can
        ever fire for a publish that later rolls back. The email (todo 253
        slice 2, H1) reuses NotificationService.send_forum_reply_notification,
        gated by each recipient's forum_notifications preference inside that
        service. Mentioned and quoted members also get an email batch of
        their own (todo 624): the optional, off-by-default important-event
        email, merged with the reply email so a mentioned subscriber gets
        one message, never two.

    moderation_decided
        Notifies the post's author of their content's moderation outcome.
        kwargs: obj (Post|Topic), status ("published"|"pending").

    answer_accepted
        Notifies the author of the post just accepted as a topic's answer
        (audit H6). kwargs: topic (Topic), post (Post), actor (User — whoever
        accepted, NOT the post's author). Exactly one recipient, so it uses
        the single-recipient `send_forum_push` rather than the batch task.
        Silent when the acceptor and the answer's author are the same person
        (the common self-answer case) and when the answer's author has
        deleted their account.

    topic_created
        Auto-subscribes the topic's own author (todo 253 slice 3) so future
        replies fan out to them, and resolves @mentions in the opening post
        (todo 253 slice 4, H4) — reply_added only sees replies, so a mention
        in a new topic's first post needs its own handling here. Also marks
        the opening post as already-read for the topic's own author (todo
        253 slice 5, H10), same reasoning as reply_added. No reply
        push/email of its own — just the subscription row, the read marker,
        and any mention notifications.
    """
    from apps.core import delivery
    from apps.users.services import web_push_enabled
    from django.db import transaction

    from .tasks import (
        send_forum_email_batch,
        send_forum_push,
        send_forum_push_batch,
        send_forum_web_push_batch,
    )

    web_push_on = web_push_enabled()

    def _record(kind, event_name, users, post):
        """The outbox rows for one batch (todo 619), written in the ambient
        transaction with the bell rows: they exist exactly when the event
        does, and reconciliation recovers a batch whose enqueue is lost.
        None when there is nothing to record (the task then runs without
        bookkeeping, as before the outbox)."""
        if kind == delivery.Kind.FORUM_WEB_PUSH and not web_push_on:
            return None
        return delivery.record_batch(
            kind,
            event_name,
            [user.pk for user in users],
            _build_payload(post),
            subject_key=getattr(post, "id", ""),
        )

    def _record_events(post, *groups):
        """The mobile-push rows for each (event, users, name) group, and the
        email rows for the mentioned and quoted ones (todo 624): every
        channel a hold or a fold can touch is in the outbox."""
        out = {}
        for event_name, users, name in groups:
            out[f"{name}_push"] = _record(
                delivery.Kind.FORUM_PUSH, event_name, users, post
            )
            if name in ("mention", "quote"):
                out[f"{name}_email"] = _record(
                    delivery.Kind.FORUM_EMAIL, event_name, users, post
                )
        return out

    def _enqueue_web_push(event_name, pks, payload, batch_id=None):
        # Browser push beside FCM (todo 413): its own task, so FCM retries
        # never resend a browser notification. Never raises into the signal.
        # A lost enqueue is still recovered: its outbox rows stay pending
        # for reconciliation (todo 619).
        if not pks:
            return
        try:
            extra = {"batch_id": batch_id} if batch_id else {}
            send_forum_web_push_batch.delay(event_name, list(pks), payload, **extra)
        except Exception:
            log_broker_failure(
                logger,
                "[CELERY] forum_host: failed to enqueue web push for event=%s",
                event_name,
            )

    topic = kwargs.get("topic")
    topic_id = getattr(topic, "id", None)

    def _build_payload(post):
        # actor_name feeds the FCM tray notification's body line (todo 253
        # slice 6). This is HOST-app code, so the host User model's
        # display_name property is the right source — the same naming policy
        # the email channel already uses (send_forum_email reads
        # post.author.display_name); the package-side host-agnostic rule
        # (slice 4) applies to wagtail_forum code, not here.
        # actor_id is the host's send-time recheck input (todo 619,
        # eligibility.py): it is never sent to a device or a browser.
        author = getattr(post, "author", None)
        return {
            "topic_id": str(topic_id),
            "topic_title": topic.title if topic else "",
            "post_id": str(getattr(post, "id", "")),
            "actor_name": (
                getattr(author, "display_name", "") if author is not None else ""
            ),
            "actor_id": str(author.pk) if author is not None else "",
        }

    def _quoted_authors_for(post, actor, *, exclude_pks=()):
        """[(author, quoted_post)] a quoting post notifies — visible quoted
        posts only, the actor and already-mentioned users excluded, blocked
        pairs dropped (wagtail_forum.quotes.resolve_quoted_authors + the
        same bidirectional block rule as mentions)."""
        from wagtail_forum.quotes import resolve_quoted_authors

        if post is None:
            return []
        exclude = set(exclude_pks) | ({actor.pk} if actor is not None else set())
        pairs = resolve_quoted_authors(post, exclude_pks=exclude)
        kept = {u.pk for u in _drop_blocked_pairs([u for u, _ in pairs], actor)}
        return [(u, q) for u, q in pairs if u.pk in kept]

    def _batch_kwargs(batch_id):
        return {"batch_id": batch_id} if batch_id else {}

    def _enqueue_email_for(event_name, users, payload, batch_id=None):
        # The optional important-event email (todo 624): enqueued for every
        # mentioned/quoted member; the task sends only to those who turned
        # that email on, or who follow the topic and want reply email (one
        # merged email, never two).
        pks = [user.pk for user in users]
        if not pks:
            return
        try:
            send_forum_email_batch.delay(
                event_name, pks, payload, **_batch_kwargs(batch_id)
            )
        except Exception:
            # The outbox rows stay pending for reconciliation (todo 619).
            log_broker_failure(
                logger,
                "[CELERY] forum_host: failed to enqueue %s email batch",
                event_name,
            )

    def _enqueue_quote_push_for(users, payload, web_batch=None, batch=None):
        # Same shape as the mention push: batch task, event "quote" (copy in
        # notification_copy.py).
        from wagtail_forum.models import NotificationVerb

        pks = [user.pk for user in users]
        if not pks:
            return
        try:
            send_forum_push_batch.delay(
                NotificationVerb.QUOTE, pks, payload, **_batch_kwargs(batch)
            )
        except Exception:
            log_broker_failure(
                logger, "[CELERY] forum_host: failed to enqueue quote push batch"
            )
        _enqueue_web_push(NotificationVerb.QUOTE, pks, payload, web_batch)

    def _enqueue_mention_push_for(mentioned, payload, web_batch=None, batch=None):
        from wagtail_forum.models import NotificationVerb

        mentioned_pks = [user.pk for user in mentioned]
        if not mentioned_pks:
            return
        try:
            # One batched enqueue for all mentioned recipients (todo 268).
            send_forum_push_batch.delay(
                NotificationVerb.MENTION,
                mentioned_pks,
                payload,
                **_batch_kwargs(batch),
            )
        except Exception:
            log_broker_failure(
                logger, "[CELERY] forum_host: failed to enqueue mention push batch"
            )
        _enqueue_web_push(NotificationVerb.MENTION, mentioned_pks, payload, web_batch)

    if event == "reply_added":
        post = kwargs.get("post")
        post_author = getattr(post, "author", None)

        from wagtail_forum.mentions import resolve_mentioned_users
        from wagtail_forum.models import NotificationVerb, TopicRead, TopicSubscription
        from wagtail_forum.notifications import create_notifications

        payload = _build_payload(post)

        def _enqueue_push():
            # One batched enqueue for all reply recipients + one for mentions
            # (todo 268) — constant enqueue count regardless of subscriber count,
            # instead of one .delay() per recipient blocking the request thread.
            reply_recipient_pks = [user.pk for user in reply_recipients]
            if reply_recipient_pks:
                try:
                    send_forum_push_batch.delay(
                        event,
                        reply_recipient_pks,
                        payload,
                        **_batch_kwargs(batches.get("reply_push")),
                    )
                except Exception:
                    log_broker_failure(
                        logger,
                        "[CELERY] forum_host: failed to enqueue reply push batch"
                        " for event=%s",
                        event,
                    )
                _enqueue_web_push(
                    event, reply_recipient_pks, payload, batches.get("reply_web")
                )
            _enqueue_mention_push_for(
                mentioned,
                payload,
                batches.get("mention_web"),
                batches.get("mention_push"),
            )
            _enqueue_quote_push_for(
                [user for user, _ in quoted],
                payload,
                batches.get("quote_web"),
                batches.get("quote_push"),
            )

        def _enqueue_email():
            # One batched enqueue for the reply recipients (todo 268), and
            # one each for the mentioned and quoted members (todo 624: their
            # optional email, merged with the reply email they may also
            # want, so a mentioned subscriber gets ONE email).
            _enqueue_email_for(
                NotificationVerb.MENTION,
                mentioned,
                payload,
                batches.get("mention_email"),
            )
            _enqueue_email_for(
                NotificationVerb.QUOTE,
                [user for user, _ in quoted],
                payload,
                batches.get("quote_email"),
            )
            reply_recipient_pks = [user.pk for user in reply_recipients]
            if reply_recipient_pks:
                try:
                    extra = (
                        {"batch_id": batches["reply_email"]}
                        if batches.get("reply_email")
                        else {}
                    )
                    send_forum_email_batch.delay(
                        event, reply_recipient_pks, payload, **extra
                    )
                except Exception:
                    # The outbox rows stay pending: reconciliation sends
                    # them once the broker is back (todo 619).
                    log_broker_failure(
                        logger,
                        "[CELERY] forum_host: failed to enqueue reply email batch"
                        " for event=%s",
                        event,
                    )

        try:
            # A nested atomic() scopes any DB failure to a savepoint: this
            # dispatch runs inside the ambient Wagtail publish transaction, and
            # an uncaught error here would poison that whole transaction (the
            # except must sit OUTSIDE the atomic() block, not inside it — see
            # docs/rules/forum.md) — the receiver chain's send_robust() only
            # swallows the PYTHON exception, not Postgres's aborted-transaction
            # state, so the very next write in the same transaction
            # (_refresh_for_post) would otherwise raise too.
            with transaction.atomic():
                # Auto-subscribe the replier so THEIR future replies fan out
                # too (todo 253 slice 3) — doesn't affect this event, since
                # the exclude() below always drops them from their own
                # reply's recipient list. Deliberately unconditional: this
                # re-subscribes even a user who explicitly unfollowed via
                # TopicSubscriptionView.delete — there is no persistent-mute
                # flag this slice, so replying is treated as a renewed
                # follow (plan decision 3; confirmed intentional, not a bug,
                # in the slice-3 review — two independent review angles
                # flagged this exact interaction for a sanity check).
                if post_author is not None and topic is not None:
                    TopicSubscription.subscribe(post_author, topic)
                    # Marks the replier's own reply as already-read — otherwise
                    # topic.last_post_at (about to be bumped to this reply's
                    # timestamp by _refresh_for_post, right after this handler
                    # returns) would be newer than any prior TopicRead/watermark
                    # for this user, making their OWN topic show "unread" to
                    # themselves (todo 253 slice 5 review, Angle A). Stamped
                    # from post.first_published_at, not topic.last_post_at —
                    # this notify() fires BEFORE _refresh_for_post below, so
                    # topic.last_post_at is still stale here; first_published_at
                    # is the exact value _refresh_topic_counters derives it
                    # from a moment later, so this can never land a hair behind.
                    TopicRead.mark_read(
                        post_author, topic_id, when=post.first_published_at
                    )

                mentioned = _drop_blocked_pairs(
                    resolve_mentioned_users(
                        post,
                        exclude_pks=(
                            {post_author.pk} if post_author is not None else ()
                        ),
                    ),
                    post_author,
                )
                mentioned_pks = {user.pk for user in mentioned}

                # Structured quotes (todo 342): the quoted authors get a QUOTE
                # notification instead of a plain REPLY — a mention of the same
                # person wins (excluded here); blocked pairs are dropped like
                # every other fan-out.
                quoted = _quoted_authors_for(
                    post, post_author, exclude_pks=mentioned_pks
                )
                quoted_pks = {user.pk for user, _ in quoted}

                subs = TopicSubscription.objects.filter(topic=topic).select_related(
                    "user"
                )
                if post_author is not None:
                    subs = subs.exclude(user_id=post_author.pk)
                # A mentioned subscriber gets the more-specific "mention"
                # notification instead of a second "reply" one for the same
                # post (todo 253 slice 4) — the (recipient, verb, post)
                # unique constraint doesn't collapse across different verbs,
                # so without this exclude() they'd get two bell entries.
                subs = subs.exclude(user_id__in=mentioned_pks | quoted_pks)
                # todo 284/M9: a blocked pair gets no reply notification —
                # subscribers aren't a mention case, so this is the only
                # place that path can be fixed (unlike mentioned above,
                # which resolve_mentioned_users already produces separately).
                reply_recipients = _drop_blocked_pairs(
                    [sub.user for sub in subs], post_author
                )

                create_notifications(
                    recipients=reply_recipients,
                    verb=NotificationVerb.REPLY,
                    actor=post_author,
                    topic=topic,
                    post=post,
                )
                create_notifications(
                    recipients=mentioned,
                    verb=NotificationVerb.MENTION,
                    actor=post_author,
                    topic=topic,
                    post=post,
                )
                for user, quoted_post in quoted:
                    create_notifications(
                        recipients=[user],
                        verb=NotificationVerb.QUOTE,
                        actor=post_author,
                        topic=topic,
                        post=post,
                        quoted_post=quoted_post,
                    )
                quoted_users = [user for user, _ in quoted]
                batches = {
                    **_record_events(
                        post,
                        (event, reply_recipients, "reply"),
                        (NotificationVerb.MENTION, mentioned, "mention"),
                        (NotificationVerb.QUOTE, quoted_users, "quote"),
                    ),
                    "reply_email": _record(
                        delivery.Kind.FORUM_EMAIL, event, reply_recipients, post
                    ),
                    "reply_web": _record(
                        delivery.Kind.FORUM_WEB_PUSH, event, reply_recipients, post
                    ),
                    "mention_web": _record(
                        delivery.Kind.FORUM_WEB_PUSH,
                        NotificationVerb.MENTION,
                        mentioned,
                        post,
                    ),
                    "quote_web": _record(
                        delivery.Kind.FORUM_WEB_PUSH,
                        NotificationVerb.QUOTE,
                        quoted_users,
                        post,
                    ),
                }
            # Only registered once the write above actually succeeds — a
            # notification-write failure must not still deliver a push/email,
            # or a recipient gets a delivery with no corresponding in-app
            # notification. A no-op (empty recipients) still safely registers
            # — both closures loop zero times.
            transaction.on_commit(_enqueue_push)
            transaction.on_commit(_enqueue_email)
        except Exception:
            logger.exception(
                "[ERROR] forum_host: failed to persist notification for event=%s topic=%s",
                event,
                topic_id,
            )

    elif event == "moderation_decided":
        obj = kwargs.get("obj")
        status = kwargs.get("status", "")
        author = getattr(obj, "author", None)
        if author is None:
            return
        # The moderation_decided signal never passes a `topic` kwarg — derive
        # topic_id from obj instead (Post has .topic_id, Topic has .id itself).
        from wagtail_forum.models import Post as ForumPost

        if isinstance(obj, ForumPost):
            resolved_topic_id = obj.topic_id
        else:
            resolved_topic_id = getattr(obj, "id", None)
        try:
            send_forum_push.delay(
                event,
                author.pk,
                {
                    "topic_id": (
                        str(resolved_topic_id) if resolved_topic_id is not None else ""
                    ),
                    "status": status,
                    "obj_id": str(getattr(obj, "id", "")),
                },
            )
        except Exception:
            log_broker_failure(
                logger,
                "[CELERY] forum_host: failed to enqueue push for event=%s user=%s",
                event,
                author.pk,
            )

    elif event == "answer_accepted":
        post = kwargs.get("post")
        actor = kwargs.get("actor")
        recipient = getattr(post, "author", None)
        if recipient is None:
            # The answer's author deleted their account (SET_NULL) — nobody to
            # tell. The topic's solved state still stands.
            return

        from wagtail_forum.models import NotificationVerb
        from wagtail_forum.notifications import create_notifications

        # `_build_payload` derives actor_name from the POST's author, which is
        # the recipient here, not the actor — override it with whoever accepted
        # the answer, or the tray line reads "You accepted your answer".
        payload = {
            **_build_payload(post),
            "actor_name": (
                getattr(actor, "display_name", "") if actor is not None else ""
            ),
            # The recheck's actor is the acceptor, too (todo 619).
            "actor_id": str(actor.pk) if actor is not None else "",
        }
        web_batch = None
        email_batch = None

        def _enqueue_push():
            try:
                send_forum_push.delay(event, recipient.pk, payload)
            except Exception:
                log_broker_failure(
                    logger,
                    "[CELERY] forum_host: failed to enqueue push for event=%s user=%s",
                    event,
                    recipient.pk,
                )
            _enqueue_web_push(event, [recipient.pk], payload, web_batch)
            # The optional accepted-answer email (todo 624, off by default).
            _enqueue_email_for(event, [recipient], payload, email_batch)

        try:
            # Same nested-atomic/except-outside shape as reply_added: this runs
            # in the caller's transaction (TopicSolutionView's save), so an
            # uncaught error here would poison it.
            with transaction.atomic():
                # create_notifications drops recipient == actor, so a topic
                # author accepting their OWN reply notifies nobody — and the
                # early return below keeps the push consistent with that.
                create_notifications(
                    recipients=[recipient],
                    verb=NotificationVerb.SOLUTION,
                    actor=actor,
                    topic=topic,
                    post=post,
                )
            if actor is None or recipient.pk != actor.pk:
                with transaction.atomic():
                    if web_push_on:
                        web_batch = delivery.record_batch(
                            delivery.Kind.FORUM_WEB_PUSH,
                            event,
                            [recipient.pk],
                            payload,
                            subject_key=getattr(post, "id", ""),
                        )
                    email_batch = delivery.record_batch(
                        delivery.Kind.FORUM_EMAIL,
                        event,
                        [recipient.pk],
                        payload,
                        subject_key=getattr(post, "id", ""),
                    )
                # Registered inside the try, after the write succeeded, so a
                # failed persist cannot still deliver a push (docs/rules/forum.md).
                transaction.on_commit(_enqueue_push)
        except Exception:
            logger.exception(
                "[ERROR] forum_host: failed to persist notification for event=%s topic=%s",
                event,
                topic_id,
            )

    elif event == "topic_created":
        post = kwargs.get("post")
        author = getattr(topic, "author", None)

        from wagtail_forum.mentions import resolve_mentioned_users
        from wagtail_forum.models import NotificationVerb, TopicRead, TopicSubscription
        from wagtail_forum.notifications import create_notifications

        payload = _build_payload(post)

        def _enqueue_mention_push():
            _enqueue_mention_push_for(
                mentioned,
                payload,
                batches.get("mention_web"),
                batches.get("mention_push"),
            )
            _enqueue_email_for(
                NotificationVerb.MENTION,
                mentioned,
                payload,
                batches.get("mention_email"),
            )

        try:
            # Same nested-atomic/except-outside shape as reply_added above —
            # this also runs inside the ambient publish transaction.
            with transaction.atomic():
                # Auto-subscribe the topic's own author (todo 253 slice 3) so
                # replies fan out to them — no push/email of its own, just
                # the row.
                if author is not None:
                    TopicSubscription.subscribe(author, topic)
                    # Same reasoning as reply_added above — the topic's own
                    # author already knows about the topic they just created;
                    # without this they'd see their own brand-new topic as
                    # "unread". Stamped from the opening post's
                    # first_published_at (the same value _refresh_topic_counters
                    # derives last_post_at from), not topic.last_post_at, which
                    # may not reflect this in-memory instance's freshest DB
                    # state. Skipped for an admin-created topic with no opening
                    # post — matches this function's own existing precedent for
                    # that edge case (the mention resolution below).
                    if post is not None:
                        TopicRead.mark_read(
                            author, topic_id, when=post.first_published_at
                        )
                else:
                    logger.info(
                        "[FORUM] topic_created topic=%s (no author to auto-subscribe)",
                        topic_id,
                    )

                # Opening-post mentions (todo 253 slice 4, H4) — reply_added
                # only ever sees replies, so a mention in a new topic's very
                # first post needs its own handling here. `post` is None for
                # an admin-created topic with no opening post.
                mentioned = _drop_blocked_pairs(
                    (
                        resolve_mentioned_users(
                            post, exclude_pks={author.pk} if author is not None else ()
                        )
                        if post is not None
                        else []
                    ),
                    author,
                )
                create_notifications(
                    recipients=mentioned,
                    verb=NotificationVerb.MENTION,
                    actor=author,
                    topic=topic,
                    post=post,
                )
                # An opening post can quote too (todo 342).
                quoted = (
                    _quoted_authors_for(
                        post, author, exclude_pks={user.pk for user in mentioned}
                    )
                    if post is not None
                    else []
                )
                for user, quoted_post in quoted:
                    create_notifications(
                        recipients=[user],
                        verb=NotificationVerb.QUOTE,
                        actor=author,
                        topic=topic,
                        post=post,
                        quoted_post=quoted_post,
                    )
                batches = {
                    **_record_events(
                        post,
                        (NotificationVerb.MENTION, mentioned, "mention"),
                        (NotificationVerb.QUOTE, [user for user, _ in quoted], "quote"),
                    ),
                    "mention_web": _record(
                        delivery.Kind.FORUM_WEB_PUSH,
                        NotificationVerb.MENTION,
                        mentioned,
                        post,
                    ),
                    "quote_web": _record(
                        delivery.Kind.FORUM_WEB_PUSH,
                        NotificationVerb.QUOTE,
                        [user for user, _ in quoted],
                        post,
                    ),
                }

            def _enqueue_quotes():
                _enqueue_quote_push_for(
                    [user for user, _ in quoted],
                    payload,
                    batches.get("quote_web"),
                    batches.get("quote_push"),
                )
                _enqueue_email_for(
                    NotificationVerb.QUOTE,
                    [user for user, _ in quoted],
                    payload,
                    batches.get("quote_email"),
                )

            transaction.on_commit(_enqueue_mention_push)
            transaction.on_commit(_enqueue_quotes)
        except Exception:
            logger.exception(
                "[ERROR] forum_host: failed to process topic_created topic=%s",
                topic_id,
            )

    else:
        logger.warning("[FORUM] notifications: unknown event %r", event)
