"""Blog Celery tasks: the newsletter task relays its command's output once."""

from unittest.mock import patch

import pytest

# The relay loop's own format string: it marks exactly the relayed lines.
RELAY_FORMAT = "%s (task=%s)"


@pytest.mark.django_db
def test_weekly_newsletter_relays_the_real_command_output_with_one_prefix():
    """Todo 573 item 4 (as todo 392 does for the forum digest): the relay
    loop adds no prefix because `send_blog_newsletter` already writes
    `[EMAIL] ...`. Run the REAL command through the task and read what the
    task logs: exactly one `[EMAIL]` per relayed line.

    The run lock is cleared first and the summary line is required, so a
    leaked lock (which relays only its "holds the lock" line) fails.
    """
    from apps.blog import tasks
    from apps.blog.management.commands.send_blog_newsletter import LOCK_KEY
    from django.core.cache import cache

    cache.delete(LOCK_KEY)
    with patch.object(tasks.logger, "info") as info:
        tasks.send_blog_weekly_newsletter.apply()

    relayed = [c.args[1] for c in info.call_args_list if c.args[0] == RELAY_FORMAT]
    assert any("recipients=" in line for line in relayed), relayed
    for line in relayed:
        assert line.startswith("[EMAIL] "), line
        assert line.count("[EMAIL]") == 1, line
