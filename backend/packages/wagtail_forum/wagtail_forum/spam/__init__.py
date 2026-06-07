from django.utils.module_loading import import_string

from ..conf import get_setting


def get_spam_backend():
    return import_string(get_setting("SPAM_BACKEND"))()
