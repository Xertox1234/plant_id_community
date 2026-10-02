"""Forum admin pages: reported content and pending content.

Reported content — a Wagtail admin *report* over open ``Report`` rows.

Why a ``ReportView`` and not a bespoke admin view (todo 345): Wagtail's
report framework is the package-safe extension point — it gives the listing,
column sorting, filters, pagination, CSV/XLSX export and the Reports menu
entry for free, with no template of our own to keep in step with admin
upgrades. It is deliberately a *listing*: the action/dismiss mutations stay
on the existing ``Report`` snippet inspect/edit views, which every row links
to, so there is exactly one mutation path.

Permission is the ``Report`` model's own policy — any of add/change/delete/
view on ``wagtail_forum.report``, exactly what the ``Report`` snippet index
and inspect views require — NOT superuser-only (the trust system grants
moderation below superuser, and ``AdminOnlyMenuItem`` would hide the queue
from exactly the people it is for) and NOT ``change_post`` (review of this
slice): every row links into the Report snippet views, so a gate looser than
theirs renders links that bounce, and a queue that shows reported DM
excerpts must not be readable by anyone the Report snippet itself denies.
The host's bootstrapped "Forum Moderators" group holds view/change on
reports for this reason (``forum_host/bootstrap.py``).

It is titled "Reported forum content", not "moderation queue" (todo 423):
the owner read "Forum moderation queue" as the place pending posts wait, and
it never listed them.

Pending content (todo 423) — ``PendingContentView``, one listing of every
topic and post waiting for a moderator, each with an Approve button that
publishes it; for a new topic, the topic and its opening post together. One
row per POST: a topic never runs the moderation workflow itself (the API
routes a new topic's opening post, and publishing that post publishes its
topic), so a new topic is its opening post's row. The page is gated on the
``publish`` permission on Post AND on Topic, the rights Approve exercises
(todo 495: Approve can publish a topic too). Reject is its own POST view
(``RejectPendingView``) that re-checks the row under a lock before it
deletes, and needs ``delete`` on whatever it deletes.

Moderators are NOT notified when content is waiting (owner decision
2026-09-28, todo 423): no push, no email. The dashboard's pending count and
this page are the signal, which is why both read the same queryset
(``pending_posts``) and the count links here.
"""

import datetime
import json
import logging
from types import SimpleNamespace

import django_filters
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import (
    Case,
    CharField,
    Count,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    When,
)
from django.db.models.functions import Cast
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.http import urlencode
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views import View
from wagtail.actions import action_registry
from wagtail.admin.filters import WagtailFilterSet
from wagtail.admin.menu import MenuItem
from wagtail.admin.ui.tables import Column, DateColumn, TitleColumn
from wagtail.admin.views.generic.base import WagtailAdminTemplateMixin
from wagtail.admin.views.reports import ReportView
from wagtail.models import Revision, TaskState, WorkflowState
from wagtail.permission_policies import ModelPermissionPolicy

from .models import Post, Report, Topic, TrustLevel

logger = logging.getLogger("wagtail_forum")

# The two statuses that still need a human: OPEN is untouched, AUTO_HIDDEN
# crossed REPORT_AUTO_HIDE_THRESHOLD and was unpublished by the system but a
# moderator still has to decide (restore or action). ACTIONED/DISMISSED are
# done and belong in the full snippet listing, not the queue.
QUEUE_STATUSES = (Report.OPEN, Report.AUTO_HIDDEN)

# The Report snippet's default policy and its index/inspect views' own
# `any_permission_required` list (wagtail/admin/views/generic/models.py) —
# the queue is a view over the same rows, so it opens for the same people.
queue_permission_policy = ModelPermissionPolicy(Report)
QUEUE_PERMISSIONS = ["add", "change", "delete", "view"]


def user_can_view_queue(user):
    return queue_permission_policy.user_has_any_permission(user, QUEUE_PERMISSIONS)


def _inspect_url(report):
    # Resolved, never hardcoded: the admin mount (/cms/ here) is host config
    # and this package is reusable (audit 2026-07-17 M1).
    return reverse(Report.snippet_viewset.get_url_name("inspect"), args=[report.pk])


def _trust_level_label(level):
    """Decode the `reporter_trust_level` annotation (int or None) for both
    the on-screen column and the CSV/XLSX export, so the download does not
    show a bare digit where the screen shows "Regular"."""
    return "" if level is None else TrustLevel(level).label


