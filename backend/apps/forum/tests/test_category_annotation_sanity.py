"""One-shot sanity check: Count+Sum on same relation must not multiply."""
import pytest
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce

from apps.forum.tests.factories import CategoryFactory, ThreadFactory


@pytest.mark.django_db
def test_category_annotation_matches_direct_queries():
    from apps.forum.models import Category, Thread

    cat = CategoryFactory.create()
    ThreadFactory.create(category=cat, is_active=True, post_count=5)
    ThreadFactory.create(category=cat, is_active=True, post_count=7)
    ThreadFactory.create(category=cat, is_active=True, post_count=2)
    ThreadFactory.create(category=cat, is_active=False, post_count=99)  # excluded

    annotated = Category.objects.filter(pk=cat.pk).annotate(
        annotated_thread_count=Count('threads', filter=Q(threads__is_active=True), distinct=True),
        annotated_post_count=Coalesce(Sum('threads__post_count', filter=Q(threads__is_active=True)), 0),
    ).get()

    assert annotated.annotated_thread_count == 3, (
        f"Expected 3 active threads, got {annotated.annotated_thread_count} — JOIN multiplication?"
    )
    assert annotated.annotated_post_count == 14, (
        f"Expected post_count=14 (5+7+2), got {annotated.annotated_post_count} — JOIN multiplication?"
    )
