"""Topic slug/board changes → Wagtail redirects (Wagtail quick wins, item 2).

``Topic.get_absolute_url`` is ``/forum/{board.id}-{board.slug}/{id}-{slug}``,
so a slug edit *or* a board move changes the public path. This pair of
receivers writes a permanent, all-sites ``wagtail.contrib.redirects`` row from
the old path to the new one, and keeps the redirect table coherent as a topic
keeps moving:

* a rename **back** deletes the auto-created row that would now bounce the
  current path away again (A→B then B→A must not leave A→B — the paths are
  404s on this host, so the middleware would loop the browser);
* a **chain** collapses: rows that sent visitors to the old path are re-pointed
  at the new one (A→B then B→C leaves A→C and B→C, never A→B→C);
* the row itself is "update every existing row for this old path, else
  create one". Not ``update_or_create``: Postgres does not enforce the
  model's ``unique_together(old_path, site)`` when ``site IS NULL`` (Wagtail's
  own RedirectForm de-dupes by hand for the same reason), so a concurrent
  double-insert would make ``.get()`` raise inside every later save.

Scope: topic slug/board changes (the receivers below) and **board slug
renames** (``page_slug_changed`` on ``ForumBoard``, todo 334). A board's slug
is part of every topic path beneath it, and Wagtail's own auto-redirects only
cover the Page ``url_path``, so a rename fans the same three steps over every
live topic as a fixed number of bulk statements — ``redirect_board_topics``.

Reach, honestly stated: the web app resolves topic routes by the leading id
and treats the slug as decorative, so an old link already renders there.
These rows serve (a) a request that reaches this origin — the middleware
answers a Wagtail 404 with a 301 — and (b) a headless client asking
``/api/v2/redirects/find/?html_path=<old>`` (mounted in project ``urls.py``).

Host-side, not in the package: ``wagtail.contrib.redirects`` is a contrib app
a host may not install, and the package must not assume it.
"""

import logging

from django.db import transaction
from django.db.models import F, Q, Value
from django.db.models.functions import Replace
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from wagtail.contrib.redirects import api as redirects_api
from wagtail.contrib.redirects.models import Redirect
from wagtail.signals import page_slug_changed
from wagtail_forum.models import ForumBoard, Topic

from .constants import REDIRECT_BULK_CREATE_BATCH_SIZE

logger = logging.getLogger(__name__)

# Stashed on the instance between pre_save and post_save.
_OLD_PATH_ATTR = "_forum_redirect_old_path"
# Only these fields can move the path; a counters/flags save with an explicit
# update_fields skips the extra SELECT entirely.
_PATH_FIELDS = {"slug", "board", "board_id"}


@receiver(
    pre_save, sender="wagtail_forum.Topic", dispatch_uid="forum_host.redirects.pre_save"
)
def remember_old_path(sender, instance, update_fields=None, raw=False, **kwargs):
    setattr(instance, _OLD_PATH_ATTR, None)
    if raw or instance.pk is None:
        return
    if update_fields is not None and not _PATH_FIELDS.intersection(update_fields):
        return
    old = sender.objects.filter(pk=instance.pk).select_related("board").first()
    # Only a path that was ever public is worth a row: live now, or published
    # at some point — unpublish keeps ``first_published_at`` (it clears
    # ``live_revision``). A never-published draft's path was always a 404.
    if old is not None and (old.live or old.first_published_at is not None):
        setattr(instance, _OLD_PATH_ATTR, old.get_absolute_url())


