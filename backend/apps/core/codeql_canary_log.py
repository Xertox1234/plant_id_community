"""THROWAWAY (todo 723): a client IP logged through log_safe_ip. DO NOT MERGE.

This module proves `py/clear-text-logging-sensitive-data` does not fire on an
IP logged through `log_safe_ip`, so the code_scanning merge rule does not block
such a PR. Nothing imports it and the PR is closed unmerged.
"""

import logging

from apps.core.utils.pii_safe_logging import log_safe_ip
from django.http import HttpRequest, HttpResponse
from django.urls import path

logger = logging.getLogger(__name__)


def codeql_canary_log(request: HttpRequest) -> HttpResponse:
    logger.warning(
        "[SECURITY] canary request from ip=%s",
        log_safe_ip(request.META.get("REMOTE_ADDR")),
    )
    return HttpResponse("ok")


urlpatterns = [path("codeql-canary-log/", codeql_canary_log)]
