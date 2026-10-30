

### 2026-10-30 - Review round 2: non-blocking findings

- **Declined:** `/categories/` returns forums and links as separate lists, so a link the admin placed between two forums is shown after them. Each list keeps its own admin order. Interleaving needs a combined row shape, which is a contract change for a later slice.
- **Declined:** the change-type form falls back to `DEFAULT_NEW_TYPE` when `to_type` is missing. Admin-only (change permission and CSRF), and the form always posts the chosen radio.
- **Declined:** the click-count write catches `DatabaseError` without a savepoint. Only a hazard under `ATOMIC_REQUESTS`, which this project does not set.
- **Declined:** the link-go and throttled read and collapse views document no 429 in their schema. The throttles are host wrappers in forum_host; the package views are unthrottled on their own.
- **Declined:** a HEAD request also counts a click (DRF maps HEAD to GET). Counts are approximate by design and bounded per IP.
- **Declined:** `_visible_rows` keeps part of the old `_visible_boards` docstring. Cosmetic.
