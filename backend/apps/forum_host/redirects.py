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

Scope: **topic** slug/board changes. A *board* page's slug is also part of
every topic path beneath it, and Wagtail's own auto-redirects only cover the
Page ``url_path``; fanning redirects over a board's N topics is a bulk write
that deserves its own design — todo 334.

Reach, honestly stated: the web app resolves topic routes by the leading id
and treats the slug as decorative, so an old link already renders there.
These rows serve (a) a request that reaches this origin — the middleware
answers a Wagtail 404 with a 301 — and (b) a headless client asking
``/api/v2/redirects/find/?html_path=<old>`` (mounted in project ``urls.py``).

Host-side, not in the package: ``wagtail.contrib.redirects`` is a contrib app
a host may not install, and the package must not assume it.
"""

import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from wagtail.contrib.redirects import api as redirects_api
from wagtail.contrib.redirects.models import Redirect

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
    if old is not None:
        setattr(instance, _OLD_PATH_ATTR, old.get_absolute_url())


@receiver(
    post_save,
    sender="wagtail_forum.Topic",
    dispatch_uid="forum_host.redirects.post_save",
)
def redirect_old_path(sender, instance, created, raw=False, **kwargs):
    old_path = getattr(instance, _OLD_PATH_ATTR, None)
    # Gate on the NEW live state: an auto-hidden topic whose slug a moderator
    # fixes on the way back to published still gets its once-public URL
    # redirected; an unpublished topic's path is a 404 either way.
    if raw or created or not old_path or not instance.live:
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


class RedirectsAPIViewSet(redirects_api.RedirectsAPIViewSet):
    """Wagtail's headless redirect lookup, mounted at ``/api/v2/redirects/``
    (project ``urls.py``). ``versioning_class = None`` for the same reason
    every project-owned Wagtail API viewset sets it (apps/blog/api/endpoints.py):
    DRF's NamespaceVersioning otherwise 404s the router's ``wagtailapi``
    namespace as an unknown version. Serves every redirect row, not only the
    forum's — it lives here because the forum is what writes rows
    automatically."""

    versioning_class = None
