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
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


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
    # N-of-K (todo 349). 1 is the original single-choice poll; a voter may
    # pick up to this many options in their ONE submission (a vote is still
    # final — see PollVoteView). Bounded on write to the option count by
    # TopicPollSerializer.validate, so it can never exceed what is offered.
    max_choices = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Poll(topic={self.topic_id}, question={self.question!r})"

    @property
    def is_closed(self):
        return self.closes_at is not None and timezone.now() >= self.closes_at

    def results(self):
        """`[{id, text, order, vote_count}, …]` in display order, plus a total.

        Aggregated from the vote rows on every read. `Count("votes")` folds
        into the options query, and the voter total rides the SAME query as a
        correlated subquery on every option row, so this is ONE query for the
        whole poll regardless of how many options or votes it has.

        `total_votes` is people who answered — distinct voters — not rows: in
        a multi-choice poll a voter contributes one row per option they
        picked, so the option counts can sum past it. Counted from the rows
        for single-choice polls too (rather than summing the option counts),
        so the number stays right even for a writer that bypasses
        PollVoteView's one-submission check (review of todo 349).
        """
        voters = (
            PollVote.objects.filter(poll=models.OuterRef("poll_id"))
            .order_by()
            .values("poll")
            .annotate(n=models.Count("user", distinct=True))
            .values("n")
        )
        options = list(
            self.options.annotate(
                vote_count=models.Count("votes"),
                voters=Coalesce(models.Subquery(voters), 0),
            ).order_by("order", "id")
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
            # Every option row carries the same poll-level subquery value;
            # a poll always has >= POLL_MIN_OPTIONS options, so [0] exists.
            "total_votes": options[0].voters if options else 0,
        }

    def serialize(self, my_vote_option_ids):
        """The one read shape shared by every poll-returning endpoint.

        `TopicDetailSerializer.get_poll` and `PollVoteView` both return this
        exact dict — it used to be hand-duplicated in both places (todo 320
        #3), which let them silently drift with only a 2-of-6-field test
        catching it. The caller resolves `my_vote_option_ids` and passes it in
        rather than this method querying for it: `get_poll` looks it up for
        the viewer (empty for anonymous — never leak anyone else's choice),
        while `PollVoteView` already has it from the rows it just wrote and
        would otherwise pay a redundant query for information it has in hand
        (todo 320 #4). A list even for single-choice polls (todo 349): one
        shape for both kinds, and "has voted" is simply a non-empty list.
        """
        results = self.results()
        return {
            "id": self.id,
            "question": self.question,
            "closes_at": self.closes_at,
            "is_closed": self.is_closed,
            "max_choices": self.max_choices,
            "options": results["options"],
            "total_votes": results["total_votes"],
            "my_vote_option_ids": list(my_vote_option_ids),
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
            # One row per (poll, user, option): a multi-choice ballot is N rows
            # (todo 349), and no user can count twice for the same option, so
            # Poll.results stays trustworthy without a stored counter. The
            # original (poll, user) constraint enforced "one submission per
            # voter" at the DB level; that invariant now lives in
            # PollVoteView, which takes a per-poll row lock and refuses a
            # second submission before writing (409), for single- and
            # multi-choice polls alike.
            models.UniqueConstraint(
                fields=["poll", "user", "option"], name="uniq_poll_vote_option"
            ),
        ]
        indexes = [
            # Results aggregate by option; the per-poll read is the hot path.
            models.Index(fields=["poll"]),
        ]

    def clean(self):
        # PollVoteView already filters `option` to `poll.options` before
        # creating (polls.py) — this documents and machine-checks the same
        # invariant for any OTHER writer (Django admin, a data migration, a
        # future second view) that doesn't go through that view. Deliberately
        # NOT wired into `save()`: Django's `full_clean()` also runs
        # `validate_constraints()`, which would pre-check
        # `uniq_poll_vote_option` against the DB and turn a duplicate row
        # into a `ValidationError` raised before `save()` — but
        # `PollVoteView.post` relies on catching the *DB's own*
        # `IntegrityError` from that constraint as its last-line 409 (see the
        # savepoint comment there). Calling `save()` here would change that
        # to an uncaught 500. Any writer that wants this check must call
        # `full_clean()` (or just `clean()`) itself — see
        # test_poll_vote_clean_rejects_option_from_another_poll.
        super().clean()
        if self.option_id and self.poll_id and self.option.poll_id != self.poll_id:
            raise ValidationError(
                {"option": _("This option does not belong to the poll being voted in.")}
            )

    def __str__(self):
        return f"PollVote(poll={self.poll_id}, user={self.user_id})"