def _trust_label(report):
    return _trust_level_label(report.reporter_trust_level)


class ModerationQueueFilterSet(WagtailFilterSet):
    reason = django_filters.ChoiceFilter(
        choices=Report.REASON_CHOICES, label=_("Reason")
    )
    # Explicit two-choice filter: Wagtail's auto-generated one would offer
    # ACTIONED/DISMISSED too, which the queue never contains.
    status = django_filters.ChoiceFilter(
        choices=[
            (status, label)
            for status, label in Report.STATUS_CHOICES
            if status in QUEUE_STATUSES
        ],
        label=_("Status"),
    )

    class Meta:
        model = Report
        fields = ["reason", "status"]


class ModerationQueueView(ReportView):
    page_title = _("Reported forum content")
    header_icon = "warning"
    index_url_name = "wagtail_forum_reports:moderation_queue"
    index_results_url_name = "wagtail_forum_reports:moderation_queue_results"
    filterset_class = ModerationQueueFilterSet
    permission_policy = queue_permission_policy
    any_permission_required = QUEUE_PERMISSIONS
    # Oldest first: the queue is a backlog, and the report nobody has looked
    # at for longest is the one to open next.
    default_ordering = "created_at"
    columns = [
        TitleColumn(
            "target_excerpt", label=_("Reported content"), get_url=_inspect_url
        ),
        Column(
            "reason",
            label=_("Reason"),
            accessor=lambda r: r.get_reason_display(),
            sort_key="reason",
        ),
        Column(
            "status",
            label=_("Status"),
            accessor=lambda r: r.get_status_display(),
            sort_key="status",
        ),
        # A plain username column, not UserColumn: the avatar cell resolves
        # `user.wagtail_userprofile` per row, which is one query per report
        # and would make the listing's query count scale with its length.
        Column(
            "reporter",
            label=_("Reporter"),
            accessor=lambda r: r.reporter.get_username(),
        ),
        Column(
            "reporter_trust_level", label=_("Reporter trust"), accessor=_trust_label
        ),
        Column(
            "target_open_reports",
            label=_("Open reports on target"),
            sort_key="target_open_reports",
        ),
        DateColumn("created_at", label=_("Reported"), sort_key="created_at"),
    ]
    list_export = [
        "id",
        "status",
        "reason",
        "detail",
        "target_excerpt",
        "reporter",
        "reporter_trust_level",
        "target_open_reports",
        "created_at",
    ]
    custom_field_preprocess = {
        "reporter_trust_level": {
            "csv": _trust_level_label,
            "xlsx": _trust_level_label,
        }
    }
    export_headings = {
        "id": _("ID"),
        "status": _("Status"),
        "reason": _("Reason"),
        "detail": _("Detail"),
        "target_excerpt": _("Reported content"),
        "reporter": _("Reporter"),
        "reporter_trust_level": _("Reporter trust level"),
        "target_open_reports": _("Open reports on target"),
        "created_at": _("Reported"),
    }

    @cached_property
    def no_results_message(self):
        # Keep the base class's filtered-vs-empty distinction (review of
        # this slice): a moderator who filtered the queue down to nothing
        # should not read that as "nothing is waiting".
        if self.is_searching or self.is_filtering:
            return _("No reports match your filters.")
        return _("No reports are waiting for moderation.")

    def get_filename(self):
        return "forum-moderation-queue-{}".format(
            datetime.date.today().strftime("%Y-%m-%d")
        )

    def order_queryset(self, queryset):
        # Deterministic tie-break (docs/rules/database.md): the base class
        # compiles the chosen column to a bare order_by, and two reports
        # filed in the same instant (a bulk flag, one request filing several)
        # would otherwise flip between pages of the 50-row pagination.
        ordering = self.ordering
        if not ordering:
            return queryset
        if not isinstance(ordering, (list, tuple)):
            ordering = (ordering,)
        return queryset.order_by(*ordering, "pk")

    def get_queryset(self):
        # "How many people flagged this same thing?" per row, as one
        # correlated subquery per target shape rather than a query per row.
        # A report has exactly one of post/message (forum_report_exactly_one_
        # target), so the CASE picks whichever side is populated.
        open_on_post = (
            Report.objects.filter(post=OuterRef("post"), status__in=QUEUE_STATUSES)
            .order_by()
            .values("post")
            .annotate(n=Count("pk"))
            .values("n")
        )
        open_on_message = (
            Report.objects.filter(
                message=OuterRef("message"), status__in=QUEUE_STATUSES
            )
            .order_by()
            .values("message")
            .annotate(n=Count("pk"))
            .values("n")
        )
        self.queryset = (
            Report.objects.filter(status__in=QUEUE_STATUSES)
            .select_related(
                "post",
                "post__topic",  # target_excerpt prefixes the topic title
                "message",
                "message__sender",  # message_summary
                "reporter",
            )
            .annotate(
                # LEFT JOIN: a reporter who has never written (no
                # ForumProfile row yet) still lists, with a blank level.
                reporter_trust_level=F("reporter__wagtail_forum_profile__trust_level"),
                target_open_reports=Case(
                    When(post__isnull=False, then=Subquery(open_on_post)),
                    default=Subquery(open_on_message),
                    output_field=IntegerField(),
                ),
            )
        )
        return super().get_queryset()


