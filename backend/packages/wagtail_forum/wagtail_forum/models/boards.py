from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page


class ForumIndex(Page):
    """Root forum node. Lets a host site place the forum in its page tree."""

    # Feature list matches `INTRO_ALLOWED_TAGS` in api/sanitize.py. Wagtail's
    # default set adds `image` and `embed`, which the API strips — offering an
    # editor a button whose output silently vanishes is its own bug, and
    # expanding either has a side effect (an untimed oEmbed fetch, a rendition
    # write) that the strip cannot refund. This is the editor-side half; the
    # API-side strip is the half that holds for content the editor never typed.
    intro = RichTextField(
        blank=True,
        features=[
            "h2",
            "h3",
            "h4",
            "bold",
            "italic",
            "link",
            "document-link",
            "ol",
            "ul",
            "hr",
        ],
    )

    # Landing-page "Community event" hero (todo 304). Backend-owned signal —
    # replaces the old client-side inference (a pinned + slug-prefix scan
    # over the recent-topics window, with hardcoded seasonal copy). A
    # moderator features/unfeatures an event by setting/clearing this FK; no
    # deploy, and no dependence on the recency window a topic could age out
    # of while the event is still live. SET_NULL, not CASCADE: deleting the
    # topic must not take the page down with it — the hero just reverts to
    # the evergreen fallback.
    featured_topic = models.ForeignKey(
        "wagtail_forum.Topic",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text=(
            "Feature this topic as the landing page's 'Community event' "
            "hero. Leave blank for the evergreen hero."
        ),
    )
    featured_eyebrow = models.CharField(
        max_length=60, blank=True, default="Community event"
    )
    featured_description = models.TextField(
        blank=True,
        help_text="Hero description shown under the featured topic's own title.",
    )

    # Forums are plain rows of `Forum` (todo 665), not child pages: the page
    # tree carries only this index, which places the forum on the site.
    subpage_types: list[str] = []
    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        MultiFieldPanel(
            [
                FieldPanel("featured_topic"),
                FieldPanel("featured_eyebrow"),
                FieldPanel("featured_description"),
            ],
            heading="Landing-page event hero",
        ),
    ]

    def get_context(self, request, *args, **kwargs):
        # Minimal server-rendered fallback (audit 2026-07-11 H17): these pages
        # are live-routable, so direct serving (admin "View live", sitemaps,
        # crawlers) must render instead of 500ing with TemplateDoesNotExist.
        context = super().get_context(request, *args, **kwargs)
        # Same visibility rule as the API (`api.views._visible_boards`): the
        # guest view, since this page is served to crawlers and caches. A
        # local import so the model module never imports the service at load.
        from ..services.forum_permissions import visible_forums

        context["boards"] = visible_forums(None, Forum.FORUM).order_by(
            "parent__position", "position", "id"
        )
        return context


# A link row's URL may only be a web address (todo 670): Django's default
# URLValidator also admits ftp/ftps, and anything else (``javascript:``,
# ``data:``) would run in the reader's browser from a forum row.
LINK_URL_SCHEMES = ("http", "https")


