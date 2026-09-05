import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_topic_snippet_list_is_reachable_in_admin(client):
    admin = User.objects.create_superuser(username="root", email="r@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/topic/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_post_snippet_list_is_reachable_in_admin(client):
    admin = User.objects.create_superuser(username="root", email="r@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/post/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_profile_snippet_list_is_reachable_in_admin(client):
    # ForumProfileViewSet is registered but its __str__ touches user.get_username();
    # guard the profile list against a silent 500 on a field/relation regression.
    admin = User.objects.create_superuser(username="root", email="r@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/forumprofile/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_report_snippet_list_is_reachable_in_admin(client):
    admin = User.objects.create_superuser(username="root", email="r@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/report/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_report_snippet_list_renders_with_a_message_report_present(client):
    # todo 319/M10: ReportViewSet.list_display gained "message_summary"
    # (a @property) alongside the pre-existing "post" column. Pin that the
    # index view still renders 200 — and shows something readable — with a
    # message report in the queryset, not just the post-report-only case
    # test_report_snippet_list_is_reachable_in_admin already covers.
    from wagtail.models import Page
    from wagtail_forum.models import (
        Conversation,
        ForumBoard,
        ForumIndex,
        Message,
        Post,
        Report,
        Topic,
    )

    admin = User.objects.create_superuser(username="root", email="r@x.io")
    sender = User.objects.create_user(username="sender", email="s@x.io")
    recipient = User.objects.create_user(username="recipient", email="rc@x.io")
    conversation = Conversation.between(sender, recipient)
    message = Message.objects.create(
        conversation=conversation, sender=sender, body="reported dm body"
    )
    Report.objects.create(message=message, reporter=recipient, reason=Report.SPAM)

    # A post report too, so both columns are exercised in the same listing —
    # mirrors test_reports.py's `_post()` helper.
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(board=board, title="T", slug="t", author=sender)
    post = Post.objects.create(topic=topic, author=sender, is_opening_post=True)
    Report.objects.create(post=post, reporter=recipient, reason=Report.ABUSE)

    client.force_login(admin)
    resp = client.get("/cms/snippets/wagtail_forum/report/")

    assert resp.status_code == 200
    assert "sender: reported dm body" in resp.content.decode()


@pytest.mark.django_db
def test_moderation_summary_item_counts_spam_rejected_post(client):
    # The homepage panel's signal is NEEDS_CHANGES content (spam the workflow
    # rejected, left as a draft) — drive a real post through submit_for_moderation
    # rather than hand-constructing a WorkflowState, so this proves the whole
    # chain: reject -> active WorkflowState -> _pending_moderation_count ->
    # homepage summary item (audit H16).
    from wagtail.models import Page
    from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Post, Topic
    from wagtail_forum.wagtail_hooks import _pending_moderation_count
    from wagtail_forum.workflow import ensure_default_workflow, submit_for_moderation

    ensure_default_workflow()
    author = User.objects.create_user(username="spammer")
    ForumProfile.for_user(author)  # trust NEW -- screened, not autopublished

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(board=board, title="T", slug="t", author=author)
    spam = "http://a.com http://b.com http://c.com http://d.com http://e.com"
    post = Post(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": f"<p>{spam}</p>"}],
    )
    post.save()
    status = submit_for_moderation(post, author)
    assert status == "pending"  # sanity: this really did get rejected, not published

    assert _pending_moderation_count() == 1

    admin = User.objects.create_superuser(username="root", email="r@x.io")
    client.force_login(admin)
    resp = client.get("/cms/")

    assert resp.status_code == 200
    assert b"1 Forum post awaiting moderation" in resp.content

    # Audit 2026-07-17 M1: the panel link is resolved via the snippet
    # viewset's URL name, not hardcoded to the /cms/ mount.
    from django.urls import reverse

    expected_url = reverse(Topic.snippet_viewset.get_url_name("list"))
    assert f'href="{expected_url}?live=false"'.encode() in resp.content


@pytest.mark.django_db
def test_forum_search_area_appears_on_admin_pages_search(client):
    # register_admin_search_area hooks render on Wagtail's global Pages search
    # page (wagtailadmin/pages/search_results.html), not on /cms/ itself —
    # SnippetViewSet listings default show_other_searches=False so they don't
    # render it either (audit M20).
    from django.urls import reverse

    admin = User.objects.create_superuser(username="root", email="r@x.io")
    client.force_login(admin)

    resp = client.get(reverse("wagtailadmin_pages:search"), {"q": "anything"})

    assert resp.status_code == 200
    assert b"Forum" in resp.content

    # Audit 2026-07-17 M1: the search area's target is resolved via the
    # snippet viewset's URL name, not hardcoded to the /cms/ mount.
    from wagtail_forum.models import Topic

    expected_url = reverse(Topic.snippet_viewset.get_url_name("list"))
    assert expected_url.encode() in resp.content


@pytest.mark.django_db
def test_post_search_fields_finds_live_post_by_body_text(client):
    from wagtail.models import Page
    from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Post, Topic

    author = User.objects.create_user(username="searchable_author")
    ForumProfile.for_user(author)
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="SForum", slug="sforum"))
    board = index.add_child(instance=ForumBoard(title="SGeneral", slug="sgeneral"))
    topic = Topic.objects.create(board=board, title="ST", slug="st", author=author)
    post = Post(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": "<p>photosynthesis basics</p>"}],
    )
    post.save()
    post.save_revision().publish()

    admin = User.objects.create_superuser(username="root3", email="r3@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/post/?q=photosynthesis")

    assert resp.status_code == 200
    # A rendered ROW, not a substring: `str(post.pk)` matched asset hashes
    # and the CSRF token, so the old assertion passed on "No posts".
    assert b"No posts" not in resp.content
    assert f"/post/edit/{post.pk}/".encode() in resp.content


@pytest.mark.django_db
def test_topic_listing_search_matches_a_title_prefix(client):
    """Pins `index.AutocompleteField("title")` on Topic (todo 276 / audit L8).

    The reader is WAGTAIL, not our code: TopicViewSet is a SnippetViewSet with
    search_fields=["title"], and the generic admin `search_queryset` calls
    `search_backend.autocomplete()` only while
    `Topic.get_autocomplete_search_fields()` is non-empty — otherwise it falls
    back to whole-word `search()` (plus a RuntimeWarning that pytest.ini does
    NOT turn into a failure). So dropping the field silently breaks prefix
    search in the CMS with every test still green.

    A PREFIX query is the whole point: "mons" is not a word in the title, so it
    only matches through the autocomplete path.
    """
    from wagtail.models import Page
    from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Topic

    author = User.objects.create_user(username="topic_search_author")
    ForumProfile.for_user(author)
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="TSForum", slug="tsforum"))
    board = index.add_child(instance=ForumBoard(title="TSGeneral", slug="tsgeneral"))
    topic = Topic.objects.create(
        board=board,
        title="Monstera repotting",
        slug="monstera-repotting",
        author=author,
    )
    topic.save_revision().publish()

    admin = User.objects.create_superuser(username="root_ts", email="rts@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/topic/?q=mons")

    assert resp.status_code == 200
    assert b"Monstera repotting" in resp.content


