from django.conf import settings
from django.db import models
from django.db.models import Count


class Reaction(models.Model):
    LIKE = "like"
    LOVE = "love"
    HELPFUL = "helpful"
    THANKS = "thanks"
    REACTION_CHOICES = [
        (LIKE, "Like"),
        (LOVE, "Love"),
        (HELPFUL, "Helpful"),
        (THANKS, "Thanks"),
    ]

    post = models.ForeignKey(
        "wagtail_forum.Post", on_delete=models.CASCADE, related_name="reactions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wagtail_forum_reactions",
    )
    reaction_type = models.CharField(max_length=16, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user", "reaction_type"], name="uniq_forum_reaction"
            )
        ]

    @staticmethod
    def recount(post):
        """Recompute and persist a post's denormalized reaction_counts.

        Reaction types with a zero count are absent from the dict (not written
        as 0), so consumers must read it as ``post.reaction_counts.get(type, 0)``,
        never by direct key access.
        """
        counts = {
            row["reaction_type"]: row["n"]
            for row in Reaction.objects.filter(post=post)
            .values("reaction_type")
            .annotate(n=Count("id"))
        }
        post.reaction_counts = counts
        post.save(update_fields=["reaction_counts"])
        return counts

    def __str__(self):
        return f"{self.reaction_type} on post {self.post_id}"
