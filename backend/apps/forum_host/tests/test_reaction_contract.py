"""L16 (todo 258): the web `REACTION_TYPES` literal must stay in sync with the
backend `Reaction.REACTION_CHOICES`. There is no OpenAPI->TS codegen in this
repo, so this is the cross-boundary DRIFT GUARD (not true single-sourcing): it
reads the committed web literal and fails CI if the two lists diverge, so neither
side can change the reaction set without the other.
"""

import re
from pathlib import Path

from django.conf import settings
from wagtail_forum.models import Reaction

# settings.BASE_DIR is the backend/ dir; its parent is the repo root.
WEB_REACTION_LITERAL = (
    Path(settings.BASE_DIR).parent / "web" / "src" / "utils" / "forumReactions.ts"
)


def test_web_reaction_types_match_backend_choices():
    assert (
        WEB_REACTION_LITERAL.exists()
    ), f"web reaction literal not found at {WEB_REACTION_LITERAL} (moved/renamed?)"
    source = WEB_REACTION_LITERAL.read_text()
    match = re.search(r"REACTION_TYPES\s*=\s*\[([^\]]*)\]", source)
    assert match, "could not find `REACTION_TYPES = [...]` in the web literal"
    web_types = re.findall(r"'([^']+)'", match.group(1))
    backend_types = [choice[0] for choice in Reaction.REACTION_CHOICES]
    assert web_types == backend_types, (
        f"web REACTION_TYPES {web_types} != backend REACTION_CHOICES "
        f"{backend_types} — update both (audit L16)."
    )
