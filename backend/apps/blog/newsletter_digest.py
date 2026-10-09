"""The weekly blog newsletter: new posts, mailed to confirmed subscribers
(todo 409, slice B). `manage.py send_blog_newsletter` runs it; the beat
entry in settings fires that once a week.

Modelled on the forum digest (`wagtail_forum.digest` and its command):

- Only a confirmed, active row is mailed (`BlogNewsletter.is_subscribed`).
- A subscriber gets the live, public posts first published after their last
  newsletter, or after they confirmed if that is later. A resubscribed reader
  never receives the backlog from the weeks they were away.
- A week with no new posts sends nothing and leaves `last_sent_at` alone, so
  next week's email still covers them.
- Every email carries a signed unsubscribe link and List-Unsubscribe headers.
"""

import html
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.text import Truncator

from . import newsletter
from .constants import (
    NEWSLETTER_CONFIRM_MAX_AGE_SECONDS,
    NEWSLETTER_EXCERPT_WORDS,
    NEWSLETTER_MAX_POSTS,
    NEWSLETTER_WINDOW_DAYS,
)
from .models import BlogNewsletter, BlogPostPage

logger = logging.getLogger(__name__)

# A block's end or a line break separates words; `strip_tags` alone would run
# "<p>One.</p><p>Two</p>" together as "One.Two".
_BLOCK_BREAK = re.compile(
    r"<br\s*/?>|<hr\s*/?>|</(?:p|div|li|h[1-6]|blockquote|pre|ul|ol)\s*>",
    re.IGNORECASE,
)

HTML_TEMPLATE = "emails/newsletter_digest.html"
TEXT_TEMPLATE = "emails/newsletter_digest.txt"


@dataclass(frozen=True)
class DigestPost:
    title: str
    url: str
    excerpt: str
    published_at: datetime


def _site_url() -> str:
    # The web app's origin, as in feeds.py: posts live at /blog/{slug} there.
    return settings.SITE_URL.rstrip("/")


def recipients():
    """Confirmed subscribers who have not unsubscribed, oldest first."""
    return BlogNewsletter.objects.filter(
        is_active=True, confirmed_at__isnull=False
    ).order_by("pk")


def is_due(subscriber: BlogNewsletter, now: datetime) -> bool:
    """Never mailed, or last mailed a window ago less a day of jitter."""
    if subscriber.last_sent_at is None:
        return True
    return subscriber.last_sent_at <= now - timedelta(days=NEWSLETTER_WINDOW_DAYS - 1)


def since_for(subscriber: BlogNewsletter) -> datetime:
    """Posts after this are new to the subscriber.

    `last_sent_at` survives an unsubscribe, so a reader who comes back has an
    old one; their new `confirmed_at` is later and wins.
    """
    last = subscriber.last_sent_at
    return max(last, subscriber.confirmed_at) if last else subscriber.confirmed_at


def _excerpt(introduction: str) -> str:
    # `introduction` is rich text: drop the markup and decode its entities
    # here, so the HTML template escapes plain text exactly once.
    text = _BLOCK_BREAK.sub(" ", introduction or "")
    text = html.unescape(strip_tags(text)).strip()
    return Truncator(" ".join(text.split())).words(NEWSLETTER_EXCERPT_WORDS)


def new_posts(since: datetime, now: datetime) -> list[DigestPost]:
    """Live, public posts first published in (since, now], newest first.

    The upper bound is the run's own timestamp, the one stamped into
    `last_sent_at`: a post published while the run is sending belongs to
    next week's email, not to this one and then next week's as well.
    """
    posts = (
        BlogPostPage.objects.live()
        .public()
        .filter(first_published_at__gt=since, first_published_at__lte=now)
        .order_by("-first_published_at", "-id")[:NEWSLETTER_MAX_POSTS]
    )
    return [
        DigestPost(
            title=post.title,
            url=f"{_site_url()}/blog/{post.slug}",
            excerpt=_excerpt(post.introduction),
            published_at=post.first_published_at,
        )
        for post in posts
    ]


def render(
    subscriber: BlogNewsletter, posts: list[DigestPost], unsubscribe_url: str
) -> tuple[str, str, str]:
    """(subject, text body, html body)."""
    site_name = getattr(settings, "SITE_NAME", "Plant Community")
    context = {
        "site_name": site_name,
        "posts": posts,
        "blog_url": f"{_site_url()}/blog",
        "unsubscribe_url": unsubscribe_url,
    }
    if len(posts) == 1:
        subject = f"New on the {site_name} blog: {posts[0].title}"
    else:
        subject = f"{len(posts)} new posts on the {site_name} blog"
    return (
        subject,
        render_to_string(TEXT_TEMPLATE, context),
        render_to_string(HTML_TEMPLATE, context),
    )


def send(subscriber: BlogNewsletter, posts: list[DigestPost]) -> bool:
    """Send one newsletter. Never raises, except the worker's soft time
    limit, which stops the run rather than failing this send."""
    try:
        # One token for the footer link and the header, so both are the same.
        token = newsletter.make_unsubscribe_token(subscriber)
        subject, text, html_body = render(
            subscriber, posts, newsletter.unsubscribe_url(subscriber, token)
        )
        message = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=[subscriber.email],
            headers=newsletter.unsubscribe_headers(subscriber, token),
        )
        message.attach_alternative(html_body, "text/html")
        message.send()
    except SoftTimeLimitExceeded:
        raise
    except Exception:
        logger.exception(f"[EMAIL] newsletter failed for subscriber={subscriber.pk}")
        return False
    logger.info(
        f"[EMAIL] newsletter sent to subscriber={subscriber.pk} posts={len(posts)}"
    )
    return True


def stale_unconfirmed(now: datetime):
    """Rows that never confirmed and whose last link has expired.

    Signing up creates the row before the reader consents, so a scripted
    signup could pile them up. A confirmed row is never touched, an
    unsubscribed one included. A row may have no stamp at all: one from the
    old endpoint, or one whose only confirmation email failed and gave the
    stamp back; its age is then its signup time.
    """
    cutoff = now - timedelta(seconds=NEWSLETTER_CONFIRM_MAX_AGE_SECONDS)
    return BlogNewsletter.objects.filter(confirmed_at__isnull=True).filter(
        Q(confirmation_sent_at__lt=cutoff)
        | Q(confirmation_sent_at__isnull=True, subscribed_at__lt=cutoff)
    )
