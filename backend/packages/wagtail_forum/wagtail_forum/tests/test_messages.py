import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from wagtail_forum.models import Conversation, Message

User = get_user_model()


@pytest.mark.django_db
def test_between_creates_a_conversation():
    a = User.objects.create_user(username="ada")
    b = User.objects.create_user(username="babbage")

    conversation = Conversation.between(a, b)

    assert conversation.pk is not None
    assert {conversation.participant_a_id, conversation.participant_b_id} == {
        a.pk,
        b.pk,
    }


@pytest.mark.django_db
def test_between_is_symmetric_and_idempotent():
    """between(a, b) and between(b, a) must resolve to the SAME row —
    participants are canonicalized by pk regardless of call order."""
    a = User.objects.create_user(username="ada2")
    b = User.objects.create_user(username="babbage2")

    forward = Conversation.between(a, b)
    backward = Conversation.between(b, a)

    assert forward.pk == backward.pk
    assert Conversation.objects.count() == 1


@pytest.mark.django_db
def test_self_conversation_is_rejected():
    a = User.objects.create_user(username="ada3")

    with pytest.raises(IntegrityError):
        Conversation.objects.create(participant_a=a, participant_b=a)


@pytest.mark.django_db
def test_other_participant_id_resolves_for_either_side():
    a = User.objects.create_user(username="ada4")
    b = User.objects.create_user(username="babbage4")
    conversation = Conversation.between(a, b)

    assert conversation.other_participant_id(a) == b.pk
    assert conversation.other_participant_id(b) == a.pk


@pytest.mark.django_db
def test_messages_ordered_oldest_first():
    a = User.objects.create_user(username="ada5")
    b = User.objects.create_user(username="babbage5")
    conversation = Conversation.between(a, b)
    first = Message.objects.create(conversation=conversation, sender=a, body="hi")
    second = Message.objects.create(conversation=conversation, sender=b, body="hello")

    assert list(conversation.messages.all()) == [first, second]
