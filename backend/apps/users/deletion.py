"""Account deletion helpers (Plan B).

Task 1: blocked re-sign-up. Task 3: erasing a deleted account's Django, forum
and email data in resumable steps (``erase_django_data``).
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable, Iterable
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from apps.core.email_feedback import address_hash
from apps.core.firebase_config import get_firestore_client, initialize_firebase
from auditlog import get_logentry_model
from auditlog.context import disable_auditlog
from auditlog.registry import auditlog
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import router, transaction
from django.db.models import Exists, OuterRef, QuerySet
from django.db.models.deletion import Collector
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from .account_links import revoke_refresh_tokens
from .avatars import avatar_file_names, delete_avatar_files_on_commit
from .constants import (
    ACCOUNT_DELETED_EMAIL_SUBJECT,
    DELETED_ACCOUNT_STATUS_DONE,
    DELETED_ACCOUNT_STATUS_PENDING,
    DELETED_TOPIC_TITLE,
    ERASE_FORUM_POST_CHUNK_SIZE,
    ERASE_LOGENTRY_CHUNK_SIZE,
    ERASE_STEP_DJANGO,
    ERASE_STEP_EMAIL,
    ERASE_STEP_FIREBASE_AUTH,
    ERASE_STEP_FIRESTORE,
    ERASE_STEP_FORUM,
    ERASE_STEP_NOTIFIED,
    FORUM_HELD_POST_DAYS,
    SIGNUP_BLOCKED_CODE,
    SIGNUP_BLOCKED_MESSAGE,
    SIGNUP_BLOCKING_REASONS,
)
from .models import DeletedAccount

if TYPE_CHECKING:
    from rest_framework.request import Request
    from wagtail_forum.models import Post

    from .models import User

logger = logging.getLogger(__name__)


class SignupBlocked(Exception):
    """Raised at an account-create point for an address deleted for abuse/under-13."""


def email_hash(address: str) -> str:
    """The hash ``EmailSuppression`` keys on (one normaliser, not a copy)."""
    return address_hash(address)


def is_deletion_pending_for_firebase_uid(uid: str) -> bool:
    """Whether a pending deletion still holds Firebase ``uid``.

    The token exchange refuses such a uid: between the ``django`` and
    ``firebase_auth`` steps the Firebase login still exists but no account
    does, and a sign-in would otherwise create a fresh account that the
    later steps then wipe.
    """
    if not uid:
        return False
    return DeletedAccount.objects.filter(
        firebase_uid=uid, status=DELETED_ACCOUNT_STATUS_PENDING
    ).exists()


def is_signup_blocked(address: str) -> bool:
    if not address:
        return False
    return DeletedAccount.objects.filter(
        email_hash=email_hash(address), reason__in=SIGNUP_BLOCKING_REASONS
    ).exists()


def signup_blocked_response() -> Response:
    return Response(
        {"error": SIGNUP_BLOCKED_MESSAGE, "code": SIGNUP_BLOCKED_CODE},
        status=status.HTTP_403_FORBIDDEN,
    )


def reject_blocked_signup(view: Callable[..., Any]) -> Callable[..., Any]:
    """Refuse 403 ``signup_blocked`` when the body's ``email`` is blocked.

    Stack it ABOVE ``@require_consent`` so a blocked address gets 403, never
    the 428 that asks it to accept the terms.
    """

    @functools.wraps(view)
    def wrapped(request: Request, *args: Any, **kwargs: Any) -> Any:
        body = request.data if isinstance(request.data, dict) else {}
        email = body.get("email")
        if isinstance(email, str) and is_signup_blocked(email):
            return signup_blocked_response()
        return view(request, *args, **kwargs)

    return wrapped


# --- Requesting a deletion (Plan B task 5) ---------------------------------


class DeletionRefused(Exception):
    """The account cannot be deleted by itself: a staff account, or the author
    of a blog post or blog author page (PROTECT foreign keys). Support has to
    handle it."""


def request_account_deletion(user: User, reason: str) -> DeletedAccount:
    """Deactivate ``user``, revoke its sessions and schedule the erase.

    Idempotent: a second request for an account already pending deletion
    returns the same record and queues nothing. ``delete_account_task`` is
    queued once, after the transaction commits, so the worker always finds
    the record. Raises ``DeletionRefused`` (changing nothing) for staff and
    blog authors, and ``ValueError`` (before any lock) for an unknown
    ``reason``.

    A pending request whose stored reason does not block re-sign-up is
    upgraded when staff now ask for ``abuse`` or ``under_13``; a blocking
    reason is never downgraded.
    """
    from apps.blog.models import BlogAuthorPage, BlogPostPage

    if reason not in dict(DeletedAccount.REASON_CHOICES):
        raise ValueError(f"Unknown account deletion reason: {reason!r}")

    with transaction.atomic():
        locked = get_user_model()._base_manager.select_for_update().get(pk=user.pk)
        pending = DeletedAccount.objects.filter(
            user_id=locked.pk, status=DELETED_ACCOUNT_STATUS_PENDING
        ).first()
        if pending is not None:
            if (
                reason in SIGNUP_BLOCKING_REASONS
                and pending.reason not in SIGNUP_BLOCKING_REASONS
            ):
                pending.reason = reason
                pending.save(update_fields=["reason"])
                logger.info(
                    "[ACCOUNT DELETE] deletion %s upgraded to %s",
                    pending.pk,
                    reason,
                )
            return pending
        if (
            locked.is_staff
            or BlogPostPage.objects.filter(author=locked).exists()
            or BlogAuthorPage.objects.filter(author=locked).exists()
        ):
            raise DeletionRefused()

        locked.is_active = False
        locked.save(update_fields=["is_active"])
        revoke_refresh_tokens(locked)
        record = DeletedAccount.objects.create(
            user_id=locked.pk,
            email=locked.email,
            email_hash=email_hash(locked.email),
            firebase_uid=locked.firebase_uid or "",
            reason=reason,
            policy_version=locked.policy_version_accepted or "",
        )
        record_id = record.pk
        # robust: a broker error at commit must not turn a deletion that did
        # start into a 500. The account is already inactive; the nightly
        # re-queue of stale pending records picks the job up.
        transaction.on_commit(lambda: _queue_deletion(record_id), robust=True)
    user.is_active = False
    logger.info(
        "[ACCOUNT DELETE] deletion %s requested for account %s (%s)",
        record.pk,
        record.user_id,
        reason,
    )
    return record


def _queue_deletion(record_id: int) -> None:
    from .tasks import delete_account_task

    try:
        delete_account_task.delay(record_id)
    except Exception as exc:
        logger.error(
            "[ACCOUNT DELETE] deletion %s could not be queued (%s); the nightly "
            "re-queue will pick it up",
            record_id,
            type(exc).__name__,
        )


def notify_account_deleted(record: DeletedAccount) -> None:
    """Step ``notified``: email the saved address that the deletion is done.

    The address comes from the record, because the ``User`` row is gone by
    now. A send that fails raises, so the step is not recorded and the task
    retries; an address with nothing to send to (none saved, or suppressed
    after a hard bounce) is recorded as skipped and never retried.
    """

    def work(locked: DeletedAccount) -> bool:
        if not locked.email:
            return False
        return _send_account_deleted_email(locked.email)

    _run_erase_step(record, ERASE_STEP_NOTIFIED, work, skipped_note="no address")


def _send_account_deleted_email(address: str) -> bool:
    """Send the "account deleted" email. True if sent, False if the address
    is suppressed; raises on any other failure so the caller retries."""
    from apps.core.services.email_service import EmailOutcome, EmailService

    service = EmailService()
    context = {"site_name": service.site_name}
    text = render_to_string("emails/account_deleted.txt", context)
    html = render_to_string("emails/account_deleted.html", context)
    sent = service.send_transactional_email(
        recipient=address,
        subject=ACCOUNT_DELETED_EMAIL_SUBJECT,
        message=text,
        html_message=html,
    )
    if sent:
        return True
    if service.last_outcome == EmailOutcome.SUPPRESSED:
        return False
    raise RuntimeError("The account-deleted email could not be sent")


def finish_deletion(record: DeletedAccount) -> None:
    """Mark ``record`` done and clear the address and Firebase uid.

    Runs after the ``notified`` step, which needed the address. Only the
    email hash stays (the blocked re-sign-up check keys on it).
    """
    DeletedAccount.objects.filter(
        pk=record.pk, status=DELETED_ACCOUNT_STATUS_PENDING
    ).update(
        status=DELETED_ACCOUNT_STATUS_DONE,
        deleted_at=timezone.now(),
        email="",
        firebase_uid="",
    )


# --- Erasing a deleted account's data (Plan B task 3) ----------------------


def erase_django_data(record: DeletedAccount) -> None:
    """Run the ``forum``, ``email`` and ``django`` erase steps for ``record``.

    Each step runs in its own transaction and is appended to
    ``record.steps_done`` inside it, so a crash resumes at the step that did
    not commit and a finished step is never repeated. If the ``User`` row is
    already gone, every remaining step is recorded as done.

    Everything runs with django-auditlog disabled: ``user.delete()`` and its
    cascades would otherwise write fresh LogEntry rows (carrying the email)
    after the ``email`` step deleted the old ones.
    """
    steps: tuple[tuple[str, Callable[["User"], None]], ...] = (
        (ERASE_STEP_FORUM, _erase_forum),
        (ERASE_STEP_EMAIL, _erase_email),
        (ERASE_STEP_DJANGO, _erase_django),
    )
    user_model = get_user_model()
    with disable_auditlog():
        _erase_forum_posts_in_chunks(record)
        for name, step in steps:

            def work(locked: DeletedAccount, step=step) -> bool:
                user = (
                    user_model._base_manager.select_for_update()
                    .filter(pk=locked.user_id)
                    .first()
                    if locked.user_id is not None
                    else None
                )
                if user is not None:
                    step(user)
                return user is not None

            _run_erase_step(record, name, work, skipped_note="no user row")


def _erase_forum_posts_in_chunks(record: DeletedAccount) -> None:
    """Erase the user's unheld forum posts ``ERASE_FORUM_POST_CHUNK_SIZE`` at
    a time, each chunk in its own committed transaction, before the ``forum``
    step runs.

    A prolific poster's posts cost a revisions delete, a re-index and image
    checks each, which can outlast the task's time limit in one transaction.
    Committed chunks survive a kill, and an erased post has no author, so it
    drops out of the next query: a retry carries on where it stopped. The
    ``forum`` step itself still runs every post that is left (held ones, or
    one written meanwhile), so it is recorded only once all are handled.
    """
    from wagtail_forum.models import Post, Report

    while True:
        with transaction.atomic():
            locked = DeletedAccount.objects.select_for_update().get(pk=record.pk)
            if ERASE_STEP_FORUM in locked.steps_done or locked.user_id is None:
                return
            queued = Report.objects.filter(
                post=OuterRef("pk"), status__in=moderation_queue_statuses()
            )
            chunk = list(
                Post.objects.filter(author_id=locked.user_id)
                .filter(~Exists(queued))
                .order_by("pk")[:ERASE_FORUM_POST_CHUNK_SIZE]
            )
            if not chunk:
                return
            for post in chunk:
                erase_post(post)
        logger.info(
            "[ACCOUNT DELETE] account %s: erased %s forum posts",
            locked.user_id,
            len(chunk),
        )


def _run_erase_step(
    record: DeletedAccount,
    name: str,
    work: Callable[[DeletedAccount], bool],
    *,
    skipped_note: str,
) -> None:
    """Run one resumable erase step and record it in ``steps_done``.

    ``work`` receives the locked ``DeletedAccount`` and returns whether it did
    anything (False is logged as skipped; the step is recorded either way). It
    runs inside the same transaction as the record, so if it or the save
    raises, the step is not recorded and a retry runs it again.
    """
    with transaction.atomic():
        # Decide from the LOCKED row, never the caller's copy: a concurrent
        # run waits here, then sees this step recorded and skips it instead of
        # redoing it and overwriting the list.
        locked = DeletedAccount.objects.select_for_update().get(pk=record.pk)
        if name in locked.steps_done:
            record.steps_done = list(locked.steps_done)
            return
        performed = work(locked)
        done = [*locked.steps_done, name]
        locked.steps_done = done
        locked.save(update_fields=["steps_done"])
    # Only once the step has committed: a failed step or save leaves the
    # caller's record without it.
    record.steps_done = done
    logger.info(
        "[ACCOUNT DELETE] account %s: %s step %s",
        record.user_id,
        name,
        "done" if performed else f"skipped ({skipped_note})",
    )


def erase_firebase_data(record: DeletedAccount) -> None:
    """Run the ``firestore`` and ``firebase_auth`` erase steps for ``record``.

    Recorded exactly like ``erase_django_data``. With no ``firebase_uid`` (a
    web-only account) both steps are recorded without any call. A configured
    Firebase is required otherwise: when it is missing this raises
    ``RuntimeError`` so the task retries and alerts instead of passing
    silently. Both Firebase calls are idempotent, so a retry after a failure
    between the call and the save is safe.
    """
    steps = (
        (ERASE_STEP_FIRESTORE, _erase_firestore),
        (ERASE_STEP_FIREBASE_AUTH, _erase_firebase_auth),
    )
    for name, step in steps:

        def work(locked: DeletedAccount, step=step) -> bool:
            if not locked.firebase_uid:
                return False
            step(locked.firebase_uid)
            return True

        _run_erase_step(record, name, work, skipped_note="no firebase uid")


def _erase_firestore(uid: str) -> None:
    """Step ``firestore``: ``users/<uid>`` and everything beneath it."""
    client = get_firestore_client()
    if client is None:
        raise RuntimeError("Firebase is not configured: cannot erase Firestore data")
    client.recursive_delete(client.collection("users").document(uid))


def _erase_firebase_auth(uid: str) -> None:
    """Step ``firebase_auth``: the Firebase login. Already gone counts as done."""
    from firebase_admin import auth as firebase_auth

    if not initialize_firebase():
        raise RuntimeError("Firebase is not configured: cannot delete the login")
    try:
        firebase_auth.delete_user(uid)
    except firebase_auth.UserNotFoundError:
        pass


def erase_post(post: Post) -> None:
    """Erase one forum post's content, keeping the row in its thread.

    Deletes the Wagtail images its body references that nothing else
    references any more, empties the body, clears the author and the
    ``erase_after`` hold, and deletes the post's revisions. The post is saved
    with a plain ``save()``, which creates no revision.
    """
    from wagtail.images import get_image_model

    image_ids = _body_image_ids(post)
    with transaction.atomic():
        post.revisions.all().delete()
        post.latest_revision = None
        post.live_revision = None
        post.body = []
        post.author = None
        post.erase_after = None
        # Saving refreshes the post's ReferenceIndex rows, so the check below
        # no longer sees this post's own (now removed) image references.
        post.save()
        _delete_unreferenced_images(
            get_image_model().objects.filter(pk__in=image_ids), clear_uploader=False
        )


def _delete_unreferenced_images(images: QuerySet[Any], *, clear_uploader: bool) -> None:
    """Delete each of ``images`` that nothing references any more; keep the
    rest, with ``uploaded_by_user`` cleared when ``clear_uploader`` is set.

    Relies on Wagtail refreshing the ReferenceIndex inside ``save()``. That
    holds under django-tasks' synchronous ImmediateBackend, the project
    default (no ``TASKS`` setting). A queued tasks backend would let the
    index lag behind a save, and this check could then delete an image that
    a just-saved object references.
    """
    from wagtail.models import ReferenceIndex

    for image in images:
        if not ReferenceIndex.get_references_to(image).exists():
            image.delete()
        elif clear_uploader and image.uploaded_by_user_id is not None:
            image.uploaded_by_user = None
            image.save(update_fields=["uploaded_by_user"])


def _body_image_ids(post: Post) -> set[int]:
    """The image pks ``post``'s body references (both image block shapes)."""
    from wagtail_forum.api.sanitize import image_block_pk

    ids = set()
    for raw in post.body.raw_data:
        if raw.get("type") != "image":
            continue
        pk = image_block_pk(raw.get("value"))
        if pk is not None:
            ids.add(pk)
    return ids