class Forum(models.Model):
    """A category, forum or link row (todo 665; spec 2026-10-28 §4).

    Replaces the old ``ForumBoard`` page. Depth is exactly two: a *category*
    holds forums and never topics; a *forum* holds topics; a *link* is a row
    that sends the reader to a URL (later slice). Every forum and link sits
    under one category. An adjacency list (``parent`` + ``position``), not a
    tree library, because every move is a one-row update at this depth.

    ``Topic.board`` points here; the field kept its name so topic URLs
    (``/forum/{board.id}-{board.slug}/...``) and the API stay unchanged, and
    the migration copied every board's page id across for the same reason.
    """

    CATEGORY = "category"
    FORUM = "forum"
    LINK = "link"
    FORUM_TYPE_CHOICES = [
        (CATEGORY, _("Category")),
        (FORUM, _("Forum")),
        (LINK, _("Link")),
    ]

    forum_type = models.CharField(
        max_length=16, choices=FORUM_TYPE_CHOICES, default=FORUM
    )
    # PROTECT: a category with forums under it can never be deleted out from
    # under them (the safe delete with "move forums to…" is a later slice).
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
        limit_choices_to={"forum_type": CATEGORY},
    )
    position = models.PositiveIntegerField(default=0)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    # Plain TextField, not RichTextField, by design: the API serves the value
    # verbatim and every client (web ForumCard, the Flutter board list)
    # renders it as escaped text. Rich text here would flip the contract to
    # HTML for all consumers and require the intro expand+sanitize pipeline —
    # for a one-line card blurb. Rich text belongs in ForumIndex.intro.
    description = models.TextField(blank=True)
    # Denormalized counters (maintained as topics/posts change; see
    # signals._refresh_board_counters). Meaningful on forum rows only; a
    # category's numbers are summed from its visible forums at read time.
    topic_count = models.PositiveIntegerField(default=0, editable=False)
    post_count = models.PositiveIntegerField(default=0, editable=False)
    # Who may see a row is its `grants` (models/permissions.py, todos
    # 675-676); `is_hidden` became a "No access for everyone" grant set.
    # Posting tab (todo 678): plain text, each line a paragraph, prefilled
    # into an empty new-topic composer.
    # db_default on each column added with this release (todo 675-680): the
    # previous release serves while `migrate` runs and inserts without them.
    topic_template = models.TextField(
        blank=True,
        default="",
        db_default="",
        help_text=_(
            "Prefilled into the new-topic composer when it is empty. Plain "
            "text: each line becomes a paragraph."
        ),
    )
    # Pruning tab (todo 679): `manage.py prune_forums` unpublishes topics
    # whose last post is older than the threshold. Days since last post only
    # (owner decision 2026-10-30).
    prune_enabled = models.BooleanField(default=False, db_default=False)
    prune_days_since_last_post = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Unpublish topics with no post for this many days."),
    )
    prune_pinned = models.BooleanField(
        default=False, db_default=False, help_text=_("Prune pinned topics too.")
    )
    prune_polls = models.BooleanField(
        default=False, db_default=False, help_text=_("Prune topics with a poll too.")
    )
    # Password-protected forum (todo 680): a Django password hash, never the
    # password. Blank = no password. Set through the admin form's write-only
    # field; unlocked per session by `POST /forum/boards/{slug}/unlock/`.
    password_hash = models.CharField(
        max_length=256, blank=True, editable=False, default="", db_default=""
    )
    # Link rows (todo 670; phpBB FORUM_LINK). phpBB counts redirects in the
    # post counter; a dedicated column keeps the forum counters honest.
    link_url = models.URLField(
        max_length=2000,
        blank=True,
        validators=[URLValidator(schemes=list(LINK_URL_SCHEMES))],
        help_text=_("Where the link sends readers (http or https only)."),
    )
    track_clicks = models.BooleanField(
        default=True,
        help_text=_(
            "Send readers through the forum's redirect so each click is counted."
        ),
    )
    # Incremented atomically by the redirect (`/forum/links/<id>/go/`).
    click_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            # `/forum/boards/{slug}/` only ever resolves forums, so a forum or
            # link slug is unique across the whole forum. Categories are left
            # out: their slugs share a namespace only with each other, which
            # is also why the migration's default "General" category can never
            # collide with an existing board's slug.
            models.UniqueConstraint(
                fields=["slug"],
                condition=~models.Q(forum_type="category"),
                name="uniq_forum_slug_non_category",
            ),
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(forum_type="category"),
                name="uniq_forum_category_slug",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def has_password(self) -> bool:
        return bool(self.password_hash)

    @property
    def title(self):
        """The old ``ForumBoard.title`` (a Page title), kept read-only so the
        API's ``title`` key and every ``topic.board.title`` reader stay as they
        were. Write ``name``."""
        return self.name

    def clean(self):
        super().clean()
        errors: dict[str, object] = {}
        if self.forum_type == self.LINK:
            if not self.link_url:
                errors["link_url"] = _("A link needs a URL.")
        else:
            # Only a link has a URL: a hidden admin field typed into before
            # the type was switched must not leave one on a forum.
            self.link_url = ""
        try:
            self._clean_parent()
        except ValidationError as error:
            errors.update(error.message_dict)
        if errors:
            raise ValidationError(errors)

    def _clean_parent(self):
        if self.forum_type == self.CATEGORY:
            if self.parent_id is not None:
                raise ValidationError({"parent": _("A category cannot have a parent.")})
            return
        if self.parent_id is None:
            raise ValidationError(
                {"parent": _("A forum or link must belong to a category.")}
            )
        parent_type = (
            self.parent.forum_type
            if self.parent is not None
            else Forum.objects.filter(pk=self.parent_id)
            .values_list("forum_type", flat=True)
            .first()
        )
        if parent_type != self.CATEGORY:
            raise ValidationError(
                {"parent": _("Only a category can hold forums and links.")}
            )
