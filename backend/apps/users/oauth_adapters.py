"""
Custom adapters for django-allauth OAuth integration with JWT authentication.
"""

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.models import SocialLogin
from allauth.core.exceptions import ImmediateHttpResponse
from django.http import HttpResponseRedirect
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter to handle OAuth flow with JWT token generation.
    """
    
    def pre_social_login(self, request, sociallogin):
        """
        Invoked just after a user successfully authenticates via a social provider,
        but before the login is actually processed.
        """
        # Check if user exists with same email
        if sociallogin.account.provider == 'google' or sociallogin.account.provider == 'github':
            email = sociallogin.account.extra_data.get('email')
            if email:
                try:
                    existing_user = User.objects.get(email=email)
                    if not sociallogin.is_existing:
                        # Connect the social account to existing user
                        sociallogin.connect(request, existing_user)
                        logger.info(f"Connected {sociallogin.account.provider} account to existing user: {existing_user.username}")
                except User.DoesNotExist:
                    pass
    
    def save_user(self, request, sociallogin, form=None):
        """
        Saves a newly signed up social login user.
        """
        user = super().save_user(request, sociallogin, form)
        
        # Update user profile with social data
        extra_data = sociallogin.account.extra_data
        
        if sociallogin.account.provider == 'google':
            # Update from Google profile
            if not user.first_name and extra_data.get('given_name'):
                user.first_name = extra_data.get('given_name', '')[:30]
            if not user.last_name and extra_data.get('family_name'):
                user.last_name = extra_data.get('family_name', '')[:150]
                
        elif sociallogin.account.provider == 'github':
            # Update from GitHub profile
            if not user.first_name and extra_data.get('name'):
                name_parts = extra_data.get('name', '').split(' ', 1)
                user.first_name = name_parts[0][:30] if name_parts else ''
                if len(name_parts) > 1:
                    user.last_name = name_parts[1][:150]
            
            # Set bio from GitHub bio if available
            if not user.bio and extra_data.get('bio'):
                user.bio = extra_data.get('bio', '')[:500]
            
            # Set website from GitHub blog if available
            if not user.website and extra_data.get('blog'):
                user.website = extra_data.get('blog', '')[:200]
        
        user.save()
        logger.info(f"Created new user via {sociallogin.account.provider}: {user.username}")
        return user
    
    def get_login_redirect_url(self, request):
        """
        Return the URL to redirect to after a successful social login.
        We'll redirect to our custom callback view that handles JWT token generation.
        """
        # Get the provider name
        provider = getattr(request, '_oauth_provider', 'unknown')
        
        # Redirect to our custom callback view
        return reverse('users:oauth_callback', kwargs={'provider': provider})


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter for regular authentication flow.
    """
    
    def get_login_redirect_url(self, request):
        """
        Return the URL to redirect to after login.
        """
        # For API-based authentication, we don't need to redirect
        return '/'
    
    def get_logout_redirect_url(self, request):
        """
        Return the URL to redirect to after logout.
        """
        return '/'
    
    def send_confirmation_mail(self, request, emailconfirmation, signup):
        """
        Custom email confirmation logic.
        """
        # You can customize email confirmation here if needed
        super().send_confirmation_mail(request, emailconfirmation, signup)