"""Tombstone log for deleted topics (Issue 6 — delta-sync completeness).

When a topic is hard-deleted its row vanishes; a mobile client polling
/sync/?since=<last_seen> would never learn it is gone and would keep
showing a stale entry.  This lightweight append-only log lets SyncView
return the ids of topics removed since the client's last poll so the
client can evict them from its local cache.

Design notes:
- No FK to Topic — the topic is gone by the time this row is read.
- board_id is stored for clients that partition their cache by board.
- deleted_at is indexed; old rows are pruned by the
  `prune_forum_tombstones` management command (retention controlled via
  WAGTAILFORUM_SYNC_TOMBSTONE_RETENTION_DAYS, default 30 days).
"""

from django.db import models
from django.utils import timezone


class TopicDeletedLog(models.Model):
    topic_id = models.IntegerField(db_index=True)
    board_id = models.IntegerField(db_index=True)
    deleted_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        app_label = "wagtail_forum"
        ordering = ["deleted_at"]
        indexes = [
            models.Index(fields=["deleted_at"], name="wf_tombstone_deleted_at_idx"),
        ]