@pytest.mark.django_db
def test_forum_profile_search_fields_finds_profile_by_username(client):
    from wagtail_forum.models import ForumProfile

    user = User.objects.create_user(username="findme_by_search")
    ForumProfile.for_user(user)

    admin = User.objects.create_superuser(username="root4", email="r4@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/forumprofile/?q=findme_by_search")

    assert resp.status_code == 200
    assert b"findme_by_search" in resp.content


@pytest.mark.django_db
def test_post_preview_renders_pending_revision_body():
    # make_preview_request() is what Wagtail's own moderation UI calls to
    # preview a pending revision (PreviewableMixin docstring: "Used for
    # previewing / moderation") — this is the actual M16 code path, not just
    # the edit page wiring (see test_post_edit_view_reachable_with_preview_
    # enabled for that).
    from wagtail.models import Page
    from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Post, Topic
    from wagtail_forum.workflow import ensure_default_workflow, submit_for_moderation

    ensure_default_workflow()
    author = User.objects.create_user(username="pending_author")
    ForumProfile.for_user(author)  # trust NEW -- screened, not autopublished

    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="PForum", slug="pforum"))
    board = index.add_child(instance=ForumBoard(title="PGeneral", slug="pgeneral"))
    topic = Topic.objects.create(board=board, title="PT", slug="pt", author=author)
    spam = "http://a.com http://b.com http://c.com http://d.com http://e.com"
    post = Post(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": f"<p>{spam}</p>"}],
    )
    post.save()
    status = submit_for_moderation(post, author)
    assert status == "pending"  # sanity: really rejected, not published

    revision_obj = post.get_latest_revision_as_object()
    response = revision_obj.make_preview_request()

    assert response.status_code == 200
    assert b"a.com" in response.content


