"""Follow/unfollow a topic (todo 253 slice 3, audit H2/H3)."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import TopicSubscription
from .views import _get_visible_topic, extend_schema

SUBSCRIPTION_SCHEMA = {
    "type": "object",
    "properties": {"subscribed": {"type": "boolean"}},
}


class TopicSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]
    versioning_class = None

    @extend_schema(
        responses={200: SUBSCRIPTION_SCHEMA},
        description="Subscribe the authenticated user to a topic (idempotent).",
    )
    def post(self, request, topic_id):
        # Visibility-gated: subscribing to a hidden/restricted topic 404s, no
        # existence leak (audit M6/M7).
        topic = _get_visible_topic(topic_id)
        TopicSubscription.subscribe(request.user, topic)
        return Response({"subscribed": True})

    @extend_schema(
        responses={200: SUBSCRIPTION_SCHEMA},
        description="Unsubscribe the authenticated user from a topic (idempotent).",
    )
    def delete(self, request, topic_id):
        # Deliberately NOT visibility-gated: this mutates only the caller's
        # own subscription row, so there's no existence-leak risk the way
        # there is on post(). Reusing _get_visible_topic here would 404 an
        # existing subscriber out of unsubscribing the moment their topic is
        # unpublished/restricted, stranding them subscribed until it comes
        # back (confirmed via repro, todo 253 slice 3 review).
        TopicSubscription.objects.filter(user=request.user, topic_id=topic_id).delete()
        return Response({"subscribed": False})
