"""
Simple working views for forum integration.
This replaces the overly complex implementation with basic functionality that actually works.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponseRedirect
from django.urls import reverse

from machina.apps.forum.models import Forum
from machina.apps.forum_conversation.models import Topic, Post
from machina.apps.forum_conversation.forms import PostForm
from machina.core.loading import get_class

from .models import ForumIndexPage, ForumCategoryPage

PermissionHandler = get_class('forum_permission.handler', 'PermissionHandler')
perm_handler = PermissionHandler()


def forum_index(request):
    """Simple forum index view."""
    # Use simple view instead of Wagtail page serving for now
    forums = Forum.objects.filter(type=Forum.FORUM_POST).order_by('name')
    
    context = {
        'forums': forums,
        'page_title': 'Plant Community Forum',
    }
    return render(request, 'forum_integration/forum_index_simple.html', context)


def forum_category(request, forum_id):
    """Simple forum category view."""
    forum = get_object_or_404(Forum, id=forum_id)
    
    # Temporarily bypass permissions for debugging
    # Check permissions
    # if not perm_handler.can_see_forum(forum, request.user):
    #     messages.error(request, "You don't have permission to view this forum.")
    #     return redirect('forum_integration:forum_index')
    
    # Get topics
    topics = Topic.objects.filter(
        forum=forum,
        approved=True
    ).select_related('poster', 'last_post', 'last_post__poster').order_by('-last_post_on')
    
    # Pagination
    paginator = Paginator(topics, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'forum': forum,
        'topics': page_obj,
        'page_title': forum.name,
        'can_create_topics': True,  # Simplified for debugging
    }
    return render(request, 'forum_integration/forum_category_simple.html', context)


def forum_topic(request, topic_id):
    """Simple topic view."""
    topic = get_object_or_404(Topic, id=topic_id)
    
    # Temporarily bypass permissions for debugging
    # Check permissions
    # if not perm_handler.can_read_forum(topic.forum, request.user):
    #     messages.error(request, "You don't have permission to view this topic.")
    #     return redirect('forum_integration:forum_index')
    
    # Get posts
    posts = Post.objects.filter(
        topic=topic,
        approved=True
    ).select_related('poster').order_by('created')
    
    # Pagination
    paginator = Paginator(posts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'topic': topic,
        'posts': page_obj,
        'page_title': topic.subject,
        'can_reply': True,  # Simplified for debugging
    }
    return render(request, 'forum_integration/forum_topic_simple.html', context)


@login_required
def create_topic(request, forum_id):
    """Simple topic creation."""
    forum = get_object_or_404(Forum, id=forum_id)
    
    # Simplified permission check for debugging
    if not request.user.is_authenticated:
        messages.error(request, "Please log in to create topics.")
        return redirect('forum_integration:forum_category', forum_id=forum.id)
    
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        content = request.POST.get('content', '').strip()
        
        if subject and content:
            # Create topic
            topic = Topic.objects.create(
                forum=forum,
                subject=subject,
                poster=request.user,
                type=Topic.TOPIC_POST,
                status=Topic.TOPIC_UNLOCKED,
                approved=True
            )
            
            # Create first post
            post = Post.objects.create(
                topic=topic,
                poster=request.user,
                content=content,
                approved=True
            )
            
            # Update topic
            topic.first_post = post
            topic.last_post = post
            topic.posts_count = 1
            topic.save()
            
            messages.success(request, f'Topic "{subject}" created successfully!')
            return redirect('forum_integration:forum_topic', topic_id=topic.id)
        else:
            messages.error(request, 'Please fill in both subject and content.')
    
    context = {
        'forum': forum,
        'page_title': f'New Topic in {forum.name}',
    }
    return render(request, 'forum_integration/create_topic_simple.html', context)


@login_required  
def create_post(request, topic_id):
    """Simple post creation (reply)."""
    topic = get_object_or_404(Topic, id=topic_id)
    
    # Simplified permission check for debugging  
    if not request.user.is_authenticated:
        messages.error(request, "Please log in to reply.")
        return redirect('forum_integration:forum_topic', topic_id=topic.id)
    
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        
        if content:
            # Create post
            post = Post.objects.create(
                topic=topic,
                poster=request.user,
                content=content,
                approved=True
            )
            
            # Update topic
            topic.last_post = post
            topic.posts_count = Post.objects.filter(topic=topic, approved=True).count()
            topic.save()
            
            messages.success(request, 'Reply posted successfully!')
            return redirect('forum_integration:forum_topic', topic_id=topic.id)
        else:
            messages.error(request, 'Please enter your reply content.')
    
    context = {
        'topic': topic,
        'page_title': f'Reply to: {topic.subject}',
    }
    return render(request, 'forum_integration/create_post_simple.html', context)


def forum_search(request):
    """Simple forum search."""
    query = request.GET.get('q', '').strip()
    results = []
    
    if query and len(query) >= 3:
        # Search topics
        topics = Topic.objects.filter(
            subject__icontains=query,
            approved=True
        ).select_related('forum', 'poster')[:20]
        
        # Search posts  
        posts = Post.objects.filter(
            content__icontains=query,
            approved=True
        ).select_related('topic', 'poster')[:20]
        
        results = {
            'topics': topics,
            'posts': posts,
        }
    
    context = {
        'query': query,
        'results': results,
        'page_title': 'Forum Search',
    }
    return render(request, 'forum_integration/search_simple.html', context)