@pytest.mark.django_db
def test_post_edit_view_reachable_with_preview_enabled(client):
    # PreviewableMixin wiring (SnippetViewSet.preview_enabled auto-detection)
    # doesn't break the ordinary snippet edit page (audit M16).
    from django.urls import reverse
    from wagtail.models import Page
    from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Post, Topic

    author = User.objects.create_user(username="edit_view_author")
    ForumProfile.for_user(author)
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="EForum", slug="eforum"))
    board = index.add_child(instance=ForumBoard(title="EGeneral", slug="egeneral"))
    topic = Topic.objects.create(board=board, title="ET", slug="et", author=author)
    post = Post(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": "<p>hello</p>"}],
    )
    post.save()
    post.save_revision().publish()

    admin = User.objects.create_superuser(username="root5", email="r5@x.io")
    client.force_login(admin)

    from wagtail_forum.models import Post as PostModel

    url = reverse(PostModel.snippet_viewset.get_url_name("edit"), args=(post.pk,))
    resp = client.get(url)

    assert resp.status_code == 200


@pytest.mark.django_db
def test_bulk_unpublish_action_unpublishes_selected_posts(client):
    # Spam-wave cleanup (audit M20): reuses the same UnpublishAction(...)
    # .execute(skip_permission_checks=True) mechanism as the single-object
    # DELETE view, attributed to the acting moderator.
    from django.urls import reverse
    from wagtail.models import ModelLogEntry, Page
    from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Post, Topic

    author = User.objects.create_user(username="bulk_target_author")
    ForumProfile.for_user(author)
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="BForum", slug="bforum"))
    board = index.add_child(instance=ForumBoard(title="BGeneral", slug="bgeneral"))
    topic = Topic.objects.create(board=board, title="BT", slug="bt", author=author)

    posts = []
    for i in range(2):
        p = Post(
            topic=topic,
            author=author,
            is_opening_post=(i == 0),
            body=[{"type": "paragraph", "value": f"<p>spam {i}</p>"}],
        )
        p.save()
        p.save_revision().publish()
        posts.append(p)

    admin = User.objects.create_superuser(username="root6", email="r6@x.io")
    client.force_login(admin)

    url = reverse(
        "wagtail_bulk_action",
        args=("wagtail_forum", "post", "unpublish"),
    )
    query = "&".join(f"id={p.pk}" for p in posts)

    # A real moderator always sees the GET confirmation page before POSTing
    # (the snippet list's "Unpublish" button). Check it too, not just the
    # POST — it renders a distinct template block (titletag) that a POST-only
    # test never touches (kimi-review follow-up: this caught a real
    # {% load %} bug, a missing wagtailadmin_tags for the intcomma filter,
    # that 500'd this exact page for every user, privileged or not).
    confirm_resp = client.get(f"{url}?{query}")
    assert confirm_resp.status_code == 200

    resp = client.post(f"{url}?{query}", data={})

    assert resp.status_code == 302
    for p in posts:
        p.refresh_from_db()
        assert p.live is False

    # get_execution_context() overrides user=self.request.user specifically so
    # takedowns attribute to the acting moderator, not "the system" (todo 265;
    # mirrors test_actor_attribution.py::test_api_delete_unpublish_logs_acting_user).
    entry = (
        ModelLogEntry.objects.filter(
            action="wagtail.unpublish", object_id=str(posts[0].pk)
        )
        .order_by("-timestamp")
        .first()
    )
    assert entry is not None
    assert entry.user == admin