class ModerationQueueMenuItem(MenuItem):
    def is_shown(self, request):
        return user_can_view_queue(request.user)


# --- Pending content (todo 423) --------------------------------------------

pending_permission_policy = ModelPermissionPolicy(Post)
topic_permission_policy = ModelPermissionPolicy(Topic)
PENDING_PERMISSION = "publish"

KIND_NEW_TOPIC = _("New topic")
KIND_OPENING_POST = _("Opening post")
KIND_REPLY = _("Reply")
KIND_EDIT = _("Edit")


def user_can_moderate_pending(user):
    """Approve publishes a post and, for an opening post, its topic, so the
    page opens for whoever may publish both: superusers and the host's forum
    moderator group (``publish_post`` and ``publish_topic``). ``publish_post``
    alone is not enough (todo 495): Approve publishes the topic with
    ``skip_permission_checks``, so it would publish topics for a user the
    host never let publish one."""
    return pending_permission_policy.user_has_permission(
        user, PENDING_PERMISSION
    ) and topic_permission_policy.user_has_permission(user, PENDING_PERMISSION)


def _taken_down(obj):
    """Published once and no longer live: a moderator's take-down, an author
    delete, or a reports auto-hide."""
    return not obj.live and obj.first_published_at is not None


def _topic_pending(topic):
    return not topic.live and topic.first_published_at is None


def pending_posts():
    """Every post waiting for a moderator. The one definition the pending
    page, its Approve and Reject actions and the dashboard count all share.

    - A post that was never published and is still a draft: a new topic's
      opening post or a reply that the spam check held. This also covers a
      post whose moderation step crashed or found no workflow (fail closed),
      which has no workflow state at all, the case the old state-only
      dashboard count missed.
    - The opening post of a topic that was never published, even when the
      post itself is live: the thread is still invisible (todo 422's repair
      case), and approving the row publishes the topic.
    - A post with an active workflow state: a live post whose edit the spam
      check held (the live row keeps its approved body).
    - A live post with unpublished changes and no state (todo 495): an edit
      whose moderation step crashed. The workflow start is atomic, so the
      crash rolls its state back, and the API still tells the author the edit
      is pending. Only while the latest revision is the author's own and no
      workflow ever ran on it (todo 499): a moderator's "Save draft" on the
      post's edit view leaves the same state, and so does a cancelled
      workflow, and one Approve would publish that work in progress as the
      author's, past trust and spam routing. A crash leaves neither mark: the
      API saves the revision as the author, and the rollback takes the
      workflow's task state with it. A moderator's own API edit that crashed
      is not listed either; it is theirs to publish from the edit view.

    A live topic's own held edit (a spam-held admin retitle, say) is not a
    row (owner decision 2026-09-29, todo 495): a row shows a post, so Approve
    would publish topic text the moderator never saw. It stays a draft
    revision on the topic's own edit page.

    An edit to a post that was published once is not pending while its topic
    is taken down (todo 495): Approve would publish it into the hidden
    thread, and Reject cannot delete published content. It is listed again
    if the topic is restored. A never-published reply there stays listed,
    with Reject only (``_approve_allowed``). A never-published opening post
    there is not listed either (todo 499, owner decision 2026-10-02): it
    could not be approved into the hidden thread, and its Reject would have
    to delete a topic that was published, so the row was one nobody could
    act on, holding the dashboard count up. It is listed again, as an
    opening post, if the topic is restored.

    A post that was published once and is no longer live is never pending,
    whatever else holds: a moderator took it down, the author deleted it, or
    reports auto-hid it. That holds even when it still has an active workflow
    state. A held edit leaves a NEEDS_CHANGES state, and Wagtail's
    ``UnpublishAction`` does not cancel it, so without this exclusion the post
    would stay listed as an "Edit" and one Approve would publish the held
    revision, bringing back content someone removed. The edit path never
    starts a new state on a post that is not live
    (``submit_edit_for_moderation`` leaves that edit as a draft revision), so
    the only states such a post can carry predate its take-down.
    """
    post_type = ContentType.objects.get_for_model(Post)
    post_state = WorkflowState.objects.active().filter(
        content_type=post_type, object_id=Cast(OuterRef("pk"), CharField())
    )
    authors_revision = Revision.objects.filter(
        pk=OuterRef("latest_revision_id"), user_id=OuterRef("author_id")
    )
    screened = TaskState.objects.filter(revision_id=OuterRef("latest_revision_id"))
    taken_down = Q(live=False, first_published_at__isnull=False)
    topic_taken_down = Q(topic__live=False, topic__first_published_at__isnull=False)
    return Post.objects.filter(
        (
            Q(live=False, first_published_at__isnull=True)
            | Q(
                is_opening_post=True,
                topic__live=False,
                topic__first_published_at__isnull=True,
            )
            | Exists(post_state)
            | (
                Q(live=True, has_unpublished_changes=True)
                & Exists(authors_revision)
                & ~Exists(screened)
            )
        )
        & ~taken_down
        & ~(
            (Q(first_published_at__isnull=False) | Q(is_opening_post=True))
            & topic_taken_down
        )
    )


