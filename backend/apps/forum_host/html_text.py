"""HTML → plain text for the forum's AI features.

Shared by the composer assist (``compose_assist.py``) and the RAG blog chunker
(``rag_chunking.py``). Kept in its own dependency-free module so the chunker,
which is imported from ``AppConfig.ready()`` via ``vector_indexes.py``, does
not have to import the compose-assist view module (DRF, permissions, the
provider client) just for a regex.
"""

import html
import re

from django.utils.html import strip_tags

# Block boundaries in rich-text HTML. Substituted with a newline BEFORE tags are
# stripped: ``strip_tags`` deletes markup without putting anything in its place,
# so "<p>one</p><p>two</p>" flattens to "onetwo" and "<li>a</li><li>b</li>" to
# "ab" — every word fused across a block boundary (verified; the todo 275
# review's one high finding). That is the normal case for any multi-paragraph
# rich-text value, and for a citation-anchored index it would also produce
# fused, mis-anchored chunks. The package's own ``plain_text_excerpt`` avoids it
# only ACROSS StreamField blocks (it joins block parts with a space); inside a
# single rich-text block the boundary has to be reconstructed here.
BLOCK_BOUNDARY_RE = re.compile(
    r"(?i)</(?:p|div|li|ul|ol|h[1-6]|blockquote|pre)\s*>|<br\s*/?>"
)


def flatten_html(raw: str) -> str:
    """Flatten rich-text HTML to plain text, one line per block.

    ``strip_tags`` is not a sanitizer and is not used as one here — nothing in
    this path is rendered as HTML.

    Entities are unescaped after stripping, for two reasons: a value whose only
    content is ``<p>&nbsp;</p>`` would otherwise read as the truthy string
    ``"&nbsp;"`` (and buy an LLM call, or an embedding, for nothing), and an
    ``&amp;`` left encoded rides through a prompt into text the client shows
    verbatim.
    """
    if not raw:
        return ""
    text = html.unescape(strip_tags(BLOCK_BOUNDARY_RE.sub("\n", raw)))
    # Drop the blank lines the substitution leaves behind (nested blocks emit
    # several boundaries in a row) and normalise each surviving line.
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())
