from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.response import Response

from ..models import ForumBoard, Topic
from .pagination import TopicCursorPagination
from .serializers import BoardSerializer, TopicListSerializer


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
