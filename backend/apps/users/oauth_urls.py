"""
OAuth URL configuration for social authentication.
"""

from django.urls import path
from . import oauth_views

urlpatterns = [
    path('login/', oauth_views.oauth_login, name='oauth_login'),
    path('callback/', oauth_views.oauth_callback, name='oauth_callback'),
]