@pytest.mark.django_db
def test_bulk_unpublish_action_execution_context_carries_acting_user():
    """Pins `ForumUnpublishBulkAction.get_execution_context()`'s
    `user=self.request.user` override directly (todo 265).

    The end-to-end `ModelLogEntry` assertion in the test above CANNOT catch
    this override's removal. `wagtail.admin.auth.require_admin_access` wraps
    every admin view in `LogContext(user=request.user)`, and
    `LogActionRegistry.log()` does `user = user or
    get_active_log_context().user` — so a bulk unpublish dispatched through a
    real admin view is attributed to the acting moderator whether or not the
    override exists. The override is load-bearing only against a future caller
    outside that ambient context (the DRF paths pinned by
    test_actor_attribution.py have no LogContext at all).

    Same shape as test_schema.py::test_topic_list_view_guards_schema_generation:
    when an ambient framework fallback supplies the same value, only a direct
    unit test can pin the explicit override. Drop the override and this fails
    with `None != <admin>` (`super()` returns `{"self": self}`, no user key).
    """
    from django.test import RequestFactory
    from wagtail_forum.models import Post
    from wagtail_forum.wagtail_hooks import ForumUnpublishBulkAction

    admin = User.objects.create_superuser(username="ctxroot", email="ctx@x.io")
    request = RequestFactory().post("/cms/bulk/wagtail_forum/post/unpublish/")
    request.user = admin

    action = ForumUnpublishBulkAction(request, Post)

    # .get(), not ["user"]: with the override dropped this must be an
    # unambiguous value mismatch, not a KeyError that could be mistaken for
    # an unrelated crash during mutation verification.
    assert action.get_execution_context().get("user") == admin


@pytest.mark.django_db
def test_bulk_unpublish_action_blocks_user_without_change_permission(client):
    # check_perm gates on wagtail_forum.change_post — a staff user who can
    # reach /cms/ (access_admin) but lacks that specific permission must not
    # be able to unpublish via this action (kimi-review follow-up: the
    # golden-path test alone never proved check_perm actually blocks anyone).
    from django.contrib.auth.models import Permission
    from django.urls import reverse
    from wagtail.models import Page
    from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Post, Topic

    author = User.objects.create_user(username="perm_test_author")
    ForumProfile.for_user(author)
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="PermForum", slug="permforum"))
    board = index.add_child(
        instance=ForumBoard(title="PermGeneral", slug="permgeneral")
    )
    topic = Topic.objects.create(
        board=board, title="PermT", slug="permt", author=author
    )
    post = Post(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": "<p>should stay live</p>"}],
    )
    post.save()
    post.save_revision().publish()

    # access_admin alone (no wagtail_forum.change_post) mirrors that
    # forum_host/bootstrap.py's own "Forum Moderators" group needs BOTH —
    # access_admin just to reach /cms/, change_post to actually moderate.
    staff = User.objects.create_user(username="no_change_perm", is_staff=True)
    staff.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="wagtailadmin", codename="access_admin"
        )
    )
    client.force_login(staff)

    url = reverse("wagtail_bulk_action", args=("wagtail_forum", "post", "unpublish"))

    # GET the confirmation page first: proves check_perm was actually reached
    # and returned False for THIS object (not just "nothing happened", which
    # a negative-only assertion after POST can't distinguish from a broken
    # request that never dispatched at all — kimi-review follow-up).
    confirm_resp = client.get(f"{url}?id={post.pk}")
    assert confirm_resp.status_code == 200
    assert b"You don't have permission to unpublish this post" in confirm_resp.content

    client.post(f"{url}?id={post.pk}", data={})

    post.refresh_from_db()
    assert post.live is True


