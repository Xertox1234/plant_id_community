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
    assert str(post.pk).encode() in resp.content


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
    from wagtail.models import Page
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
