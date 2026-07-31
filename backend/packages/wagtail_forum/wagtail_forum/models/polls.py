"""Per-topic polls (todo 283, audit M8).

A model trio rather than a ``ForumBodyBlock`` entry, deliberately. A poll is
not really content: its votes need their own rows, a unique constraint, and
aggregation at read time. A StreamField block can hold the *question* but has
nowhere to put the votes, and reshaping a block later means a data migration
across every stored body.

**Counts are never stored.** ``PollOption`` has no ``vote_count`` column;
results are aggregated from ``PollVote`` on read (see ``Poll.results``). A
denormalized counter is one bug away from disagreeing with the rows it
summarizes, and it is the thing a client would try to write.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Poll(models.Model):
    # OneToOne, not FK: one poll per topic, which lets TopicDetailView
    # `select_related("poll")` and pay ZERO extra queries for the common
    # poll-less topic. Same shape and same reason as
    # ForumIdentificationAttachment (audit M6).
    topic = models.OneToOneField(
        "wagtail_forum.Topic",
        on_delete=models.CASCADE,
        related_name="poll",
    )
    question = models.CharField(max_length=300)
    # Null means "open forever". A closed poll still renders its results — it
    # just stops accepting votes.
    closes_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Poll(topic={self.topic_id}, question={self.question!r})"

    @property
    def is_closed(self):
        return self.closes_at is not None and timezone.now() >= self.closes_at

    def results(self):
        """`[{id, text, order, vote_count}, …]` in display order, plus a total.

        Aggregated from the vote rows on every read. `Count("votes")` folds
        into the options query, so this is ONE query for the whole poll
        regardless of how many options or votes it has.
        """
        options = list(
            self.options.annotate(vote_count=models.Count("votes")).order_by(
                "order", "id"
            )
        )
        return {
            "options": [
                {
                    "id": option.id,
                    "text": option.text,
                    "order": option.order,
                    "vote_count": option.vote_count,
                }
                for option in options
            ],
            # Summed in Python from rows already fetched above — a second
            # aggregate query would buy nothing. Each vote is counted exactly
            # once because UniqueConstraint(poll, user) makes double-voting
            # impossible at the DB level.
            "total_votes": sum(option.vote_count for option in options),
        }


class PollOption(models.Model):
    poll = models.ForeignKey(
        Poll,
        on_delete=models.CASCADE,
        related_name="options",
    )
    text = models.CharField(max_length=200)
    # Author-defined display order. Explicit rather than relying on insertion
    # id, so a future reorder does not need a data migration.
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"PollOption(poll={self.poll_id}, text={self.text!r})"


class PollVote(models.Model):
    # `poll` is carried here rather than reached through `option` precisely so
    # the one-vote-per-user constraint below is expressible in a single table.
    # PollVoteView validates that the option actually belongs to this poll.
    poll = models.ForeignKey(
        Poll,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    option = models.ForeignKey(
        PollOption,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        # Follows the forum_topic_* convention set by
        # forum_topic_subscriptions / forum_topic_reads / forum_topic_bookmarks.
        related_name="forum_poll_votes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # One vote per user per poll. This is what makes Poll.results
            # trustworthy without a stored counter: the row count IS the
            # answer, and no user can inflate it. Single-choice by design for
            # the first cut — multi-choice would need this constraint widened
            # to include `option`, which is a different product decision.
            models.UniqueConstraint(fields=["poll", "user"], name="uniq_poll_vote"),
        ]
        indexes = [
            # Results aggregate by option; the per-poll read is the hot path.
            models.Index(fields=["poll"]),
        ]

    def __str__(self):
        return f"PollVote(poll={self.poll_id}, user={self.user_id})"
