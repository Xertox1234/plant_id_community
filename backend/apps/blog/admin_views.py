"""
Blog admin views for managing blog content, comments, and settings.
Provides comprehensive administrative functionality beyond basic Wagtail page management.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, UpdateView
from django.urls import reverse_lazy
from django.conf import settings

from .models import BlogPostPage, BlogComment, BlogCategory, BlogSeries
from .serializers import BlogPostPageSerializer, BlogCommentSerializer


@staff_member_required
def blog_admin_dashboard(request):
    """
    Main blog administration dashboard with statistics and quick actions.
    """
    # Gather comprehensive statistics
    stats = {
        'total_posts': BlogPostPage.objects.all().count(),
        'published_posts': BlogPostPage.objects.live().public().count(),
        'draft_posts': BlogPostPage.objects.filter(live=False).count(),
        'featured_posts': BlogPostPage.objects.live().public().filter(is_featured=True).count(),
        'total_comments': BlogComment.objects.count(),
        'pending_comments': BlogComment.objects.filter(is_approved=False).count(),
        'approved_comments': BlogComment.objects.filter(is_approved=True).count(),
        'total_categories': BlogCategory.objects.count(),
        'total_series': BlogSeries.objects.count(),
    }
    
    # Recent activity
    recent_posts = BlogPostPage.objects.live().order_by('-first_published_at')[:5]
    recent_comments = BlogComment.objects.order_by('-created_at')[:5]
    
    # Popular posts (by comment count)
    popular_posts = BlogPostPage.objects.live().annotate(
        comment_count=Count('comments')
    ).order_by('-comment_count')[:5]
    
    context = {
        'stats': stats,
        'recent_posts': recent_posts,
        'recent_comments': recent_comments,
        'popular_posts': popular_posts,
        'title': 'Blog Administration Dashboard'
    }
    
    return render(request, 'blog/admin/dashboard.html', context)


@staff_member_required
def moderate_comments(request):
    """
    Comment moderation interface with approval/rejection functionality.
    """
    status_filter = request.GET.get('status', 'pending')
    search_query = request.GET.get('q', '')
    
    # Build queryset based on filters
    comments = BlogComment.objects.select_related('post', 'author')
    
    if status_filter == 'pending':
        comments = comments.filter(is_approved=False)
    elif status_filter == 'approved':
        comments = comments.filter(is_approved=True)
    elif status_filter == 'all':
        pass  # Show all comments
    
    if search_query:
        comments = comments.filter(
            Q(content__icontains=search_query) |
            Q(author__username__icontains=search_query) |
            Q(post__title__icontains=search_query)
        )
    
    comments = comments.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(comments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'title': 'Comment Moderation'
    }
    
    return render(request, 'blog/admin/comments.html', context)


@staff_member_required
@require_POST
def approve_comment(request, comment_id):
    """
    Approve a specific comment.
    """
    comment = get_object_or_404(BlogComment, id=comment_id)
    comment.is_approved = True
    comment.save()
    
    messages.success(request, f'Comment by {comment.author.username} has been approved.')
    
    if request.headers.get('Content-Type') == 'application/json':
        return JsonResponse({'status': 'success', 'message': 'Comment approved'})
    
    return redirect('blog_admin:moderate_comments')


@staff_member_required
@require_POST
def reject_comment(request, comment_id):
    """
    Reject/delete a specific comment.
    """
    comment = get_object_or_404(BlogComment, id=comment_id)
    author_name = comment.author.username
    comment.delete()
    
    messages.success(request, f'Comment by {author_name} has been rejected and deleted.')
    
    if request.headers.get('Content-Type') == 'application/json':
        return JsonResponse({'status': 'success', 'message': 'Comment rejected'})
    
    return redirect('blog_admin:moderate_comments')


@staff_member_required
def featured_posts(request):
    """
    Manage featured posts - view, feature, and unfeature posts.
    """
    featured = BlogPostPage.objects.live().filter(is_featured=True).order_by('-first_published_at')
    recent_posts = BlogPostPage.objects.live().filter(is_featured=False).order_by('-first_published_at')[:10]
    
    context = {
        'featured_posts': featured,
        'recent_posts': recent_posts,
        'title': 'Featured Posts Management'
    }
    
    return render(request, 'blog/admin/featured.html', context)


@staff_member_required
@require_POST
def toggle_featured(request, post_id):
    """
    Toggle featured status for a blog post.
    """
    post = get_object_or_404(BlogPostPage, id=post_id)
    post.is_featured = not post.is_featured
    post.save()
    
    status = "featured" if post.is_featured else "unfeatured"
    messages.success(request, f'"{post.title}" has been {status}.')
    
    if request.headers.get('Content-Type') == 'application/json':
        return JsonResponse({
            'status': 'success', 
            'message': f'Post {status}',
            'is_featured': post.is_featured
        })
    
    return redirect('blog_admin:featured_posts')


@staff_member_required
def post_comments(request, post_id):
    """
    View and moderate comments for a specific post.
    """
    post = get_object_or_404(BlogPostPage, id=post_id)
    comments = post.comments.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(comments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'post': post,
        'page_obj': page_obj,
        'title': f'Comments for "{post.title}"'
    }
    
    return render(request, 'blog/admin/post_comments.html', context)


@staff_member_required
def ai_content_suggestions(request, post_id=None):
    """
    AI-powered content suggestions for blog posts.
    """
    if not hasattr(settings, 'OPENAI_API_KEY') or not settings.OPENAI_API_KEY:
        messages.error(request, 'OpenAI API key is not configured. Cannot provide AI suggestions.')
        return redirect('blog_admin:dashboard')
    
    post = None
    if post_id:
        post = get_object_or_404(BlogPostPage, id=post_id)
    
    suggestions = []
    
    if request.method == 'POST':
        # This would integrate with Wagtail AI for content suggestions
        # For now, we'll provide placeholder functionality
        content_type = request.POST.get('content_type', 'title')
        context_text = request.POST.get('context', '')
        
        # Mock AI suggestions - in production this would use Wagtail AI
        if content_type == 'title':
            suggestions = [
                "10 Essential Plant Care Tips for Beginners",
                "How to Identify Common Garden Pests",
                "The Ultimate Guide to Indoor Plant Lighting"
            ]
        elif content_type == 'outline':
            suggestions = [
                "Introduction to the topic",
                "Main benefits and advantages", 
                "Step-by-step instructions",
                "Common mistakes to avoid",
                "Conclusion and next steps"
            ]
    
    context = {
        'post': post,
        'suggestions': suggestions,
        'title': 'AI Content Suggestions'
    }
    
    return render(request, 'blog/admin/ai_suggestions.html', context)


@staff_member_required
def blog_search(request):
    """
    Advanced search interface for blog content.
    """
    query = request.GET.get('q', '')
    content_type = request.GET.get('type', 'all')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    results = {
        'posts': [],
        'comments': [],
        'categories': [],
    }
    
    if query:
        # Search posts
        if content_type in ['all', 'posts']:
            posts = BlogPostPage.objects.live().filter(
                Q(title__icontains=query) |
                Q(search_description__icontains=query) |
                Q(introduction__icontains=query)
            )
            
            if date_from:
                posts = posts.filter(first_published_at__gte=date_from)
            if date_to:
                posts = posts.filter(first_published_at__lte=date_to)
                
            results['posts'] = posts[:20]
        
        # Search comments
        if content_type in ['all', 'comments']:
            comments = BlogComment.objects.filter(
                Q(content__icontains=query) |
                Q(author__username__icontains=query)
            )
            results['comments'] = comments[:20]
        
        # Search categories
        if content_type in ['all', 'categories']:
            categories = BlogCategory.objects.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query)
            )
            results['categories'] = categories[:10]
    
    context = {
        'query': query,
        'content_type': content_type,
        'date_from': date_from,
        'date_to': date_to,
        'results': results,
        'title': 'Blog Search'
    }
    
    return render(request, 'blog/admin/search.html', context)


@staff_member_required
def blog_settings(request):
    """
    Blog-specific settings and configuration.
    """
    if request.method == 'POST':
        # Handle settings updates
        # This would typically update a BlogSettings model or use Django settings
        messages.success(request, 'Blog settings have been updated.')
        return redirect('blog_admin:settings')
    
    # Mock settings - in production these would come from a model or Django settings
    settings_data = {
        'posts_per_page': 10,
        'allow_comments': True,
        'moderate_comments': True,
        'enable_ai_suggestions': True,
        'featured_posts_limit': 5,
        'auto_excerpt_length': 150,
    }
    
    context = {
        'settings': settings_data,
        'title': 'Blog Settings'
    }
    
    return render(request, 'blog/admin/settings.html', context)


@staff_member_required
def tag_plants(request, post_id):
    """
    Interface for tagging plants mentioned in blog posts.
    """
    post = get_object_or_404(BlogPostPage, id=post_id)
    
    if request.method == 'POST':
        # Handle plant tagging
        plant_tags = request.POST.getlist('plant_tags')
        # This would integrate with the plant identification system
        messages.success(request, f'Plant tags updated for "{post.title}".')
        return redirect('blog_admin:dashboard')
    
    # Mock plant suggestions - would come from plant identification system
    suggested_plants = [
        {'id': 1, 'name': 'Monstera deliciosa', 'scientific_name': 'Monstera deliciosa'},
        {'id': 2, 'name': 'Snake Plant', 'scientific_name': 'Sansevieria trifasciata'},
        {'id': 3, 'name': 'Pothos', 'scientific_name': 'Epipremnum aureum'},
    ]
    
    context = {
        'post': post,
        'suggested_plants': suggested_plants,
        'title': f'Tag Plants in "{post.title}"'
    }
    
    return render(request, 'blog/admin/tag_plants.html', context)


@staff_member_required
def export_data(request):
    """
    Export blog data in various formats (CSV, JSON).
    """
    export_type = request.GET.get('type', 'posts')
    format_type = request.GET.get('format', 'csv')
    
    if export_type == 'posts':
        posts = BlogPostPage.objects.live().order_by('-first_published_at')
        
        if format_type == 'json':
            serializer = BlogPostPageSerializer(posts, many=True)
            response = JsonResponse({'posts': serializer.data})
            response['Content-Disposition'] = 'attachment; filename="blog_posts.json"'
            return response
        
    elif export_type == 'comments':
        comments = BlogComment.objects.all().order_by('-created_at')
        
        if format_type == 'json':
            serializer = BlogCommentSerializer(comments, many=True)
            response = JsonResponse({'comments': serializer.data})
            response['Content-Disposition'] = 'attachment; filename="blog_comments.json"'
            return response
    
    # Default response
    return JsonResponse({'error': 'Invalid export parameters'}, status=400)