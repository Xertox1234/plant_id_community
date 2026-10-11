"""The web summary panel's MIN_POSTS must equal SUMMARY_MIN_POSTS (todo 554).

``web/src/components/forum/ThreadSummaryPanel.tsx`` hides the "Summarize
thread" button below ``MIN_POSTS`` live posts, because every click on a
shorter thread spends a slot of the 30/h ``topic_summary`` bucket only to learn
``too_short``. It mirrored ``apps.forum_host.constants.SUMMARY_MIN_POSTS`` by a
comment alone. If the server's floor moves down, the web hides a button the
server would honour; if it moves up, every click below it is a wasted slot.
"""

import pathlib
import re

from apps.forum_host.constants import SUMMARY_MIN_POSTS

PANEL = (
    pathlib.Path(__file__).resolve().parents[4]
    / "web"
    / "src"
    / "components"
    / "forum"
    / "ThreadSummaryPanel.tsx"
)

MIN_POSTS_RE = re.compile(r"^const MIN_POSTS = (\d+);", re.MULTILINE)


def test_the_web_panel_mirrors_the_server_floor():
    matches = MIN_POSTS_RE.findall(PANEL.read_text(encoding="utf-8"))

    assert len(matches) == 1, f"expected one `const MIN_POSTS = <n>;` in {PANEL}"
    assert int(matches[0]) == SUMMARY_MIN_POSTS