def _pending_kind(post):
    if post.is_opening_post and _topic_pending(post.topic):
        return KIND_NEW_TOPIC
    if post.first_published_at is None:
        # A draft opening post under a topic that went live another way
        # (published from the admin) is not a new topic (todo 495).
        return KIND_OPENING_POST if post.is_opening_post else KIND_REPLY
    return KIND_EDIT


def _approve_allowed(post):
    """False for any row whose topic was taken down (todo 495): Approve would
    publish it into the hidden topic and notify subscribers with a link that
    404s. Only a never-published reply is listed there (``pending_posts``,
    which leaves out a draft opening post too since todo 499), and it keeps
    Reject, so a moderator still clears it."""
    return not _taken_down(post.topic)


def _reject_target(post):
    """What Reject deletes, or None when it must not offer one.

    A topic only while the topic itself is still pending: its delete removes
    the thread and every reply, so it must never reach a live topic (an
    opening post can still be a draft under a topic that went live another
    way, for example published from the admin by a different author). A
    never-published reply is deleted on its own. A held edit, or an opening
    post whose topic is live, gets no Reject: deleting either would take
    published content down, so the moderator opens it from the title link."""
    if post.is_opening_post:
        return post.topic if _topic_pending(post.topic) else None
    return post if post.first_published_at is None else None


def _user_can_reject(user, target):
    """Reject deletes, so it needs the same ``delete`` permission the snippet
    delete view it replaced required."""
    return ModelPermissionPolicy(type(target)).user_has_permission(user, "delete")


def _pending_body(post):
    """The body waiting for approval: the latest revision's, not the row's.
    An edit to a live post exists only as a revision (the live row keeps its
    approved body), so the row would show the moderator the wrong text.

    None when the revision's body cannot be read (todo 495): falling back to
    the row would show the approved text as if it were the pending one."""
    revision = post.latest_revision
    if revision is None or "body" not in revision.content:
        return post.body
    raw = revision.content["body"]
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = None
    if isinstance(raw, list):
        # plain_text_excerpt reads only .raw_data.
        return SimpleNamespace(raw_data=raw)
    logger.warning(
        "[MODERATION] wagtail_forum pending post %s: revision %s body is unreadable",
        post.pk,
        revision.pk,
    )
    return None


def _pending_excerpt(post):
    # Lazy: api.views imports the models this module's callers import.
    from .api.views import plain_text_excerpt

    body = _pending_body(post)
    if body is None:
        return gettext("(the pending text could not be read)")
    return plain_text_excerpt(body, 120) or gettext("(no text)")


def _post_edit_url(post):
    return reverse(Post.snippet_viewset.get_url_name("edit"), args=[post.pk])


