import logging

logger = logging.getLogger("forum_host.notifications")


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
        service, and is sent only to "reply" recipients — a mention notifies
        via bell + push only, no email this slice.

    moderation_decided
        Notifies the post's author of their content's moderation outcome.
        kwargs: obj (Post|Topic), status ("published"|"pending").

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
    from django.db import transaction

    from .tasks import send_forum_email, send_forum_push

    topic = kwargs.get("topic")
    topic_id = getattr(topic, "id", None)

    def _build_payload(post):
        return {
            "topic_id": str(topic_id),
            "topic_title": topic.title if topic else "",
            "post_id": str(getattr(post, "id", "")),
        }

    def _enqueue_mention_push_for(mentioned, payload):
        from wagtail_forum.models import NotificationVerb

        for recipient in mentioned:
            try:
                send_forum_push.delay(NotificationVerb.MENTION, recipient.pk, payload)
            except Exception:
                logger.exception(
                    "[CELERY] forum_host: failed to enqueue push for event=%s user=%s",
                    "mention",
                    recipient.pk,
                )

    if event == "reply_added":
        post = kwargs.get("post")
        post_author = getattr(post, "author", None)

        from wagtail_forum.mentions import resolve_mentioned_users
        from wagtail_forum.models import NotificationVerb, TopicRead, TopicSubscription
        from wagtail_forum.notifications import create_notifications

        payload = _build_payload(post)

        def _enqueue_push():
            for recipient in reply_recipients:
                try:
                    send_forum_push.delay(event, recipient.pk, payload)
                except Exception:
                    logger.exception(
                        "[CELERY] forum_host: failed to enqueue push for event=%s user=%s",
                        event,
                        recipient.pk,
                    )
            _enqueue_mention_push_for(mentioned, payload)

        def _enqueue_email():
            # Mentioned users get bell + push only, not email, this slice
            # (todo 253 slice 4 scope decision) — loop reply_recipients only.
            for recipient in reply_recipients:
                try:
                    send_forum_email.delay(event, recipient.pk, payload)
                except Exception:
                    logger.exception(
                        "[CELERY] forum_host: failed to enqueue email for event=%s user=%s",
                        event,
                        recipient.pk,
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

                mentioned = resolve_mentioned_users(
                    post,
                    exclude_pks=({post_author.pk} if post_author is not None else ()),
                )
                mentioned_pks = {user.pk for user in mentioned}

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
                subs = subs.exclude(user_id__in=mentioned_pks)
                reply_recipients = [sub.user for sub in subs]

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
            logger.exception(
                "[CELERY] forum_host: failed to enqueue push for event=%s user=%s",
                event,
                author.pk,
            )

    elif event == "topic_created":
        post = kwargs.get("post")
        author = getattr(topic, "author", None)

        from wagtail_forum.mentions import resolve_mentioned_users
        from wagtail_forum.models import NotificationVerb, TopicRead, TopicSubscription
        from wagtail_forum.notifications import create_notifications

        payload = _build_payload(post)

        def _enqueue_mention_push():
            _enqueue_mention_push_for(mentioned, payload)

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
                        "forum.topic_created topic=%s (no author to auto-subscribe)",
                        topic_id,
                    )

                # Opening-post mentions (todo 253 slice 4, H4) — reply_added
                # only ever sees replies, so a mention in a new topic's very
                # first post needs its own handling here. `post` is None for
                # an admin-created topic with no opening post.
                mentioned = (
                    resolve_mentioned_users(
                        post, exclude_pks={author.pk} if author is not None else ()
                    )
                    if post is not None
                    else []
                )
                create_notifications(
                    recipients=mentioned,
                    verb=NotificationVerb.MENTION,
                    actor=author,
                    topic=topic,
                    post=post,
                )
            transaction.on_commit(_enqueue_mention_push)
        except Exception:
            logger.exception(
                "[ERROR] forum_host: failed to process topic_created topic=%s",
                topic_id,
            )

    else:
        logger.warning("forum_host.notifications: unknown event %r", event)