@receiver(
    post_save,
    sender="wagtail_forum.Topic",
    dispatch_uid="forum_host.redirects.post_save",
)
def redirect_old_path(sender, instance, created, raw=False, **kwargs):
    old_path = getattr(instance, _OLD_PATH_ATTR, None)
    # Deliberately NOT gated on the new ``live`` state (audit 2026-09-04 M1).
    # Since Wagtail 6.0 the admin saves a draft edit of an UNPUBLISHED
    # snippet straight to the row (``form.save(commit=not live)``), and the
    # later publish is a plain ``save()`` whose pre_save snapshot then reads
    # the already-renamed row: waiting for the publish would find old == new
    # and write nothing, leaving the once-public URL a plain 404 — the "hide
    # it, fix the slug, republish it" moderation flow. So the draft save
    # writes the row: it costs nothing (the target 404s until republished,
    # exactly as the old path already does) and it is the only save that
    # still knows the once-public path. The pre_save gate above keeps
    # never-published drafts out.
    if raw or created or not old_path:
        return
    new_path = instance.get_absolute_url()
    if Redirect.normalise_path(old_path) == Redirect.normalise_path(new_path):
        return
    redirect_topic_path(old_path, new_path)


def redirect_topic_path(old_path, new_path):
    """Write ``old_path → new_path`` and keep the table loop- and chain-free.
    Runs inside the caller's transaction (the topic save), so a rolled-back
    save leaves no stray redirect."""
    old_path = Redirect.normalise_path(old_path)
    new_path = Redirect.normalise_path(new_path)
    # Nothing may redirect FROM the path the topic now lives at: our own
    # rename-back row (A→B then B→A) would loop, and a hand-made row from it
    # would either loop with the new A→B or be rewritten into B→B by the chain
    # collapse below. An editor's manual row is removed too, but loudly.
    shadowing = Redirect.objects.filter(old_path=new_path)
    for manual in shadowing.filter(automatically_created=False):
        logger.warning(
            "[ERROR] Removed manual redirect %s -> %s: a forum topic now lives at "
            "%s and the row would loop",
            manual.old_path,
            manual.link,
            new_path,
        )
    shadowing.delete()
    # Chain collapse: whatever sent visitors to the old path sends them on.
    Redirect.objects.filter(redirect_link=old_path).update(redirect_link=new_path)
    # Re-point EVERY existing all-sites row for the old path (see module
    # docstring on NULL-site uniqueness), else create the one row.
    updated = Redirect.objects.filter(old_path=old_path, site=None).update(
        redirect_link=new_path,
        redirect_page=None,
        is_permanent=True,
        automatically_created=True,
    )
    if not updated:
        Redirect.objects.create(
            old_path=old_path,
            site=None,
            redirect_link=new_path,
            is_permanent=True,
            automatically_created=True,
        )


# --- board slug renames (todo 334) -------------------------------------------


def board_topic_prefix(board_id, slug):
    """The path every topic under a board shares: the board half of
    ``Topic.get_absolute_url`` (``/forum/{board.id}-{board.slug}/``). Only the
    prefix-wide chain collapse needs it; per-topic paths come from the model
    method itself. Pinned against that method by the redirect tests."""
    return f"/forum/{board_id}-{slug}/"


@receiver(
    page_slug_changed,
    sender=ForumBoard,
    dispatch_uid="forum_host.redirects.board_slug_changed",
)
def redirect_board_topics_on_slug_change(sender, instance, instance_before, **kwargs):
    # Wagtail sends this from transaction.on_commit with the SPECIFIC page
    # instances, so the board's own save has already committed by now.
    if not isinstance(instance, ForumBoard):
        return
    redirect_board_topics(instance_before, instance)


