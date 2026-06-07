import copy

from django.conf import settings

DEFAULTS = {
    "SPAM_BACKEND": "wagtail_forum.spam.heuristic.HeuristicSpamBackend",
    "TRUST_AUTOPUBLISH_LEVEL": 2,  # TrustLevel.MEMBER
    "SPAM_MAX_LINKS": 3,
    "SPAM_BANNED_WORDS": [],
    "TRUST_THRESHOLDS": {1: 1, 2: 5, 3: 50, 4: 200},  # trust_level -> min post_count
}


def get_setting(name):
    # deepcopy so a caller that mutates a returned list/dict (e.g. the empty
    # SPAM_BANNED_WORDS default) can't poison the shared DEFAULTS for later reads.
    value = getattr(settings, f"WAGTAILFORUM_{name}", DEFAULTS[name])
    return copy.deepcopy(value)
