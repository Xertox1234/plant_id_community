from collections.abc import Sequence

from rest_framework.pagination import CursorPagination


class ForumCursorPagination(CursorPagination):
    page_size = 20
    max_page_size = 100
    page_size_query_param = "page_size"
    # DRF accepts a field name or a sequence of them; declared wide here so
    # the subclasses' tuple orderings check against it.
    ordering: str | Sequence[str] = "-id"  # stable, unique cursor ordering


class ForumImageCursorPagination(ForumCursorPagination):
    # "My forum images" reuse list (personal-library view onto the forum's
    # image collection) reads as a thumbnail grid, not a feed — a slightly
    # larger page than the ForumCursorPagination default (20) suits that.
    page_size = 24


class TopicCursorPagination(ForumCursorPagination):
    # Pinned-first, then activity; -id is the unique tiebreak that keeps the
    # cursor deterministic when last_post_at ties. The list filters live=True,
    # and live topics always have a non-null last_post_at, so the cursor never
    # orders on NULL. DRF tracks the cursor position by the FIRST field, so
    # paging inside the (large) unpinned group falls back to DRF's
    # offset-from-position mechanism — fine at forum scale; revisit if a board
    # reaches tens of thousands of topics.
    ordering = ("-is_pinned", "-last_post_at", "-id")

    # Board-list sort options exposed to the web ThreadListPage <select>. Keys
    # are the exact values the select sends as ?sort=; each ordering keeps
    # -is_pinned first (pinned topics stay on top) and ends in a unique id
    # tiebreak so the cursor stays deterministic. "-post_count" is the UI label
    # for the model's reply_count field.
    # Scale note: only (board, -last_post_at) is indexed (Topic.Meta); the
    # created_at/view_count/reply_count sorts fall back to a sequential sort as a
    # board grows — the same accepted tradeoff as the default ordering's "revisit
    # if a board reaches tens of thousands of topics" note. Add composite indexes
    # then, not speculatively now.
    SORT_ORDERINGS = {
        "-last_activity_at": ("-is_pinned", "-last_post_at", "-id"),
        "-created_at": ("-is_pinned", "-created_at", "-id"),
        "created_at": ("-is_pinned", "created_at", "id"),
        "-view_count": ("-is_pinned", "-view_count", "-id"),
        "-post_count": ("-is_pinned", "-reply_count", "-id"),
    }

    def paginate_queryset(self, queryset, request, view=None):
        # The board the view resolved (TopicListView.get_queryset), so its
        # topics-per-page and default sort (todo 669) apply.
        self._board = getattr(view, "board", None)
        return super().paginate_queryset(queryset, request, view)

    def get_page_size(self, request):
        # A forum's `topics_per_page` (todo 669) replaces the site default;
        # an explicit ?page_size= still wins. 0 = the site default.
        board = getattr(self, "_board", None)
        per_page = getattr(board, "topics_per_page", 0) or 0
        if per_page and self.page_size_query_param not in request.query_params:
            return min(per_page, self.max_page_size)
        return super().get_page_size(request)

    def get_ordering(self, request, queryset, view):
        # An unknown or blank ?sort= falls back to the forum's default sort
        # (todo 669), then the default ordering — a bad value is ignored,
        # never a 500. Every page of the list resolves the same way, so
        # `next`/`previous` links keep the order.
        sort = request.query_params.get("sort", "")
        if sort not in self.SORT_ORDERINGS:
            sort = getattr(getattr(view, "board", None), "default_sort", "") or ""
        return self.SORT_ORDERINGS.get(sort, self.ordering)


class PostCursorPagination(ForumCursorPagination):
    # Posts read oldest-first (Post.Meta.ordering = ["created_at"]); id is the
    # unique tiebreak that keeps the cursor deterministic when created_at ties.
    ordering = ("created_at", "id")


class MessageCursorPagination(ForumCursorPagination):
    # Messages within a conversation read NEWEST-first (todo 339): a chat
    # thread opens on its latest page and pages OLDER, so the first cursor
    # page is what an inbox shows and what marks the thread read. Clients
    # render each page reversed. (Message.Meta.ordering stays oldest-first for
    # in-process iteration; the cursor applies its own ordering.)
    ordering = ("-created_at", "-id")


class ConversationCursorPagination(ForumCursorPagination):
    # Inbox order: most recent activity first (Conversation.last_message_at,
    # bumped on every send — todo 339), id as the unique tiebreak. Matches
    # Conversation.Meta.ordering. CursorPagination always re-applies its OWN
    # `ordering` via queryset.order_by(*ordering), so this must be spelled
    # out here rather than inherited (review finding on the original
    # -created_at version).
    ordering = ("-last_message_at", "-id")


class BookmarkCursorPagination(ForumCursorPagination):
    # Most-recently-bookmarked-first (todo 283 / M2) — "come back to this",
    # not the topic's own activity, so this deliberately does NOT reuse
    # TopicCursorPagination's ordering. `bookmarked_at` is a per-request
    # annotation (api/bookmarks.py's TopicBookmarkListView.get_queryset), not
    # a model column — DRF's CursorPagination re-applies `ordering` via
    # `queryset.order_by(*ordering)` itself, so this name must match the
    # annotation exactly. `-id` (Topic.id, unique) is the tiebreak.
    ordering = ("-bookmarked_at", "-id")
