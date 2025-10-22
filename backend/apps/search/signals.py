"""
Signal handlers for search functionality.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchVector
from machina.apps.forum_conversation.models import Topic, Post
from apps.plant_identification.models import PlantSpecies, PlantDiseaseDatabase
from apps.blog.models import BlogPostPage
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_search_preferences(sender, instance, created, **kwargs):
    """Create default search preferences when a new user is created."""
    if created:
        from .models import UserSearchPreferences
        UserSearchPreferences.objects.get_or_create(user=instance)


@receiver(post_save, sender=Topic)
def update_topic_search_vector(sender, instance, **kwargs):
    """Update search vector when a topic is saved."""
    try:
        # Update search vector for the topic
        Topic.objects.filter(id=instance.id).update(
            search_vector=SearchVector('subject', weight='A')
        )
        logger.debug(f"Updated search vector for topic {instance.id}")
    except Exception as e:
        logger.error(f"Failed to update search vector for topic {instance.id}: {str(e)}")


@receiver(post_save, sender=Post)
def update_post_search_vector(sender, instance, **kwargs):
    """Update search vector when a post is saved."""
    try:
        # Update search vector for the post
        Post.objects.filter(id=instance.id).update(
            search_vector=SearchVector('content', weight='B')
        )
        
        # Also update the topic's search vector if this is the first post
        if hasattr(instance, 'topic') and instance.topic:
            if instance.topic.first_post_id == instance.id:
                Topic.objects.filter(id=instance.topic.id).update(
                    search_vector=SearchVector('subject', weight='A') + 
                                 SearchVector('first_post__content', weight='B')
                )
        
        logger.debug(f"Updated search vector for post {instance.id}")
    except Exception as e:
        logger.error(f"Failed to update search vector for post {instance.id}: {str(e)}")


@receiver(post_save, sender=PlantSpecies)
def update_plant_search_vector(sender, instance, **kwargs):
    """Update search vector when a plant species is saved."""
    try:
        PlantSpecies.objects.filter(id=instance.id).update(
            search_vector=SearchVector('scientific_name', weight='A') + 
                         SearchVector('common_names', weight='A') + 
                         SearchVector('family', weight='B')
        )
        logger.debug(f"Updated search vector for plant species {instance.id}")
    except Exception as e:
        logger.error(f"Failed to update search vector for plant species {instance.id}: {str(e)}")


@receiver(post_save, sender=PlantDiseaseDatabase)
def update_disease_search_vector(sender, instance, **kwargs):
    """Update search vector when a plant disease is saved."""
    try:
        PlantDiseaseDatabase.objects.filter(id=instance.id).update(
            search_vector=SearchVector('disease_name', weight='A') + 
                         SearchVector('description', weight='B') + 
                         SearchVector('symptoms', weight='B')
        )
        logger.debug(f"Updated search vector for disease {instance.id}")
    except Exception as e:
        logger.error(f"Failed to update search vector for disease {instance.id}: {str(e)}")


@receiver(post_save, sender=BlogPostPage)
def update_blog_search_vector(sender, instance, **kwargs):
    """Update search vector when a blog post is saved."""
    try:
        # Only update for live pages
        if instance.live:
            BlogPostPage.objects.filter(id=instance.id).update(
                search_vector=SearchVector('title', weight='A') + 
                             SearchVector('intro', weight='B') + 
                             SearchVector('body', weight='C')
            )
            logger.debug(f"Updated search vector for blog post {instance.id}")
    except Exception as e:
        logger.error(f"Failed to update search vector for blog post {instance.id}: {str(e)}")


# Clear search vectors when content is deleted
@receiver(post_delete, sender=Topic)
def clear_topic_search_vector(sender, instance, **kwargs):
    """Clear search-related data when a topic is deleted."""
    logger.debug(f"Topic {instance.id} deleted, search vector automatically cleared")


@receiver(post_delete, sender=Post)
def clear_post_search_vector(sender, instance, **kwargs):
    """Clear search-related data when a post is deleted."""
    logger.debug(f"Post {instance.id} deleted, search vector automatically cleared")


@receiver(post_delete, sender=PlantSpecies)
def clear_plant_search_vector(sender, instance, **kwargs):
    """Clear search-related data when a plant species is deleted."""
    logger.debug(f"Plant species {instance.id} deleted, search vector automatically cleared")


@receiver(post_delete, sender=PlantDiseaseDatabase)
def clear_disease_search_vector(sender, instance, **kwargs):
    """Clear search-related data when a disease is deleted."""
    logger.debug(f"Disease {instance.id} deleted, search vector automatically cleared")


@receiver(post_delete, sender=BlogPostPage)
def clear_blog_search_vector(sender, instance, **kwargs):
    """Clear search-related data when a blog post is deleted."""
    logger.debug(f"Blog post {instance.id} deleted, search vector automatically cleared")