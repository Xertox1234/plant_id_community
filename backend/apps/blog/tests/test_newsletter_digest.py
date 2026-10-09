"""The weekly blog newsletter sender (todo 409, slice B)."""

from datetime import date, timedelta
from io import StringIO
from unittest import mock
from urllib.parse import parse_qs, urlencode, urlparse

from apps.blog import newsletter, newsletter_digest, tasks
from apps.blog.constants import (
    NEWSLETTER_CONFIRM_MAX_AGE_SECONDS,
    NEWSLETTER_CONTINUATION_DELAY,
    NEWSLETTER_MAX_POSTS,
    NEWSLETTER_SOFT_TIME_LIMIT,
    NEWSLETTER_TIME_LIMIT,
)
from apps.blog.management.commands.send_blog_newsletter import LOCK_KEY
from apps.blog.models import BlogIndexPage, BlogNewsletter, BlogPostPage
from celery.exceptions import SoftTimeLimitExceeded
from celery.schedules import crontab
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.utils import timezone
from wagtail.models import Page, PageViewRestriction

SITE = "https://web.example"
API = "https://api.example"


def _run(*args):
    out = StringIO()
    call_command("send_blog_newsletter", *args, stdout=out)
    return out.getvalue()


@override_settings(SITE_URL=SITE, API_PUBLIC_URL=API)
class NewsletterSenderTests(TestCase):
    def setUp(self):
        cache.clear()  # the run lock lives in the cache
        self.now = timezone.now()
        self.author = get_user_model().objects.create_user(
            username="author", email="author@example.com"
        )
        self.index = BlogIndexPage(title="Blog", slug="newsletter-blog")
        Page.objects.get(id=1).add_child(instance=self.index)

    def _post(self, slug, days_ago, live=True, introduction="<p>intro</p>"):
        post = BlogPostPage(
            title=slug.replace("-", " ").title(),
            slug=slug,
            author=self.author,
            publish_date=date.today(),
            introduction=introduction,
            content_blocks=[],
            live=live,
        )
        self.index.add_child(instance=post)
        # add_child() leaves first_published_at NULL, and a NULL post would
        # drop out of every window, so the suite would pass on empty emails.
        BlogPostPage.objects.filter(pk=post.pk).update(
            first_published_at=self.now - timedelta(days=days_ago)
        )
        return post

    def _subscriber(self, email="reader@example.com", confirmed_days_ago=30, **fields):
        fields.setdefault("confirmed_at", self.now - timedelta(days=confirmed_days_ago))
        return BlogNewsletter.objects.create(email=email, **fields)

    def _sent_to(self):
        return sorted(address for m in mail.outbox for address in m.to)

    # --- who gets it -----------------------------------------------------

    def test_only_confirmed_active_subscribers_are_mailed(self):
        self._post("fresh-post", days_ago=1)
        self._subscriber("confirmed@example.com")
        self._subscriber("pending@example.com", confirmed_at=None)
        self._subscriber("left@example.com", is_active=False, unsubscribed_at=self.now)

        _run()

        self.assertEqual(self._sent_to(), ["confirmed@example.com"])

    def test_posts_from_before_confirmation_are_not_sent(self):
        self._post("before", days_ago=3)
        self._post("after", days_ago=1)
        self._subscriber(confirmed_days_ago=2)

        _run()

        body = mail.outbox[0].body
        self.assertIn(f"{SITE}/blog/after", body)
        self.assertNotIn("/blog/before", body)

    def test_a_returning_reader_gets_no_backlog_from_while_they_were_away(self):
        self._post("while-away", days_ago=20)
        self._post("since-return", days_ago=1)
        # Mailed 30 days ago, then unsubscribed, then confirmed again 2 days ago.
        self._subscriber(
            confirmed_days_ago=2, last_sent_at=self.now - timedelta(days=30)
        )

        _run()

        body = mail.outbox[0].body
        self.assertIn("/blog/since-return", body)
        self.assertNotIn("/blog/while-away", body)

    def test_posts_since_the_last_newsletter_only(self):
        self._post("old-news", days_ago=10)
        self._post("this-week", days_ago=2)
        self._subscriber(last_sent_at=self.now - timedelta(days=7))

        _run()

        body = mail.outbox[0].body
        self.assertIn("/blog/this-week", body)
        self.assertNotIn("/blog/old-news", body)

    def test_drafts_private_and_future_posts_are_left_out(self):
        self._post("public-post", days_ago=1)
        self._post("draft-post", days_ago=1, live=False)
        private = self._post("private-post", days_ago=1)
        PageViewRestriction.objects.create(
            page=private, restriction_type=PageViewRestriction.LOGIN
        )
        # Published after the run's own timestamp: next week's email.
        self._post("future-post", days_ago=-1)
        self._subscriber()

        _run()

        body = mail.outbox[0].body
        self.assertIn("/blog/public-post", body)
        for slug in ("draft-post", "private-post", "future-post"):
            self.assertNotIn(f"/blog/{slug}", body)

    def test_a_long_backlog_is_capped(self):
        for n in range(NEWSLETTER_MAX_POSTS + 2):
            self._post(f"post-{n}", days_ago=1 + n * 0.1)
        self._subscriber()

        _run()

        body = mail.outbox[0].body
        self.assertEqual(body.count(f"{SITE}/blog/post-"), NEWSLETTER_MAX_POSTS)
        self.assertIn("/blog/post-0", body)  # newest first
        self.assertIn(f"Everything on the blog: {SITE}/blog", body)

    # --- the email -------------------------------------------------------

    def test_every_email_unsubscribes_with_one_token_in_link_and_header(self):
        self._post("fresh-post", days_ago=1)
        subscriber = self._subscriber()

        _run()

        message = mail.outbox[0]
        header = message.extra_headers["List-Unsubscribe"].strip("<>")
        self.assertTrue(header.startswith(f"{API}/"))
        self.assertEqual(
            message.extra_headers["List-Unsubscribe-Post"],
            "List-Unsubscribe=One-Click",
        )
        token = parse_qs(urlparse(header).query)["token"][0]
        link = f"{SITE}/newsletter/unsubscribe?{urlencode({'token': token})}"
        self.assertIn(link, message.body)
        self.assertIn(link, message.alternatives[0][0])

        newsletter.unsubscribe(token)
        subscriber.refresh_from_db()
        self.assertFalse(subscriber.is_subscribed)

    def test_rich_text_introduction_becomes_plain_escaped_text(self):
        self._post(
            "fresh-post", days_ago=1, introduction="<p>Ferns &amp; <b>moss</b></p>"
        )
        self._subscriber()

        _run()

        message = mail.outbox[0]
        self.assertIn("Ferns & moss", message.body)
        html = message.alternatives[0][0]
        self.assertIn("Ferns &amp; moss", html)
        self.assertNotIn("<b>moss</b>", html)
        self.assertNotIn("&amp;amp;", html)

    def test_subject_names_a_single_post(self):
        self._post("only-one", days_ago=1)
        self._subscriber()

        _run()

        self.assertIn("Only One", mail.outbox[0].subject)

    # --- once a week -----------------------------------------------------

    def test_an_empty_week_sends_nothing_and_keeps_the_marker(self):
        last = self.now - timedelta(days=7)
        subscriber = self._subscriber(last_sent_at=last)

        out = _run()

        self.assertEqual(mail.outbox, [])
        subscriber.refresh_from_db()
        self.assertEqual(subscriber.last_sent_at, last)
        self.assertIn("empty=1", out)

    def test_a_second_run_that_week_sends_nothing(self):
        self._post("fresh-post", days_ago=1)
        subscriber = self._subscriber()

        _run()
        subscriber.refresh_from_db()
        self.assertIsNotNone(subscriber.last_sent_at)
        self._post("later-post", days_ago=0.5)
        _run()

        self.assertEqual(len(mail.outbox), 1)

    def test_an_early_fire_a_day_short_of_the_week_still_sends(self):
        self._post("fresh-post", days_ago=1)
        self._subscriber(last_sent_at=self.now - timedelta(days=6, hours=1))

        _run()

        self.assertEqual(len(mail.outbox), 1)

    def test_an_overlapping_run_exits_without_sending(self):
        self._post("fresh-post", days_ago=1)
        self._subscriber()
        cache.add(LOCK_KEY, "held", 60)

        out = _run()

        self.assertEqual(mail.outbox, [])
        self.assertIn("another run holds the lock", out)
        self.assertEqual(cache.get(LOCK_KEY), "held")

    def test_the_lock_is_released_after_a_run(self):
        _run()
        self.assertIsNone(cache.get(LOCK_KEY))

    def test_a_failed_send_gives_the_claim_back(self):
        self._post("fresh-post", days_ago=1)
        subscriber = self._subscriber()

        with mock.patch(
            "django.core.mail.EmailMultiAlternatives.send",
            side_effect=ConnectionError("smtp down"),
        ):
            out = _run()

        subscriber.refresh_from_db()
        self.assertIsNone(subscriber.last_sent_at)
        self.assertIn("failed=1", out)

    def test_the_soft_time_limit_stops_the_run_and_gives_the_claim_back(self):
        self._post("fresh-post", days_ago=1)
        subscriber = self._subscriber()

        with mock.patch(
            "django.core.mail.EmailMultiAlternatives.send",
            side_effect=SoftTimeLimitExceeded(),
        ):
            with self.assertRaises(SoftTimeLimitExceeded):
                _run()

        subscriber.refresh_from_db()
        self.assertIsNone(subscriber.last_sent_at)
        self.assertIsNone(cache.get(LOCK_KEY))

    def test_the_soft_time_limit_is_not_swallowed_while_building(self):
        self._subscriber()

        with mock.patch.object(
            newsletter_digest, "new_posts", side_effect=SoftTimeLimitExceeded()
        ):
            with self.assertRaises(SoftTimeLimitExceeded):
                _run()

    def test_a_reader_who_unsubscribes_mid_run_is_not_mailed(self):
        self._post("fresh-post", days_ago=1)
        subscriber = self._subscriber()
        real_new_posts = newsletter_digest.new_posts

        def unsubscribe_then_build(since, now):
            # The row was read with its chunk; it unsubscribes before its turn.
            BlogNewsletter.objects.filter(pk=subscriber.pk).update(is_active=False)
            return real_new_posts(since, now)

        with mock.patch.object(
            newsletter_digest, "new_posts", side_effect=unsubscribe_then_build
        ):
            out = _run()

        self.assertEqual(mail.outbox, [])
        self.assertIn("failed=0", out)

    def test_a_dry_run_sends_and_writes_nothing(self):
        self._post("fresh-post", days_ago=1)
        subscriber = self._subscriber()
        stale = BlogNewsletter.objects.create(email="stale@example.com")
        BlogNewsletter.objects.filter(pk=stale.pk).update(
            subscribed_at=self.now - timedelta(days=30)
        )

        out = _run("--dry-run")

        self.assertEqual(mail.outbox, [])
        subscriber.refresh_from_db()
        self.assertIsNone(subscriber.last_sent_at)
        self.assertTrue(BlogNewsletter.objects.filter(pk=stale.pk).exists())
        self.assertIn("would send=1", out)
        self.assertIn("would prune=1", out)

    # --- pruning unconfirmed signups --------------------------------------

    def test_prune_deletes_exactly_the_expired_unconfirmed_rows(self):
        expired = self.now - timedelta(seconds=NEWSLETTER_CONFIRM_MAX_AGE_SECONDS + 60)
        fresh = self.now - timedelta(hours=1)
        rows = {
            # Unconfirmed, link expired: pruned.
            "expired-link": dict(confirmed_at=None, confirmation_sent_at=expired),
            # Unconfirmed, no stamp (old endpoint, or a failed first send), old.
            "old-no-stamp": dict(confirmed_at=None, confirmation_sent_at=None),
            # Unconfirmed, link still valid: kept.
            "live-link": dict(confirmed_at=None, confirmation_sent_at=fresh),
            # Old row that was re-sent a link recently: kept.
            "old-resent": dict(confirmed_at=None, confirmation_sent_at=fresh),
            # Unconfirmed, no stamp, signed up just now: kept.
            "new-no-stamp": dict(confirmed_at=None, confirmation_sent_at=None),
            # Confirmed rows are never pruned, unsubscribed ones included.
            "confirmed": dict(confirmed_at=expired),
            "unsubscribed": dict(
                confirmed_at=expired, is_active=False, unsubscribed_at=expired
            ),
        }
        for name, fields in rows.items():
            BlogNewsletter.objects.create(email=f"{name}@example.com", **fields)
        BlogNewsletter.objects.exclude(email="new-no-stamp@example.com").update(
            subscribed_at=expired
        )

        out = _run()

        left = set(BlogNewsletter.objects.values_list("email", flat=True))
        self.assertEqual(
            left,
            {
                f"{name}@example.com"
                for name in (
                    "live-link",
                    "old-resent",
                    "new-no-stamp",
                    "confirmed",
                    "unsubscribed",
                )
            },
        )
        self.assertIn("pruned=2", out)


