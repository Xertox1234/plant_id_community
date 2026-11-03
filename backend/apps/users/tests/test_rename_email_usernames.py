"""``rename_email_usernames``: accounts whose username was minted from their
email get a random one, and their ``@old`` mentions are rewritten."""

from io import StringIO

from apps.users.management.commands.rename_email_usernames import is_email_derived
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from wagtail.models import Revision
from wagtail_forum.models import Post, Topic
from wagtail_forum.tests.factories import make_forum

User = get_user_model()

HANDLE = r"^member_[a-z2-9]{8}$"


class IsEmailDerivedTest(SimpleTestCase):
    def test_local_part_and_minting_suffixes(self):
        for username, email in [
            ("john", "john@example.com"),
            ("John.Doe+Test", "john.doe+test@example.com"),  # Firebase kept it as-is
            ("johndoetest", "john.doe+test@example.com"),  # allauth cleaned it
            ("john_1a2b3c4d", "john@example.com"),  # Firebase clash suffix
            ("john2", "john@example.com"),  # OAuth / allauth clash counter
        ]:
            with self.subTest(username=username):
                self.assertTrue(is_email_derived(username, email))

    def test_unrelated_or_already_generated(self):
        for username, email in [
            ("gardener", "john@example.com"),
            ("johnathan", "john@example.com"),  # longer name, not a suffix
            ("member_k7wq2mxd", "member_k7wq2mxd@example.com"),
            ("john", ""),
        ]:
            with self.subTest(username=username):
                self.assertFalse(is_email_derived(username, email))


class RenameEmailUsernamesCommandTest(TestCase):
    def setUp(self):
        # Minted by Firebase: no password.
        self.minted = User.objects.create(
            username="jane.doe", email="jane.doe@example.com", firebase_uid="uid-1"
        )
        # Chose its username at registration and signs in with a password.
        self.registered = User.objects.create_user(
            username="sam",
            email="sam@example.com",
            password="pw-12345678x",  # pragma: allowlist secret
        )
        self.other = User.objects.create_user(
            username="gardener", email="g@example.com"
        )

    def _run(self, *args):
        out = StringIO()
        call_command("rename_email_usernames", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_writes_nothing(self):
        output = self._run()

        self.minted.refresh_from_db()
        self.assertEqual(self.minted.username, "jane.doe")
        self.assertIn(f"would rename id={self.minted.pk}", output)
        self.assertIn(f"skip id={self.registered.pk}", output)

    def test_apply_renames_minted_accounts_only(self):
        output = self._run("--apply")

        self.minted.refresh_from_db()
        self.registered.refresh_from_db()
        self.other.refresh_from_db()
        self.assertRegex(self.minted.username, HANDLE)
        self.assertEqual(self.registered.username, "sam")
        self.assertEqual(self.other.username, "gardener")
        # The output lands in deployment logs: ids and new handles only.
        for leaked in ("jane", "sam@", "example.com"):
            self.assertNotIn(leaked, output)

    def test_include_password_accounts(self):
        self._run("--apply", "--include-password-accounts")

        self.registered.refresh_from_db()
        self.assertRegex(self.registered.username, HANDLE)

    def test_rewrites_mentions_in_bodies_titles_and_revisions(self):
        forum = make_forum()
        topic = Topic.objects.create(
            board=forum, title="Ask @jane.doe", slug="ask", author=self.other
        )
        post = Post.objects.create(
            topic=topic,
            author=self.other,
            body=[
                {
                    "type": "paragraph",
                    "value": (
                        "<p>thanks @jane.doe, cc @jane.doe_x and "
                        "mail me at x@jane.doe</p>"
                    ),
                }
            ],
        )
        post.save_revision()
        topic.save_revision()

        output = self._run("--apply")

        new = User.objects.get(pk=self.minted.pk).username
        post.refresh_from_db()
        topic.refresh_from_db()
        self.assertEqual(
            post.body.raw_data[0]["value"],
            f"<p>thanks @{new}, cc @jane.doe_x and mail me at x@jane.doe</p>",
        )
        self.assertEqual(topic.title, f"Ask @{new}")
        for revision in Revision.objects.filter(object_id__in=[post.pk, topic.pk]):
            self.assertNotIn("@jane.doe,", str(revision.content))
            self.assertNotIn("Ask @jane.doe", str(revision.content))
        self.assertIn(f"@{new}", str(post.latest_revision.content))
        self.assertIn("rewrote 4 mention(s) in 2 post(s)/topic(s)", output)

    def test_nothing_to_do(self):
        self.minted.delete()

        self.assertIn("Nothing to rename.", self._run("--apply"))
