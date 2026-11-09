"""RagAnswerReport survives its reporter's deletion (Plan B, task 2)."""

import pytest
from apps.forum_host.models import RagAnswer, RagAnswerReport
from django.contrib.auth import get_user_model

User = get_user_model()

pytestmark = pytest.mark.django_db


def test_reports_survive_reporter_deletion():
    asker = User.objects.create_user(username="asker")
    reporter = User.objects.create_user(username="rag_reporter")
    answer = RagAnswer.objects.create(
        user=asker, question="q", answer="a", sources=[], prompt_version=1
    )
    report = RagAnswerReport.objects.create(answer=answer, reporter=reporter)

    reporter.delete()

    report.refresh_from_db()
    assert report.reporter_id is None
    assert RagAnswerReport.objects.count() == 1
    assert RagAnswer.objects.filter(pk=answer.pk).exists()


def test_two_deleted_reporters_may_report_the_same_answer():
    asker = User.objects.create_user(username="asker2")
    r1 = User.objects.create_user(username="rr1")
    r2 = User.objects.create_user(username="rr2")
    answer = RagAnswer.objects.create(
        user=asker, question="q", answer="a", sources=[], prompt_version=1
    )
    RagAnswerReport.objects.create(answer=answer, reporter=r1)
    RagAnswerReport.objects.create(answer=answer, reporter=r2)

    r1.delete()
    r2.delete()

    assert RagAnswerReport.objects.filter(answer=answer, reporter=None).count() == 2
