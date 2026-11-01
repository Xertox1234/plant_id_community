# Per-forum display settings (todo 669). Every column carries a db_default:
# the previous release still serves while `migrate` runs, and its inserts
# name none of them (docs/rules/database.md expand/contract).

import django.core.validators
import django.db.models.deletion
import wagtail_forum.models.boards
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("wagtail_forum", "0049_remove_forum_is_hidden"),
        ("wagtailimages", "0027_image_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="forum",
            name="colour",
            field=models.CharField(
                blank=True,
                choices=[
                    ("sage", "Sage"),
                    ("pollen", "Pollen"),
                    ("bloom", "Bloom"),
                    ("orchid", "Orchid"),
                ],
                db_default="",
                default="",
                help_text="An accent from the site palette, safe in light and dark.",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="forum",
            name="default_sort",
            field=models.CharField(
                blank=True,
                choices=[
                    ("-last_activity_at", "Latest activity"),
                    ("-created_at", "Newest topics"),
                    ("created_at", "Oldest topics"),
                    ("-view_count", "Most viewed"),
                    ("-post_count", "Most replies"),
                ],
                db_default="",
                default="",
                help_text="The topic order readers see first. Blank = latest activity.",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="forum",
            name="icon",
            field=models.CharField(
                blank=True,
                db_default="",
                default="",
                help_text="A single emoji shown beside the forum's name.",
                max_length=16,
                validators=[wagtail_forum.models.boards.validate_forum_icon],
            ),
        ),
        migrations.AddField(
            model_name="forum",
            name="image",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="wagtailimages.image",
            ),
        ),
        migrations.AddField(
            model_name="forum",
            name="is_closed",
            field=models.BooleanField(
                db_default=False,
                default=False,
                help_text="No new topics or replies. Staff and this forum's moderators can still post.",
            ),
        ),
        migrations.AddField(
            model_name="forum",
            name="rules",
            field=models.TextField(
                blank=True,
                db_default="",
                default="",
                help_text="Plain text shown above the topic list. Each line a paragraph.",
            ),
        ),
        migrations.AddField(
            model_name="forum",
            name="rules_url",
            field=models.URLField(
                blank=True,
                db_default="",
                default="",
                help_text="Optional link to the full rules (http or https only).",
                max_length=2000,
                validators=[
                    django.core.validators.URLValidator(schemes=["http", "https"])
                ],
            ),
        ),
        migrations.AddField(
            model_name="forum",
            name="topics_per_page",
            field=models.PositiveSmallIntegerField(
                db_default=0,
                default=0,
                help_text="Topics on each page of this forum. 0 = the site default.",
                validators=[django.core.validators.MaxValueValidator(100)],
            ),
        ),
    ]
