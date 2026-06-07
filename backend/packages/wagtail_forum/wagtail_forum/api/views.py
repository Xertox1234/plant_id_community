from rest_framework import generics
from rest_framework.response import Response

from ..models import ForumBoard
from .serializers import BoardSerializer


class BoardListView(generics.ListAPIView):
    serializer_class = BoardSerializer
    pagination_class = None  # boards are few; return a flat results list
    versioning_class = None  # host may configure NamespaceVersioning globally; opt out

    def get_queryset(self):
        return ForumBoard.objects.live().order_by("path")

    def list(self, request, *args, **kwargs):
        data = self.get_serializer(self.get_queryset(), many=True).data
        return Response({"results": data})
