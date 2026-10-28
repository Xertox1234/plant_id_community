"""Boards stop being Wagtail pages (todo 665, spec 2026-10-28 §4) — step 1 of 4.

Creates ``Forum`` (category / forum / link rows) and copies every
``ForumBoard`` page into it **keeping its id**, so every topic URL
(``/forum/{board.id}-{board.slug}/...``) and every stored ``board_id`` stays
valid. Each copied board becomes a forum under one default category,
"General". A board that was not live, or that sat under a
``PageViewRestriction`` (on itself or an ancestor), was invisible to the whole
API (``.live().public()``), so it becomes ``is_hidden=True``.

The four steps are four migrations on purpose: Postgres foreign keys are
``DEFERRABLE INITIALLY DEFERRED``, so rows written here leave pending trigger
events, and an ``ALTER TABLE`` or ``DROP TABLE`` in the same transaction fails
with "cannot ALTER TABLE because it has pending trigger events".

0042 repoints ``Topic.board`` at ``Forum`` (``PROTECT``), 0043 deletes the old
board pages, 0044 drops the ``ForumBoard`` table.
"""

import django.db.models.deletion
from django.core.management.color import no_style
from django.db import migrations, models

# The default category's slug. Category slugs are unique among categories
# only (a partial constraint), so a board whose slug is also "general" copies
# across untouched.
DEFAULT_CATEGORY_SLUG = "general"


def copy_boards_to_forums(apps, schema_editor):
    ForumBoard = apps.get_model("wagtail_forum", "ForumBoard")
    Forum = apps.get_model("wagtail_forum", "Forum")
    PageViewRestriction = apps.get_model("wagtailcore", "PageViewRestriction")

    boards = list(ForumBoard.objects.order_by("path"))
    if not boards:
        # A fresh database gets no default category here: seed_default_forum
        # creates one with the first forum.
        return

    restricted_paths = list(
        PageViewRestriction.objects.values_list("page__path", flat=True)
    )
    taken = set()
    rows = []
    for position, board in enumerate(boards):
        # Page slugs were unique among siblings only, so two forum trees could
        # share one. Forum slugs are unique forum-wide; the later board (tree
        # order) takes its id as a suffix rather than failing the migration.
        slug = board.slug
        if slug in taken:
            slug = f"{board.slug}-{board.pk}"
        taken.add(slug)
        hidden = not board.live or any(
            board.path.startswith(path) for path in restricted_paths
        )
        rows.append(
            Forum(
                id=board.pk,
                forum_type="forum",
                position=position,
                name=board.title,
                slug=slug,
                description=board.description,
                topic_count=board.topic_count,
                post_count=board.post_count,
                is_hidden=hidden,
            )
        )
    Forum.objects.bulk_create(rows)

    # Explicit ids leave the sequence behind them; the next INSERT (the
    # category just below) would collide with a copied board's id.
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        for sql in connection.ops.sequence_reset_sql(no_style(), [Forum]):
            cursor.execute(sql)

    category = Forum.objects.create(
        forum_type="category", name="General", slug=DEFAULT_CATEGORY_SLUG
    )
    Forum.objects.filter(forum_type="forum").update(parent=category)


class Migration(migrations.Migration):
    dependencies = [
        ("wagtail_forum", "0040_forumprofile_quiet_hours"),
        ("wagtailcore", "0097_baselogentry_uuid_action_timestamp_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="Forum",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "forum_type",
                    models.CharField(
                        choices=[
                            ("category", "Category"),
                            ("forum", "Forum"),
                            ("link", "Link"),
                        ],
                        default="forum",
                        max_length=16,
                    ),
                ),
                ("position", models.PositiveIntegerField(default=0)),
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("topic_count", models.PositiveIntegerField(default=0, editable=False)),
                ("post_count", models.PositiveIntegerField(default=0, editable=False)),
                ("is_hidden", models.BooleanField(default=False)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        limit_choices_to={"forum_type": "category"},
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="wagtail_forum.forum",
                    ),
                ),
            ],
            options={
                "ordering": ["position", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="forum",
            constraint=models.UniqueConstraint(
                condition=models.Q(("forum_type", "category"), _negated=True),
                fields=("slug",),
                name="uniq_forum_slug_non_category",
            ),
        ),
        migrations.AddConstraint(
            model_name="forum",
            constraint=models.UniqueConstraint(
                condition=models.Q(("forum_type", "category")),
                fields=("slug",),
                name="uniq_forum_category_slug",
            ),
        ),
        # Reverse is a no-op: unapplying CreateModel drops the copied rows.
        migrations.RunPython(copy_boards_to_forums, migrations.RunPython.noop),
    ]