# --- CSV export + inspect view (Wagtail quick wins, item 4) -------------------
#
# ``list_export`` drives the "Download CSV/XLSX" button on the snippet index;
# ``inspect_view_enabled`` adds a read-only detail page. Pinned here because a
# column that resolves through a nullable FK (a message report has no post)
# would 500 the whole export, and because the headings are what a moderator
# sees in the spreadsheet.


def _admin_client(client):
    client.force_login(User.objects.create_superuser(username="root", email="r@x.io"))
    return client


def _post_report(detail="looks like a bot"):
    from wagtail.models import Page
    from wagtail_forum.models import ForumBoard, ForumIndex, Post, Report, Topic

    author = User.objects.create_user(username="author")
    reporter = User.objects.create_user(username="reporter")
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    topic = Topic.objects.create(
        board=board, title="Seedling help", slug="seedling-help", author=author
    )
    post = Post.objects.create(topic=topic, author=author, is_opening_post=True)
    return Report.file(post, reporter, Report.SPAM, detail=detail)


def _message_report():
    from wagtail_forum.models import Conversation, Message, Report

    sender = User.objects.create_user(username="sender")
    recipient = User.objects.create_user(username="recipient")
    message = Message.objects.create(
        conversation=Conversation.between(sender, recipient), sender=sender, body="hi"
    )
    return Report.objects.create(
        message=message, reporter=recipient, reason=Report.ABUSE
    )


def _csv(resp):
    raw = b"".join(resp.streaming_content) if resp.streaming else resp.content
    return raw.decode("utf-8-sig").splitlines()


REPORT_HEADINGS = [
    "ID",
    "Status",
    "Reason",
    "Detail",
    "Topic",
    "Post",
    "Message",
    "Reporter",
    "Created",
    "Resolved at",
    "Resolved by",
]

TOPIC_HEADINGS = [
    "ID",
    "Title",
    "Board",
    "Author",
    "Live",
    "Pinned",
    "Closed",
    "Replies",
    "Views",
    "Solved post ID",
    "Created",
    "Last post",
]


@pytest.mark.django_db
def test_report_csv_export_has_triage_columns(client):
    report = _post_report()

    resp = _admin_client(client).get("/cms/snippets/wagtail_forum/report/?export=csv")

    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    header, row = _csv(resp)[:2]
    assert header.split(",") == REPORT_HEADINGS
    assert "looks like a bot" in row
    assert "Seedling help" in row
    assert f"Post #{report.post_id}" in row
    assert "reporter" in row


@pytest.mark.django_db
def test_report_csv_export_survives_a_message_report(client):
    _post_report()
    _message_report()

    resp = _admin_client(client).get("/cms/snippets/wagtail_forum/report/?export=csv")

    assert resp.status_code == 200
    rows = _csv(resp)
    assert len(rows) == 3  # header + two reports
    assert any("sender: hi" in r for r in rows)


@pytest.mark.django_db
def test_topic_csv_export_has_triage_columns(client):
    report = _post_report()

    resp = _admin_client(client).get("/cms/snippets/wagtail_forum/topic/?export=csv")

    assert resp.status_code == 200
    header, row = _csv(resp)[:2]
    assert header.split(",") == TOPIC_HEADINGS
    assert row.startswith(f"{report.post.topic_id},Seedling help,General,author,True")


@pytest.mark.django_db
def test_report_inspect_view_is_reachable(client):
    from django.urls import reverse
    from wagtail_forum.models import Report

    report = _post_report()
    url = reverse(Report.snippet_viewset.get_url_name("inspect"), args=[report.pk])

    resp = _admin_client(client).get(url)

    assert resp.status_code == 200
    assert b"looks like a bot" in resp.content