def moderation_queue_statuses() -> tuple[str, str]:
    """The report statuses still in the moderation queue (ruling R9): open
    and auto-hidden. A post with such a report is held, not erased; the
    nightly release (``retention.release_held_posts``) reads the same pair."""
    from wagtail_forum.models import Report

    return (Report.OPEN, Report.AUTO_HIDDEN)


def _erase_forum(user: User) -> None:
    """Step ``forum``, while the user row still exists.

    A post with a report still in the moderation queue (open or
    auto-hidden) is held for ``FORUM_HELD_POST_DAYS`` with its body and
    images intact; every other post is erased now. Topics are retitled and
    lose their revisions, the user's uploaded images go (except those a
    held post shows), and notifications the user caused are deleted.
    """
    from wagtail.images import get_image_model
    from wagtail_forum.models import ForumProfile, Notification, Post, Report, Topic

    queued = Report.objects.filter(
        post=OuterRef("pk"), status__in=moderation_queue_statuses()
    )
    held_until = timezone.now() + timedelta(days=FORUM_HELD_POST_DAYS)
    held_image_ids: set[int] = set()
    posts = Post.objects.filter(author=user).annotate(held=Exists(queued))
    for post in posts.order_by("pk"):
        if post.held:
            Post.objects.filter(pk=post.pk).update(erase_after=held_until)
            held_image_ids |= _body_image_ids(post)
        else:
            erase_post(post)

    # The forum avatar must be the user's own upload, and the profile still
    # references it here (the profile goes only with user.delete()), so the
    # sweep below would keep it. Unlink it first, with save() so the
    # ReferenceIndex drops the reference, and the sweep deletes the photo.
    profile = ForumProfile.objects.filter(user=user, avatar__isnull=False).first()
    if profile is not None:
        profile.avatar = None
        profile.save()

    for topic in Topic.objects.filter(author=user).order_by("pk"):
        topic.revisions.all().delete()
        topic.latest_revision = None
        topic.live_revision = None
        topic.title = DELETED_TOPIC_TITLE
        topic.save()

    # The user's own erased posts no longer reference anything (their bodies
    # are empty and re-indexed above), so an upload still referenced now is
    # used by someone else's post or a page: it stays, without an uploader.
    _delete_unreferenced_images(
        get_image_model()
        .objects.filter(uploaded_by_user=user)
        .exclude(pk__in=held_image_ids),
        clear_uploader=True,
    )

    Notification.objects.filter(actor=user).delete()


