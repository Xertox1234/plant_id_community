"""The six legal documents carry the policy version the server stamps at sign-up."""

import pytest
from apps.users.constants import LEGAL_POLICY_VERSION
from django.conf import settings

LEGAL_DIR = settings.BASE_DIR.parent / "web" / "src" / "content" / "legal"
DOCUMENTS = [
    f"{doc}.{lang}.md" for doc in ("privacy", "terms") for lang in ("en", "fr", "es")
]


@pytest.mark.parametrize("name", DOCUMENTS)
def test_documents_carry_current_version(name):
    text = (LEGAL_DIR / name).read_text(encoding="utf-8")
    assert f"<!-- version: {LEGAL_POLICY_VERSION} -->" in text