@pytest.mark.django_db
def test_topic_inspect_view_is_reachable(client):
    from django.urls import reverse
    from wagtail_forum.models import Topic

    topic = _post_report().post.topic
    url = reverse(Topic.snippet_viewset.get_url_name("inspect"), args=[topic.pk])

    resp = _admin_client(client).get(url)

    assert resp.status_code == 200
    assert b"seedling-help" in resp.content


@pytest.mark.django_db
def test_post_listing_search_matches_a_body_prefix(client):
    """Pins `index.AutocompleteField("body")` on Post (audit 2026-09-04 L10),
    the Post half of test_topic_listing_search_matches_a_title_prefix: with
    PostViewSet.search_fields=["body"] but no AutocompleteField, Wagtail's
    admin `search_queryset` falls back to whole-word search() (plus a
    RuntimeWarning pytest does not fail on), so "photosynth" stops matching
    "photosynthesis basics" in the CMS with every test still green."""
    from wagtail.models import Page
    from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Post, Topic

    author = User.objects.create_user(username="prefix_search_author")
    ForumProfile.for_user(author)
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="PForum", slug="pforum"))
    board = index.add_child(instance=ForumBoard(title="PGeneral", slug="pgeneral"))
    topic = Topic.objects.create(board=board, title="PT", slug="pt", author=author)
    post = Post(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": "<p>photosynthesis basics</p>"}],
    )
    post.save()
    post.save_revision().publish()

    admin = User.objects.create_superuser(username="root_pp", email="rpp@x.io")
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/post/?q=photosynth")

    assert resp.status_code == 200
    # Mutation-checked (code review, PR #629): with the AutocompleteField
    # removed the page says "No posts" — `str(post.pk)` still matched asset
    # hashes, so only a rendered-row marker pins the field.
    assert b"No posts" not in resp.content
    assert f"/post/edit/{post.pk}/".encode() in resp.content


@pytest.mark.django_db
def test_badge_snippet_list_is_reachable_in_admin(client):
    """todo 348: badges are CMS-curated snippets in the Forum group."""
    from wagtail_forum.models import Badge, BadgeMetric, BadgeRule

    admin = User.objects.create_superuser(username="root", email="r@x.io")
    badge = Badge.objects.create(slug="listed", name="Listed")
    BadgeRule.objects.create(badge=badge, metric=BadgeMetric.POSTS, threshold=1)
    client.force_login(admin)

    resp = client.get("/cms/snippets/wagtail_forum/badge/")

    assert resp.status_code == 200
    assert "Listed" in resp.content.decode()


@pytest.mark.django_db
def test_badge_snippet_create_form_saves_inline_rules(client):
    """The genuinely new Wagtail surface (todo 348 review): a ClusterableModel
    snippet whose InlinePanel child formset must persist through the real
    create view, not just list."""
    from django.urls import reverse
    from wagtail_forum.models import Badge

    admin = User.objects.create_superuser(username="root", email="r@x.io")
    client.force_login(admin)
    url = reverse(Badge.snippet_viewset.get_url_name("add"))
    assert client.get(url).status_code == 200

    resp = client.post(
        url,
        {
            "name": "Helper",
            "slug": "helper",
            "description": "Answered a question.",
            "order": "5",
            "is_active": "on",
            "rules-TOTAL_FORMS": "1",
            "rules-INITIAL_FORMS": "0",
            "rules-MIN_NUM_FORMS": "1",
            "rules-MAX_NUM_FORMS": "1000",
            "rules-0-metric": "solutions_accepted",
            "rules-0-threshold": "1",
            "rules-0-ORDER": "1",
            "rules-0-DELETE": "",
        },
    )

    assert resp.status_code == 302, resp.content.decode()[:2000]
    badge = Badge.objects.get(slug="helper")
    rule = badge.rules.get()
    assert (rule.metric, rule.threshold) == ("solutions_accepted", 1)
