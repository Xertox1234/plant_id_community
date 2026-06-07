import logging

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..blocks import ForumBodyBlock
from ..models import ForumBoard, Post, Topic
from ..workflow import submit_for_moderation
from .idempotency import idempotency_cache_key, remember, replay
from .pagination import TopicCursorPagination
from .serializers import BoardSerializer, TopicCreateSerializer, TopicListSerializer

logger = logging.getLogger("wagtail_forum")


class BoardListView(generics.ListAPIView):
    serializer_class = BoardSerializer
    pagination_class = None  # boards are few; return a flat results list
    versioning_class = None  # host may configure NamespaceVersioning globally; opt out

    def get_queryset(self):
        return ForumBoard.objects.live().order_by("path")

    def list(self, request, *args, **kwargs):
        data = self.get_serializer(self.get_queryset(), many=True).data
        return Response({"results": data})


class TopicListView(generics.ListAPIView):
    serializer_class = TopicListSerializer
    pagination_class = TopicCursorPagination
    versioning_class = None

    def get_queryset(self):
        board = get_object_or_404(ForumBoard.objects.live(), slug=self.kwargs["slug"])
        return (
            Topic.objects.filter(board=board, live=True)
            .select_related("author", "last_post_author")
            .order_by("-last_post_at", "-id")
        )


class TopicCreateView(APIView):
    permission_classes = [IsAuthenticated]
    versioning_class = None

    def post(self, request, slug):
        cache_key = idempotency_cache_key(request)
        cached = replay(cache_key)
        if cached is not None:
            return Response(cached, status=http_status.HTTP_200_OK)

        serializer = TopicCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        board = get_object_or_404(ForumBoard.objects.live(), slug=slug)

        # 1) Create the draft topic + opening post atomically (born live=False).
        try:
            with transaction.atomic():
                topic = Topic(
                    board=board,
                    title=serializer.validated_data["title"],
                    slug=serializer.validated_data["slug"],
                    author=request.user,
                    live=False,
                )
                topic.save()
                opening = Post(
                    topic=topic,
                    author=request.user,
                    is_opening_post=True,
                    body=ForumBodyBlock().to_python(serializer.validated_data["body"]),
                    live=False,
                )
                opening.save()
        except IntegrityError:
            return Response(
                {"detail": "A topic with this slug already exists in this board."},
                status=http_status.HTTP_409_CONFLICT,
            )

        # 2) Route through moderation OUTSIDE the creation transaction. A pluggable
        # spam backend can raise; the draft is already live=False, so never 500 —
        # leave it as a pending draft for a moderator.
        moderation_failed = False
        try:
            status = submit_for_moderation(opening, request.user)
        except Exception:
            logger.exception(
                "[ERROR] submit_for_moderation failed for post %s; left as draft",
                opening.pk,
            )
            status = "pending"
            moderation_failed = True

        result = {"id": topic.id, "slug": topic.slug, "status": status}
        # Don't cache a backend-crash outcome, so a client retry can re-attempt.
        # A legitimate spam-"pending" IS cached (idempotent — no duplicate draft).
        if not moderation_failed:
            remember(cache_key, result)
        return Response(result, status=http_status.HTTP_201_CREATED)
