from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, URLValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.images import get_image_model_string
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
        # The guest view of the API's rule (`api.views._visible_boards`),
        # since this page is served to crawlers and caches, minus its
        # ForumIndex gate: the page being served IS the index, and Wagtail
        # already let this viewer past its privacy (round-2 review; main
        # listed the boards here too). A local import so the model module
        # never imports the service at load.
        from ..services.forum_permissions import LIST, READ, access_q

        context["boards"] = Forum.objects.filter(
            access_q(None, READ) & access_q(None, LIST, "parent"),
            forum_type=Forum.FORUM,
            password_hash="",
        ).order_by("parent__position", "position", "id")
        return context


# A link row's URL may only be a web address (todo 670): Django's default
# URLValidator also admits ftp/ftps, and anything else (``javascript:``,
# ``data:``) would run in the reader's browser from a forum row.
LINK_URL_SCHEMES = ("http", "https")

# Display settings (todo 669, owner decision 2026-10-30). A forum's colour is
# one of the Canopy accent tokens, stored by name: the web maps each to a
# `--gt-*` token that is defined for light and dark, so no stored value can
# fail contrast in either mode. Blank = the default ink.
FORUM_COLOUR_CHOICES = [
    ("sage", _("Sage")),
    ("pollen", _("Pollen")),
    ("bloom", _("Bloom")),
    ("orchid", _("Orchid")),
]

# The `?sort=` values of the topic list (api/pagination.py SORT_ORDERINGS),
# kept literal so this module never imports the API layer. A test pins the
# two lists together.
FORUM_SORT_CHOICES = [
    ("-last_activity_at", _("Latest activity")),
    ("-created_at", _("Newest topics")),
    ("created_at", _("Oldest topics")),
    ("-view_count", _("Most viewed")),
    ("-post_count", _("Most replies")),
]

# The topics-per-page bound: the paginator's own `max_page_size`.
FORUM_TOPICS_PER_PAGE_MAX = 100

# Per-forum themes (todo 681, owner decision 2026-10-30): a fixed set of
# Canopy-safe token scopes the web applies on the forum and thread pages.
# Blank = the site's own Canopy tokens. The colour above stays an accent on
# top of the theme.
FORUM_THEME_CHOICES = [
    ("botanical", _("Botanical")),
    ("moss", _("Moss")),
    ("terracotta", _("Terracotta")),
    ("slate", _("Slate")),
]

# The longest icon value: one emoji can be several code points (a skin tone,
# a ZWJ sequence, a variation selector), so the bound is generous in code
# points but the validator still admits one visible symbol only.
FORUM_ICON_MAX_LENGTH = 16


def validate_forum_icon(value: str) -> None:
    """A single emoji (owner decision 2026-10-30), or blank.

    Python's ``re`` has no grapheme-cluster class, so this is the structural
    approximation: the first code point must be a pictograph (or a regional
    indicator, for a flag), and every later one must be a joiner, a variation
    selector, a skin-tone modifier, a keycap/tag mark or a pictograph that a
    joiner glued on. Letters, digits, spaces and punctuation are refused.
    """
    if not value:
        return
    error = ValidationError(_("Enter a single emoji."), code="invalid_icon")
    if len(value) > FORUM_ICON_MAX_LENGTH:
        raise error

    def pictograph(cp: int) -> bool:
        return (
            0x1F000 <= cp <= 0x1FAFF
            or 0x2600 <= cp <= 0x27BF
            or 0x2300 <= cp <= 0x23FF
            or 0x2B00 <= cp <= 0x2BFF
            or cp in (0x00A9, 0x00AE, 0x203C, 0x2049, 0x2122, 0x2139, 0x3030, 0x303D)
            or 0x2190 <= cp <= 0x21FF
        )

    def regional(cp: int) -> bool:
        return 0x1F1E6 <= cp <= 0x1F1FF

    def modifier(cp: int) -> bool:
        return (
            cp in (0x200D, 0xFE0F, 0xFE0E, 0x20E3)
            or 0x1F3FB <= cp <= 0x1F3FF
            or 0xE0020 <= cp <= 0xE007F
        )

    cps = [ord(ch) for ch in value]
    first = cps[0]
    # A lone skin-tone modifier sits inside the pictograph range, and a
    # trailing joiner joins nothing: neither is a whole emoji.
    if 0x1F3FB <= first <= 0x1F3FF or cps[-1] == 0x200D:
        raise error
    if regional(first):
        if len(cps) != 2 or not regional(cps[1]):
            raise error
        return
    if not pictograph(first) and not (
        # A keycap: digit/#/* + VS16 + U+20E3.
        len(cps) == 3
        and chr(first) in "0123456789#*"
        and cps[1] == 0xFE0F
        and cps[2] == 0x20E3
    ):
        raise error
    previous_joiner = False
    for cp in cps[1:]:
        if modifier(cp):
            previous_joiner = cp == 0x200D
            continue
        if previous_joiner and pictograph(cp):
            previous_joiner = False
            continue
        raise error


# The longest forum password the admin sets or a reader may submit (todo 680):
# an unbounded body would make every unlock attempt hash it whole.
FORUM_PASSWORD_MAX_LENGTH = 128


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
    # Display settings (todo 669). `is_closed`, not phpBB's "locked": the API
    # already says `is_locked` for a password forum this session has not
    # unlocked (todo 680), and a closed forum mirrors `Topic.is_closed`: no
    # new topics or replies, staff and the forum's moderators exempt.
    is_closed = models.BooleanField(
        default=False,
        db_default=False,
        help_text=_(
            "No new topics or replies. Staff and this forum's moderators can "
            "still post."
        ),
    )
    # Rules (owner decision 2026-10-30): plain text plus an optional link,
    # phpBB style. Served verbatim and rendered as escaped text.
    rules = models.TextField(
        blank=True,
        default="",
        db_default="",
        help_text=_("Plain text shown above the topic list. Each line a paragraph."),
    )
    rules_url = models.URLField(
        max_length=2000,
        blank=True,
        default="",
        db_default="",
        validators=[URLValidator(schemes=list(LINK_URL_SCHEMES))],
        help_text=_("Optional link to the full rules (http or https only)."),
    )
    icon = models.CharField(
        max_length=FORUM_ICON_MAX_LENGTH,
        blank=True,
        default="",
        db_default="",
        validators=[validate_forum_icon],
        help_text=_("A single emoji shown beside the forum's name."),
    )
    colour = models.CharField(
        max_length=16,
        blank=True,
        default="",
        db_default="",
        choices=FORUM_COLOUR_CHOICES,
        help_text=_("An accent from the site palette, safe in light and dark."),
    )
    # Owner decision 2026-10-31: an optional Wagtail image, chosen in the
    # admin and shown on the forum index. SET_NULL: deleting the image never
    # takes the forum with it.
    image = models.ForeignKey(
        get_image_model_string(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    topics_per_page = models.PositiveSmallIntegerField(
        default=0,
        db_default=0,
        validators=[MaxValueValidator(FORUM_TOPICS_PER_PAGE_MAX)],
        help_text=_("Topics on each page of this forum. 0 = the site default."),
    )
    default_sort = models.CharField(
        max_length=32,
        blank=True,
        default="",
        db_default="",
        choices=FORUM_SORT_CHOICES,
        help_text=_("The topic order readers see first. Blank = latest activity."),
    )
    # Todo 681: one of the fixed Canopy-safe themes, or blank.
    theme = models.CharField(
        max_length=16,
        blank=True,
        default="",
        db_default="",
        choices=FORUM_THEME_CHOICES,
        help_text=_("A colour theme for this forum's pages."),
    )

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
