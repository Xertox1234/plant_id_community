"""Send one sample of each live email family to named test inboxes (todo 626).

For checking how the real templates look in Gmail, Apple Mail and Outlook.
Every family goes through the template, and where one exists the send helper,
that the live path uses, with sample content in place of member data. Signed
links (verify, confirm, reset) point at a harmless sample page on SITE_URL
instead of carrying a real token.

Recipients come ONLY from --to; nothing is read from the user table to decide
who gets mail. Use approved test inboxes, never members.

    manage.py send_inbox_samples --to me+inbox@example.com
    manage.py send_inbox_samples --to a@example.com b@example.com --family digest
    manage.py send_inbox_samples --to me@example.com --dry-run
"""

from datetime import timedelta

from apps.blog import newsletter_digest
from apps.blog.models import BlogNewsletter
from apps.blog.newsletter import CONFIRM_HTML_TEMPLATE, CONFIRM_TEXT_TEMPLATE
from apps.blog.newsletter_digest import DigestPost
from apps.core.services.email_service import EmailService, EmailType
from apps.forum_host.notification_copy import email_content
from apps.users.account_links import password_reset_url
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.utils import timezone
from wagtail_forum.digest import Digest, DigestTopic, render_digest

User = get_user_model()

SUBJECT_PREFIX = "[Inbox check] "
# A handful of test inboxes, never a mailing list.
MAX_RECIPIENTS = 5

TOPIC_TITLE = "Yellow leaves on my fiddle leaf fig after repotting"
EXCERPT = (
    "Mine did exactly this after I moved it to a bigger pot. Let the top "
    "5 cm of soil dry out between waterings and keep it out of direct "
    "afternoon sun for a couple of weeks while the roots settle."
)
ACTOR = "Fern Gully"


def _site_url() -> str:
    return (getattr(settings, "SITE_URL", "") or "").rstrip("/")


def _sample_link(name: str) -> str:
    return f"{_site_url()}/inbox-check/{name}"


def _forum_copy(event: str) -> tuple[str, str]:
    copy = email_content(event, topic_title=TOPIC_TITLE, actor=ACTOR)
    if copy is None:
        raise CommandError(f"No forum email copy for {event!r}.")
    return copy


def _sample_user():
    # Unsaved: supplies names to the templates, never touches the database.
    return User(username="sample.gardener", first_name="Sam", last_name="Gardener")