def _erase_email(user: User) -> None:
    """Step ``email``: mail records, blog views, the audit trail, tokens."""
    from apps.blog.models import BlogNewsletter, BlogPostView
    from apps.core.models import EmailNotification
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

    EmailNotification.objects.filter(user=user).delete()
    if user.email:
        EmailNotification.objects.filter(recipient_email__iexact=user.email).delete()
        BlogNewsletter.objects.filter(email__iexact=user.email).delete()
    BlogPostView.objects.filter(user=user).delete()

    entries = get_logentry_model().objects
    user_type = ContentType.objects.get_for_model(get_user_model())
    # The user row's own history (its object_repr and changes name them).
    _delete_in_chunks(entries.filter(content_type=user_type, object_pk=str(user.pk)))
    # Every row the user is the actor of, on any object: each one stores
    # ``actor_email``.
    _delete_in_chunks(entries.filter(actor=user))

    # SET_NULL would leave the tokens behind with no user
    # (expire_unverified_accounts does the same).
    OutstandingToken.objects.filter(user=user).delete()


def _erase_django(user: User) -> None:
    """Step ``django``: avatar files, push token, then ``user.delete()``."""
    from wagtail_forum.models import ForumProfile, Post, Reaction

    reacted_post_ids = list(
        Reaction.objects.filter(user=user).values_list("post_id", flat=True).distinct()
    )
    delete_avatar_files_on_commit(user, avatar_file_names(user))
    ForumProfile.objects.filter(user=user).update(fcm_token="")
    _delete_owned_audit_rows(user)
    # The cascades remove the rest. Scan photos go through their on-commit
    # post_delete receiver; the garden app's User receivers purge its rows.
    user.delete()
    # Reaction rows cascade without recounting the posts' denormalized counts.
    for post in Post.objects.filter(pk__in=reacted_post_ids).order_by("pk"):
        Reaction.recount(post)