def _author_name(post):
    if post.author is None:
        return gettext("(deleted account)")
    return post.author.get_username()


def _author_trust(post):
    return _trust_level_label(post.author_trust_level)


def approve_pending_post(post, user):
    """Publish a pending post as ``user``. For a new topic, publish the topic
    and its opening post together.

    What goes live is the latest revision, never a fresh copy of the row: a
    held edit exists only as a revision (todo 432). Publishing cancels the
    post's active workflow state (``WAGTAIL_WORKFLOW_CANCEL_ON_PUBLISH``), so
    the row leaves the queue and the dashboard count drops. The revision's
    snapshot of ``reaction_counts`` does not go live: every publish keeps the
    live row's counts (``Post.with_content_json``, todo 499), so a reaction
    added while the edit waited survives.

    The post is published when it is not live, when it has unpublished
    changes, or when it has an active workflow state. The last covers a live
    post whose state has nothing unpublished behind it, a workflow started
    on the live revision itself (todo 499): publishing that revision again is
    what cancels the state, so without it the row could never leave the
    queue.

    A live post with nothing pending of its own (a live opening post listed
    because its topic was never published) is not republished (todo 495): its
    latest revision can be older than the row, and only the topic is waiting.

    The opening post going live already publishes its topic through the
    ``published`` receiver, but only for the same author: that is the IDOR
    guard an API author must not get around. Here a moderator is approving
    the thread, so a topic still unpublished afterwards is published too,
    from its row: the title the page showed. A topic that was published
    once is never published here, so neither a taken-down thread nor a live
    topic's own held edit goes live from this page (owner decision
    2026-09-29, todo 495). ``skip_permission_checks``: the caller has
    checked ``publish`` on Post and Topic, and approving the thread is that
    decision.
    """
    with transaction.atomic():
        if (
            not post.live
            or post.has_unpublished_changes
            or post.current_workflow_state is not None
        ):
            revision = post.latest_revision or post.save_revision(user=user)
            revision.publish(user=user, skip_permission_checks=True)
        if post.is_opening_post:
            topic = Topic.objects.select_for_update().get(pk=post.topic_id)
            if _topic_pending(topic):
                topic.save_revision(user=user).publish(
                    user=user, skip_permission_checks=True
                )


def _pending_index_url():
    return reverse("wagtail_forum_pending:index")


def _already_decided(request):
    messages.info(
        request,
        gettext(
            "That content was already decided, changed or removed. "
            "Nothing was published or deleted."
        ),
    )
    return redirect("wagtail_forum_pending:index")


def _changed_since_loaded(request, post):
    messages.warning(
        request,
        gettext("“%(title)s” changed after this page loaded. Review it again.")
        % {"title": post.topic.title},
    )
    return redirect("wagtail_forum_pending:index")


def _no_reject(request, post):
    """A row still pending that offers no Reject (``_reject_target``): a held
    edit, or an opening post whose topic is live (todo 499)."""
    messages.warning(
        request,
        gettext(
            "“%(title)s” has no Reject: deleting it would take published "
            "content down. Open it from its title link instead."
        )
        % {"title": post.topic.title},
    )
    return redirect("wagtail_forum_pending:index")


def _revision_missing(request):
    """A Reject request that names no revision at all: not one the pending
    page made, which always sends the revision its row showed (todo 499)."""
    messages.warning(
        request,
        gettext(
            "That Reject request did not name the revision it was for, so "
            "nothing was deleted. Use Reject on the pending page."
        ),
    )
    return redirect("wagtail_forum_pending:index")


def _shown_revision(post):
    return str(post.latest_revision_id or "")