def redirect_board_topics(board_before, board):
    """Bulk form of :func:`redirect_topic_path` for every LIVE topic under
    ``board``, whose slug moved from ``board_before.slug`` to ``board.slug``.
    The same three steps, each as one statement over the whole set, so the
    admin save costs the same number of queries at 3 topics as at 1,000 (the
    redirect tests pin both); only the INSERT splits past
    ``REDIRECT_BULK_CREATE_BATCH_SIZE`` rows. Wrapped in its own transaction
    because the caller's has already committed: a failure leaves the table as
    it was, never half-moved.

    Never-published drafts get no row (their path is a 404 before and after);
    a once-public topic that is unpublished right now does, for the same
    reason the per-topic receiver writes one while hidden (audit 2026-09-04
    M1): its old path was public and the new one is right the moment it is
    republished. The chain collapse still re-points rows aimed at drafts, by
    prefix, so they are right if the draft is ever published — which is why
    steps 2–2b run even when no topic qualifies (step 1 has nothing to shadow
    then), and why a row the collapse folds onto itself is dropped (2b)."""
    old_prefix = board_topic_prefix(board.pk, board_before.slug)
    new_prefix = board_topic_prefix(board.pk, board.slug)
    if old_prefix == new_prefix:
        return
    live = board.topics.filter(
        Q(live=True) | Q(first_published_at__isnull=False)
    ).values_list("id", "slug")
    pairs = [
        (
            Redirect.normalise_path(
                Topic(board=board_before, id=topic_id, slug=slug).get_absolute_url()
            ),
            Redirect.normalise_path(
                Topic(board=board, id=topic_id, slug=slug).get_absolute_url()
            ),
        )
        for topic_id, slug in live
    ]
    old_paths = [old for old, _ in pairs]
    new_paths = [new for _, new in pairs]
    with transaction.atomic():
        # 1. Nothing may redirect FROM a path a live topic now lives at — the
        #    rename-back's own rows would loop, and step 2 would rewrite a
        #    manual one into a self-loop. Manual rows go too, loudly.
        if pairs:
            shadowing = Redirect.objects.filter(old_path__in=new_paths)
            for manual in shadowing.filter(automatically_created=False):
                logger.warning(
                    "[ERROR] Removed manual redirect %s -> %s: a forum topic now "
                    "lives at %s and the row would loop",
                    manual.old_path,
                    manual.link,
                    manual.old_path,
                )
            shadowing.delete()
        # 2. Chain collapse, by prefix: whatever sent visitors under the old
        #    board path sends them under the new one (A→B then B→C leaves
        #    A→C and B→C). Prefix-wide on purpose: rows aimed at a topic that
        #    is unpublished right now must follow the board too.
        Redirect.objects.filter(redirect_link__startswith=old_prefix).update(
            redirect_link=Replace(
                F("redirect_link"), Value(old_prefix), Value(new_prefix)
            )
        )
        # 2b. A rename BACK folds the row an earlier rename left for a topic
        #     that has since been unpublished (its new path is not in step 1's
        #     live set) onto itself: old_path == redirect_link. A self-loop is
        #     never a valid row, so drop them. (Review round 1, todo 334.)
        Redirect.objects.filter(
            old_path__startswith=new_prefix, redirect_link=F("old_path")
        ).delete()
        if not pairs:
            return
        # 3. One all-sites row per live topic. Update-or-create in bulk is
        #    delete-then-insert: every existing row for an old path (there
        #    can be several — NULL-site uniqueness, see the module docstring)
        #    is replaced by the one row, exactly as the per-topic update does.
        Redirect.objects.filter(old_path__in=old_paths, site=None).delete()
        Redirect.objects.bulk_create(
            [
                Redirect(
                    old_path=old,
                    site=None,
                    redirect_link=new,
                    is_permanent=True,
                    automatically_created=True,
                )
                for old, new in pairs
            ],
            batch_size=REDIRECT_BULK_CREATE_BATCH_SIZE,
            ignore_conflicts=True,
        )


class RedirectsAPIViewSet(redirects_api.RedirectsAPIViewSet):
    """Wagtail's headless redirect lookup, mounted at ``/api/v2/redirects/``
    (project ``urls.py``). ``versioning_class = None`` for the same reason
    every project-owned Wagtail API viewset sets it (apps/blog/api/endpoints.py):
    DRF's NamespaceVersioning otherwise 404s the router's ``wagtailapi``
    namespace as an unknown version. Serves every redirect row, not only the
    forum's — it lives here because the forum is what writes rows
    automatically."""

    versioning_class = None