def _delete_owned_audit_rows(user: User) -> None:
    """Delete the LogEntry rows of every audited object ``user.delete()``
    will cascade to (garden beds and plants, saved plants, collections...).

    Uses Django's own deletion ``Collector`` so the set is exactly what the
    cascade deletes, however many hops away. An audited model always lands
    in ``collector.data``, never in ``fast_deletes``: auditlog's
    ``post_delete`` receiver rules out fast deletion.
    """
    collector = Collector(using=router.db_for_write(type(user)))
    collector.collect([user])
    entries = get_logentry_model().objects
    for model, instances in collector.data.items():
        if model is type(user) or not auditlog.contains(model):
            continue
        content_type = ContentType.objects.get_for_model(model)
        pks = [str(obj.pk) for obj in instances]
        for chunk in _chunks(pks):
            _delete_in_chunks(
                entries.filter(content_type=content_type, object_pk__in=chunk)
            )


def _chunks(items: list[str]) -> Iterable[list[str]]:
    for start in range(0, len(items), ERASE_LOGENTRY_CHUNK_SIZE):
        yield items[start : start + ERASE_LOGENTRY_CHUNK_SIZE]


def _delete_in_chunks(queryset: QuerySet[Any]) -> None:
    """Delete ``queryset``'s rows, ``ERASE_LOGENTRY_CHUNK_SIZE`` at a time."""
    model = queryset.model
    queryset = queryset.order_by()
    while True:
        pks = list(queryset.values_list("pk", flat=True)[:ERASE_LOGENTRY_CHUNK_SIZE])
        if not pks:
            return
        model.objects.filter(pk__in=pks).delete()
