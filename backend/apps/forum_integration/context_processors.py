"""
Simple context processor for forum integration.
"""

def forum_globals(request):
    """
    Add basic forum data to all template contexts.
    """
    return {
        'forum_enabled': True,
        'forum_url': '/forum/',
    }