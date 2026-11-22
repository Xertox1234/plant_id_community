"""THROWAWAY (todo 723): a deliberate critical CodeQL alert. DO NOT MERGE.

This module proves the code_scanning merge rule blocks a PR carrying a
critical alert. Nothing imports it and no URLconf includes it, so the view
is unreachable even if it were merged. The PR is closed unmerged.
"""

import subprocess

from django.http import HttpRequest, HttpResponse
from django.urls import path


def codeql_canary(request: HttpRequest) -> HttpResponse:
    # py/command-line-injection: user input reaches a shell.
    subprocess.call(request.GET["cmd"], shell=True)  # noqa: S602
    return HttpResponse("ok")


urlpatterns = [path("codeql-canary/", codeql_canary)]
