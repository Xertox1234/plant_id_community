from django.core.management.base import BaseCommand
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex


class Command(BaseCommand):
    help = "Idempotently ensure a ForumIndex + a starter ForumBoard exist."

    def handle(self, *args, **options):
        index = ForumIndex.objects.first()
        if index is None:
            root = Page.objects.filter(depth=1).first()
            index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
            self.stdout.write(self.style.SUCCESS("Created ForumIndex 'forum'."))

        if not index.get_children().type(ForumBoard).exists():
            index.add_child(
                instance=ForumBoard(
                    title="General Discussion",
                    slug="general-discussion",
                    description="Talk about anything plant-related.",
                )
            )
            self.stdout.write(self.style.SUCCESS("Created board 'general-discussion'."))
        else:
            self.stdout.write("Forum already seeded; nothing to do.")
