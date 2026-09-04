"""Query-hit logging for Wagtail's search-terms report (Wagtail quick wins, item 5).

``wagtail.contrib.search_promotions`` keeps a ``Query`` row per distinct
normalised search string and a ``QueryDailyHits`` counter per day; the admin
"Search terms" report and the promoted-results editor read from them. The
host ``SearchView`` (api.py) calls :func:`record_query_hit` from the package's
``record_search`` hook.

Two deliberate limits. Anonymous searches the CDN answers from its shared
cache (``PUBLIC_READ_CACHE_SECONDS``) never reach this origin and so are not
counted — the report undercounts repeat anonymous searches within that
window, which is the price of keeping those responses edge-cacheable. And a
failure here is logged and swallowed: the search result is the product, the
hit is telemetry.
"""

import logging

from django.db import transaction
from wagtail.contrib.search_promotions.models import Query

logger = logging.getLogger(__name__)

# Query.query_string is a bounded CharField; the forum view's own cap
# (SEARCH_MAX_QUERY_CHARS) is wider, so truncate here or Postgres raises.
_MAX_CHARS = Query._meta.get_field("query_string").max_length


def record_query_hit(query):
    """Count one hit for ``query``. Never raises."""
    try:
        # Savepoint so a DB error (missing table before migrate, a race on
        # get_or_create) can't leave the request's transaction aborted.
        with transaction.atomic():
            Query.get(query[:_MAX_CHARS]).add_hit()
    except Exception:
        logger.warning(
            "[ERROR] forum search hit not recorded for %r",
            query[:80],
            exc_info=True,
        )