class NewsletterTaskTests(TestCase):
    def test_the_beat_entry_names_the_registered_task(self):
        entry = settings.CELERY_BEAT_SCHEDULE["blog-weekly-newsletter"]
        self.assertEqual(entry["task"], tasks.send_blog_weekly_newsletter.name)
        self.assertIsInstance(entry["schedule"], crontab)
        self.assertEqual(entry["schedule"].day_of_week, {1})  # monday
        # Not on top of the forum digest.
        forum = settings.CELERY_BEAT_SCHEDULE["forum-weekly-digest"]["schedule"]
        self.assertNotEqual(entry["schedule"].hour, forum.hour)

    def test_the_task_is_sized_for_a_cohort_and_retries_db_blips(self):
        task = tasks.send_blog_weekly_newsletter
        self.assertEqual(task.soft_time_limit, NEWSLETTER_SOFT_TIME_LIMIT)
        self.assertEqual(task.time_limit, NEWSLETTER_TIME_LIMIT)
        self.assertGreater(task.time_limit, task.soft_time_limit)
        self.assertIn(OperationalError, task.autoretry_for)
        self.assertEqual(task.max_retries, 3)
        # A redelivered batch would double-send: the default early ack stays.
        self.assertFalse(task.acks_late)

    def test_the_task_runs_the_command_and_logs_its_summary(self):
        def fake_command(name, stdout):
            stdout.write("[EMAIL] newsletter recipients=3 due=1 sent=1\n")

        with mock.patch(
            "django.core.management.call_command", side_effect=fake_command
        ) as command:
            with self.assertLogs("apps.blog.tasks", "INFO") as logs:
                tasks.send_blog_weekly_newsletter.apply()

        self.assertEqual(command.call_args.args, ("send_blog_newsletter",))
        self.assertTrue(any("recipients=3 due=1 sent=1" in m for m in logs.output))

    def test_the_task_re_enqueues_itself_after_the_soft_time_limit(self):
        with mock.patch(
            "django.core.management.call_command",
            side_effect=SoftTimeLimitExceeded(),
        ):
            with mock.patch.object(
                tasks.send_blog_weekly_newsletter, "apply_async"
            ) as again:
                tasks.send_blog_weekly_newsletter.apply()

        again.assert_called_once_with(countdown=NEWSLETTER_CONTINUATION_DELAY)