def _lock_pending_post(pk, *, whole_thread=False):
    """Lock the post row, then its topic's, and only then look the post up in
    ``pending_posts()`` as its own query, so the lookup sees whatever a
    concurrent Approve or Reject (a double-click, a second moderator)
    committed. Approve and Reject both lock in this order. None when the post
    is gone or no longer pending. Call inside ``transaction.atomic()``.

    Post before topic is also the order of every other write: an API edit,
    an API delete and a reports auto-hide lock the post, then update the
    topic's counters. The one write that runs the other way is a topic's
    delete, which deletes every post in the thread after the topic row is
    already held. So Reject passes ``whole_thread``, and for an opening post,
    whose Reject may delete its topic, every post in the thread is locked in
    pk order before the topic (todo 499). An Approve or Reject of a reply in
    that thread then waits on its post instead of holding it while it waits
    for the topic, which is the deadlock the cascade otherwise sets up.
    Taking the topic first instead would only move that deadlock onto the
    API paths above. An opening post under a live topic has no Reject, so
    only a hand-made request locks a live thread here, and only for this
    transaction."""
    locked = Post.objects.select_for_update().filter(pk=pk).first()
    if locked is None:
        return None
    if whole_thread and locked.is_opening_post:
        list(
            Post.objects.select_for_update()
            .filter(topic_id=locked.topic_id)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
    Topic.objects.select_for_update().filter(pk=locked.topic_id).first()
    return (
        pending_posts().select_related("topic", "latest_revision").filter(pk=pk).first()
    )


class PendingActionsColumn(Column):
    """Approve (a POST form carrying the revision the row shows), unless
    ``_approve_allowed`` refuses it, and, where ``_reject_target`` allows one
    and the user may delete it, Reject: ``RejectPendingView``'s confirmation
    page, carrying the same revision. Both return to the pending page."""

    cell_template_name = "wagtail_forum/admin/pending_queue_actions.html"

    def get_cell_context_data(self, instance, parent_context):
        context = super().get_cell_context_data(instance, parent_context)
        request = parent_context.get("request")
        # Cell templates render from a plain dict, not a RequestContext, so
        # {% csrf_token %} needs the token handed over explicitly.
        context["csrf_token"] = get_token(request) if request is not None else ""
        # The revision this row shows: Approve and Reject act only on that one.
        context["revision_id"] = _shown_revision(instance)
        context["approve_url"] = None
        if _approve_allowed(instance):
            context["approve_url"] = reverse(
                "wagtail_forum_pending:approve", args=[instance.pk]
            )
        context["reject_url"] = None
        target = _reject_target(instance)
        if (
            target is not None
            and request is not None
            and _user_can_reject(request.user, target)
        ):
            reject_url = reverse("wagtail_forum_pending:reject", args=[instance.pk])
            query = urlencode({"revision": context["revision_id"]})
            context["reject_url"] = f"{reject_url}?{query}"
        return context


class PendingContentView(ReportView):
    page_title = _("Pending forum content")
    header_icon = "doc-empty-inverse"
    index_url_name = "wagtail_forum_pending:index"
    index_results_url_name = "wagtail_forum_pending:results"
    # Oldest first: the post that has waited longest is the one to open next.
    default_ordering = "submitted_at"
    columns = [
        TitleColumn(
            "excerpt",
            label=_("Pending content"),
            accessor=_pending_excerpt,
            get_url=_post_edit_url,
        ),
        Column("kind", label=_("Kind"), accessor=_pending_kind),
        Column("topic", label=_("Topic"), accessor=lambda p: p.topic.title),
        Column("author", label=_("Author"), accessor=_author_name),
        Column("author_trust_level", label=_("Author trust"), accessor=_author_trust),
        DateColumn("submitted_at", label=_("Submitted"), sort_key="submitted_at"),
        PendingActionsColumn("actions", label=_("Actions")),
    ]

    def dispatch(self, request, *args, **kwargs):
        # The page's only gate: publish on Post AND on Topic. A report view's
        # permission_policy / permission_required pair names one model, so
        # this view sets neither rather than carry a Post-only check that
        # reads as the gate and is not (todo 499).
        if not user_can_moderate_pending(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def no_results_message(self):
        return _("No forum content is waiting for moderation.")

    def order_queryset(self, queryset):
        # Deterministic tie-break, as in ModerationQueueView.
        ordering = self.ordering
        if not ordering:
            return queryset
        if not isinstance(ordering, (list, tuple)):
            ordering = (ordering,)
        return queryset.order_by(*ordering, "pk")

    def get_queryset(self):
        self.queryset = (
            pending_posts()
            .select_related("topic", "author", "latest_revision")
            .annotate(
                # LEFT JOIN: an author with no ForumProfile row lists blank.
                author_trust_level=F("author__wagtail_forum_profile__trust_level"),
                submitted_at=F("latest_revision__created_at"),
            )
        )
        return super().get_queryset()


class ApprovePendingView(View):
    """POST only: publish one pending post, and its topic for a new topic.

    The lookup goes through ``pending_posts()``, so a stale form for content
    that was already decided publishes nothing. It returns to the pending
    page with an "already decided" message rather than a 404 (todo 495): a
    double-click is the usual cause.

    The form carries the revision its row showed, and Approve publishes only
    that one. An author can edit a held post again after the page loaded,
    and the moderator must not publish text they never saw. The post row is
    locked first, and the pending lookup runs after the lock as its own query
    (``_lock_pending_post``), so it sees whatever a concurrent approval (a
    double-click, a second moderator) committed: that one publishes nothing
    instead of publishing twice."""

    http_method_names = ["post"]

    def post(self, request, pk):
        if not user_can_moderate_pending(request.user):
            raise PermissionDenied
        with transaction.atomic():
            post = _lock_pending_post(pk)
            if post is None:
                return _already_decided(request)
            if not _approve_allowed(post):
                messages.warning(
                    request,
                    gettext(
                        "“%(title)s” was taken down, so a reply to it cannot be "
                        "approved. Reject it instead."
                    )
                    % {"title": post.topic.title},
                )
                return redirect("wagtail_forum_pending:index")
            if request.POST.get("revision") != _shown_revision(post):
                return _changed_since_loaded(request, post)
            approve_pending_post(post, request.user)
        messages.success(
            request, gettext("Published “%(title)s”.") % {"title": post.topic.title}
        )
        return redirect("wagtail_forum_pending:index")


class RejectPendingView(WagtailAdminTemplateMixin, View):
    """Reject one pending row (todo 495): GET is the confirmation page, POST
    deletes.

    It replaced a link to Wagtail's generic snippet delete view, which
    re-checked nothing between page load and confirmation: if another
    moderator approved the topic in between, it hard-deleted a now-live
    thread and all its replies. And its confirmation form posted without
    ``next``, so a real Reject landed on the snippet index. Here the POST, like
    Approve, locks the row, re-runs ``pending_posts()`` and ``_reject_target()``
    and compares the revision the row showed before it deletes anything, and
    every outcome returns to the pending page. The delete itself is the
    model's registered delete action, so it is logged as ``wagtail.delete``
    like the snippet view's."""

    http_method_names = ["get", "post"]
    template_name = "wagtail_forum/admin/pending_reject_confirm.html"
    page_title = _("Reject pending content")
    header_icon = "bin"

    def get_breadcrumbs_items(self):
        return self.breadcrumbs_items + [
            {"url": _pending_index_url(), "label": PendingContentView.page_title},
            {"url": "", "label": self.get_page_title()},
        ]

    def get(self, request, pk):
        if not user_can_moderate_pending(request.user):
            raise PermissionDenied
        post = (
            pending_posts()
            .select_related("topic", "latest_revision")
            .filter(pk=pk)
            .first()
        )
        if post is None:
            return _already_decided(request)
        target = _reject_target(post)
        if target is None:
            return _no_reject(request, post)
        if not _user_can_reject(request.user, target):
            raise PermissionDenied
        revision = request.GET.get("revision")
        if revision is None:
            return _revision_missing(request)
        if revision != _shown_revision(post):
            return _changed_since_loaded(request, post)
        is_topic = isinstance(target, Topic)
        context = self.get_context_data(
            topic_title=post.topic.title,
            excerpt=_pending_excerpt(post),
            is_topic=is_topic,
            post_count=target.posts.count() if is_topic else 1,
            revision=revision,
            reject_url=reverse("wagtail_forum_pending:reject", args=[post.pk]),
            cancel_url=_pending_index_url(),
        )
        return self.render_to_response(context)

    def post(self, request, pk):
        if not user_can_moderate_pending(request.user):
            raise PermissionDenied
        with transaction.atomic():
            post = _lock_pending_post(pk, whole_thread=True)
            if post is None:
                return _already_decided(request)
            target = _reject_target(post)
            if target is None:
                return _no_reject(request, post)
            if not _user_can_reject(request.user, target):
                raise PermissionDenied
            revision = request.POST.get("revision")
            if revision is None:
                return _revision_missing(request)
            if revision != _shown_revision(post):
                return _changed_since_loaded(request, post)
            title = post.topic.title
            # Permission checked above, as the generic delete view does.
            action_registry.get_action_class(type(target), "delete")(
                target, user=request.user
            ).execute(skip_permission_checks=True)
        messages.success(request, gettext("Rejected “%(title)s”.") % {"title": title})
        return redirect("wagtail_forum_pending:index")


class PendingContentMenuItem(MenuItem):
    def is_shown(self, request):
        return user_can_moderate_pending(request.user)