class Command(BaseCommand):
    help = "Send one sample of each live email family to test inboxes (todo 626)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            nargs="+",
            required=True,
            help=f"Test inbox address(es), at most {MAX_RECIPIENTS}.",
        )
        parser.add_argument(
            "--family",
            action="append",
            help="Send only this family (repeatable). Default: all.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Render every family and report sizes; send nothing.",
        )

    def handle(self, *args, **options):
        recipients = options["to"]
        if len(recipients) > MAX_RECIPIENTS:
            raise CommandError(f"At most {MAX_RECIPIENTS} --to addresses.")
        if any("@" not in r for r in recipients):
            raise CommandError("Every --to value must be an email address.")

        families = self._families()
        wanted = options.get("family") or list(families)
        unknown = sorted(set(wanted) - set(families))
        if unknown:
            raise CommandError(
                f"Unknown family {', '.join(unknown)}; choose from "
                f"{', '.join(families)}."
            )

        self.dry_run = options["dry_run"]
        failures = 0
        for to in recipients:
            for name in wanted:
                ok, detail = families[name](to)
                failures += 0 if ok else 1
                style = self.style.SUCCESS if ok else self.style.ERROR
                self.stdout.write(
                    style(f"{name:<20} {'ok' if ok else 'FAILED':<7} {detail}")
                )
        if failures:
            raise CommandError(f"{failures} sample(s) failed.")

    def _families(self):
        return {
            "verification": self._verification,
            "welcome": self._welcome,
            "password_reset": self._password_reset,
            "signup_confirm": self._signup_confirm,
            "provider_linked": self._provider_linked,
            "forum_reply": self._forum_reply,
            "forum_mention": self._forum_mention,
            "forum_digest": self._forum_digest,
            "newsletter_confirm": self._newsletter_confirm,
            "newsletter_digest": self._newsletter_digest,
        }

    # -- senders -------------------------------------------------------------

    def _plain(self, to, subject, text, html, headers=None):
        """Send pre-rendered parts the way the newsletter and digest paths do."""
        if self.dry_run:
            return True, f"dry run: text {len(text)} B, html {len(html)} B"
        message = EmailMultiAlternatives(
            subject=SUBJECT_PREFIX + subject,
            body=text,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=[to],
            headers=headers or {},
        )
        message.attach_alternative(html, "text/html")
        sent = message.send()
        return bool(sent), "sent" if sent else "0 recipients (suppressed?)"

    def _transactional(self, to, subject, text, html):
        """Account mail: EmailService.send_transactional_email, as live."""
        if self.dry_run:
            return True, f"dry run: text {len(text)} B, html {len(html)} B"
        service = EmailService()
        ok = service.send_transactional_email(
            recipient=to,
            subject=SUBJECT_PREFIX + subject,
            message=text,
            html_message=html,
        )
        return ok, f"outcome={service.last_outcome}"

    def _templated(self, to, email_type, subject, template_name, context):
        """EmailService.send_email, as live: base context, click links,
        List-Unsubscribe. Preferences are skipped so a test inbox with forum
        mail turned off still gets its sample; suppression still applies."""
        service = EmailService()
        if self.dry_run:
            member = to if isinstance(to, User) else None
            full = {**context, **service._get_base_context(member, email_type)}
            html = render_to_string(f"emails/{template_name}.html", full)
            return True, f"dry run: html {len(html)} B"
        ok = service.send_email(
            email_type=email_type,
            recipient=to,
            subject=SUBJECT_PREFIX + subject,
            template_name=template_name,
            context=context,
            respect_preferences=False,
        )
        return ok, f"outcome={service.last_outcome}"

    # -- families ------------------------------------------------------------

    def _verification(self, to):
        site_name = EmailService().site_name
        context = {
            "site_name": site_name,
            "account": "sample.gardener",
            "verify_url": _sample_link("verify-email"),
        }
        return self._transactional(
            to,
            f"Confirm your email for {site_name}",
            render_to_string("emails/email_verification.txt", context),
            render_to_string("emails/email_verification.html", context),
        )

    def _provider_linked(self, to):
        site_name = EmailService().site_name
        context = {
            "site_name": site_name,
            "provider_name": "Google",
            "account": "sample.gardener",
            "reset_url": password_reset_url(),
        }
        return self._transactional(
            to,
            f"Google sign-in was connected to your {site_name} account",
            render_to_string("emails/provider_linked.txt", context),
            render_to_string("emails/provider_linked.html", context),
        )

    def _welcome(self, to):
        site_name = EmailService().site_name
        # The live welcome always has a member: the template reads `user`.
        # A test inbox with an account renders as that account; otherwise an
        # unsaved sample stands in (its tracking row is skipped, logged).
        member = User.objects.filter(email__iexact=to).first()
        if member is None:
            member = _sample_user()
            member.email = to
        return self._templated(
            member,
            EmailType.ACCOUNT_VERIFICATION,
            f"🎉 Welcome to {site_name}, Sam!",
            "welcome_email",
            {"user_first_name": "Sam"},
        )

    def _allauth(self, to, template, subject, extra):
        # allauth renders our HTML override and its own .txt part.
        context = {"user": _sample_user(), **extra}
        return self._plain(
            to,
            subject,
            render_to_string(f"account/email/{template}.txt", context),
            render_to_string(f"account/email/{template}.html", context),
        )

    def _password_reset(self, to):
        return self._allauth(
            to,
            "password_reset_key_message",
            "Password reset email",
            {
                "username": "sample.gardener",
                "password_reset_url": _sample_link("password-reset"),
            },
        )

    def _signup_confirm(self, to):
        return self._allauth(
            to,
            "email_confirmation_signup_message",
            "Please confirm your email address",
            {"activate_url": _sample_link("confirm-email")},
        )

    def _forum_reply(self, to):
        subject, _ = _forum_copy("reply_added")
        topic_url = f"{_site_url()}/forum/topics/1"
        return self._templated(
            to,
            EmailType.FORUM_REPLY,
            subject,
            "forum_reply",
            {
                "topic_title": TOPIC_TITLE,
                "author_name": ACTOR,
                "post_excerpt": EXCERPT,
                "topic_url": topic_url,
                "post_url": f"{topic_url}#post-2",
                "reply_count": 1,
            },
        )

    def _forum_mention(self, to):
        subject, line = _forum_copy("mention")
        topic_url = f"{_site_url()}/forum/topics/1"
        return self._templated(
            to,
            EmailType.FORUM_MENTION,
            subject,
            "forum_event",
            {
                "topic_title": TOPIC_TITLE,
                "author_name": ACTOR,
                "post_excerpt": EXCERPT,
                "topic_url": topic_url,
                "post_url": f"{topic_url}#post-2",
                "event_line": line,
            },
        )

    def _forum_digest(self, to):
        now = timezone.now()
        base = f"{_site_url()}/forum/topics"
        digest = Digest(
            user=_sample_user(),
            since=now - timedelta(days=7),
            display_name="Sam Gardener",
            watched=[
                DigestTopic(1, TOPIC_TITLE, f"{base}/1", "Plant care", 6, now, 3),
                DigestTopic(
                    2,
                    "Best soil mix for succulents?",
                    f"{base}/2",
                    "Soil & potting",
                    12,
                    now,
                    1,
                ),
            ],
            trending=[
                DigestTopic(
                    3,
                    "Show us your propagation station",
                    f"{base}/3",
                    "Show and tell",
                    24,
                    now,
                ),
                DigestTopic(
                    4,
                    "Fungus gnats: what finally worked for you",
                    f"{base}/4",
                    "Pests & diseases",
                    17,
                    now,
                ),
            ],
        )
        subject, text, html = render_digest(digest, _sample_link("unsubscribe"))
        return self._plain(to, str(subject), text, html)

    def _newsletter_confirm(self, to):
        site_name = getattr(settings, "SITE_NAME", "Houseplant MD")
        context = {
            "site_name": site_name,
            "confirm_url": _sample_link("newsletter-confirm"),
            "confirm_days": 7,
        }
        return self._plain(
            to,
            f"Confirm your {site_name} newsletter subscription",
            render_to_string(CONFIRM_TEXT_TEMPLATE, context),
            render_to_string(CONFIRM_HTML_TEMPLATE, context),
        )

    def _newsletter_digest(self, to):
        now = timezone.now()
        posts = [
            DigestPost(
                "Why your monstera isn't splitting its leaves",
                f"{_site_url()}/blog/monstera-fenestration",
                "Fenestration comes with maturity and light. Here is how to "
                "tell which one your plant is missing, and what to change.",
                now,
            ),
            DigestPost(
                "A beginner's guide to bottom watering",
                f"{_site_url()}/blog/bottom-watering",
                "Bottom watering keeps leaves dry and roots evenly moist. "
                "We cover when it helps and when it can hurt.",
                now - timedelta(days=2),
            ),
        ]
        subject, text, html = newsletter_digest.render(
            BlogNewsletter(email=to), posts, _sample_link("unsubscribe")
        )
        return self._plain(to, subject, text, html)
