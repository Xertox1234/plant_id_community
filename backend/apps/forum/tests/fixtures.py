"""
Reusable test fixtures for forum testing.

Provides pre-configured test data scenarios for common testing situations.
"""

from typing import Dict, Any
from .factories import (
    UserFactory,
    CategoryFactory,
    ThreadFactory,
    PostFactory,
    AttachmentFactory,
    ReactionFactory,
)


class ForumTestFixtures:
    """
    Collection of reusable test fixtures.

    Provides complete test scenarios with realistic data.
    """

    @staticmethod
    def create_basic_forum() -> Dict[str, Any]:
        """
        Create a basic forum with minimal content.

        Returns:
            Dict containing:
            - category: Main category
            - threads: List of 3 threads
            - users: List of 3 users
        """
        users = UserFactory.create_batch(3)
        category = CategoryFactory.create(name="General Discussion")

        threads = [
            ThreadFactory.create(
                title=f"Thread {i+1}",
                author=users[i % len(users)],
                category=category
            )
            for i in range(3)
        ]

        # Add first posts to threads
        for thread in threads:
            PostFactory.create(
                thread=thread,
                author=thread.author,
                is_first_post=True
            )

        return {
            'category': category,
            'threads': threads,
            'users': users,
        }

    @staticmethod
    def create_forum_with_hierarchy() -> Dict[str, Any]:
        """
        Create a forum with category hierarchy.

        Returns:
            Dict containing:
            - parent_category: Top-level category
            - child_categories: List of 2 child categories
            - threads: Threads distributed across categories
        """
        parent = CategoryFactory.create(name="Plants")
        children = [
            CategoryFactory.create(name="Indoor Plants", parent=parent),
            CategoryFactory.create(name="Outdoor Plants", parent=parent),
        ]

        users = UserFactory.create_batch(5)
        threads = []

        # Create threads in each child category
        for child in children:
            for i in range(3):
                thread = ThreadFactory.create(
                    title=f"{child.name} Thread {i+1}",
                    author=users[i % len(users)],
                    category=child
                )
                PostFactory.create(
                    thread=thread,
                    author=thread.author,
                    is_first_post=True
                )
                threads.append(thread)

        return {
            'parent_category': parent,
            'child_categories': children,
            'threads': threads,
            'users': users,
        }

    @staticmethod
    def create_active_discussion() -> Dict[str, Any]:
        """
        Create an active discussion with multiple posts and reactions.

        Returns:
            Dict containing:
            - thread: Discussion thread
            - posts: List of 10 posts
            - users: Participants in discussion
            - reactions: Mixed reactions on posts
        """
        users = UserFactory.create_batch(5)
        category = CategoryFactory.create(name="Plant Care Questions")

        thread = ThreadFactory.create(
            title="Why are my leaves yellowing?",
            author=users[0],
            category=category,
            excerpt="My pothos leaves have been turning yellow lately..."
        )

        # Create initial post
        first_post = PostFactory.create(
            thread=thread,
            author=users[0],
            content_raw="My pothos leaves have been turning yellow. I water once a week. Help!",
            is_first_post=True
        )

        # Create reply posts
        posts = [first_post]
        for i in range(9):
            post = PostFactory.create(
                thread=thread,
                author=users[(i+1) % len(users)],
                content_raw=f"Reply {i+1}: Here's my advice based on my experience..."
            )
            posts.append(post)

        # Add varied reactions
        reaction_data = {}
        for post in posts:
            reaction_data[post.id] = ReactionFactory.create_mixed_reactions(post=post)

        # Update thread statistics
        thread.post_count = len(posts)
        thread.save()

        return {
            'thread': thread,
            'posts': posts,
            'users': users,
            'reactions': reaction_data,
            'category': category,
        }

    @staticmethod
    def create_forum_with_attachments() -> Dict[str, Any]:
        """
        Create a thread with posts containing image attachments.

        Returns:
            Dict containing:
            - thread: Thread with images
            - posts: Posts with 1-3 images each
            - attachments: All attachments
        """
        user = UserFactory.create(username='photographer')
        category = CategoryFactory.create(name="Plant Identification")

        thread = ThreadFactory.create(
            title="Can you identify this plant?",
            author=user,
            category=category
        )

        # First post with 3 images
        first_post = PostFactory.create(
            thread=thread,
            author=user,
            content_raw="Found this beautiful plant. Here are photos from different angles.",
            is_first_post=True
        )
        first_post_attachments = AttachmentFactory.create_batch(3, post=first_post)

        # Reply with 1 image
        reply_post = PostFactory.create(
            thread=thread,
            author=UserFactory.create(),
            content_raw="Looks like a Monstera! Here's a comparison photo."
        )
        reply_attachments = AttachmentFactory.create_batch(1, post=reply_post)

        all_attachments = first_post_attachments + reply_attachments

        return {
            'thread': thread,
            'posts': [first_post, reply_post],
            'attachments': all_attachments,
            'user': user,
            'category': category,
        }

    @staticmethod
    def create_moderation_scenario() -> Dict[str, Any]:
        """
        Create a scenario requiring moderation (flagged content, spam).

        Returns:
            Dict containing:
            - threads: Mix of normal and flagged threads
            - spam_user: User with spam posts
            - moderator: User with moderation permissions
        """
        normal_users = UserFactory.create_batch(3)
        spam_user = UserFactory.create(username='spammer')
        moderator = UserFactory.create(username='moderator', is_staff=True)

        category = CategoryFactory.create(name="General")

        # Normal threads
        normal_threads = [
            ThreadFactory.create(
                title=f"Normal Thread {i+1}",
                author=normal_users[i % len(normal_users)],
                category=category
            )
            for i in range(3)
        ]

        # Spam threads (locked/inactive)
        spam_threads = [
            ThreadFactory.create(
                title=f"BUY CHEAP FERTILIZER!!! {i+1}",
                author=spam_user,
                category=category,
                is_locked=True,
                is_active=False
            )
            for i in range(2)
        ]

        # Add posts to all threads
        for thread in normal_threads + spam_threads:
            PostFactory.create(
                thread=thread,
                author=thread.author,
                is_first_post=True
            )

        return {
            'normal_threads': normal_threads,
            'spam_threads': spam_threads,
            'spam_user': spam_user,
            'moderator': moderator,
            'category': category,
        }

    @staticmethod
    def create_user_progression_scenario() -> Dict[str, Any]:
        """
        Create users at different trust levels for testing progression.

        Returns:
            Dict containing users at each trust level
        """
        from apps.forum.constants import (
            TRUST_LEVEL_NEW,
            TRUST_LEVEL_BASIC,
            TRUST_LEVEL_TRUSTED,
            TRUST_LEVEL_VETERAN,
            TRUST_LEVEL_EXPERT,
        )

        users = {
            'new': UserFactory.create(username='newbie'),
            'basic': UserFactory.create(username='basic_user'),
            'trusted': UserFactory.create(username='trusted_user'),
            'veteran': UserFactory.create(username='veteran_user'),
            'expert': UserFactory.create(username='expert_user', is_staff=True),
        }

        # Note: Trust level field will be added to User model in Phase 4
        # For now, this is a placeholder for future use

        category = CategoryFactory.create(name="Community")

        # Create threads/posts by each user type
        threads = {}
        for level, user in users.items():
            thread = ThreadFactory.create(
                title=f"Thread by {level} user",
                author=user,
                category=category
            )
            PostFactory.create(
                thread=thread,
                author=user,
                is_first_post=True
            )
            threads[level] = thread

        return {
            'users': users,
            'threads': threads,
            'category': category,
        }

    @staticmethod
    def create_search_test_data() -> Dict[str, Any]:
        """
        Create diverse content for testing search functionality.

        Returns:
            Dict containing threads with varied content
        """
        users = UserFactory.create_batch(3)
        categories = CategoryFactory.create_batch(2)

        # Create threads with specific searchable content
        threads = {
            'pothos': ThreadFactory.create(
                title="Pothos Care Guide",
                author=users[0],
                category=categories[0],
                excerpt="Everything about pothos plant care"
            ),
            'monstera': ThreadFactory.create(
                title="Monstera Deliciosa Tips",
                author=users[1],
                category=categories[0],
                excerpt="Growing and maintaining monstera plants"
            ),
            'yellowing': ThreadFactory.create(
                title="Yellow Leaves Problem",
                author=users[2],
                category=categories[1],
                excerpt="Why are my plant leaves turning yellow?"
            ),
        }

        # Add posts with searchable content
        for key, thread in threads.items():
            PostFactory.create(
                thread=thread,
                author=thread.author,
                content_raw=f"Detailed information about {key}",
                is_first_post=True
            )

        return {
            'threads': threads,
            'users': users,
            'categories': categories,
        }
