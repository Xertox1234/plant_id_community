"""
Blog services package for caching and performance optimization.

This package (services/) shadows the parent services.py file.
We need to re-export classes from the parent services.py for backward compatibility.
"""

from .blog_cache_service import BlogCacheService

# Re-export from parent services.py module for backward compatibility
# The parent directory has both:
# - services.py (with BlockAutoPopulationService, PlantDataLookupService)
# - services/ directory (this package, with BlogCacheService)
#
# When code does `from .services import BlockAutoPopulationService`,
# Python imports from services/ (this package), so we need to re-export.

def __getattr__(name):
    """Lazy import from parent services.py to avoid circular imports."""
    if name in ('BlockAutoPopulationService', 'PlantDataLookupService'):
        # Import the parent-level services.py module
        import importlib
        import importlib.util
        import os

        # Oops, this will recurse. Need different approach.
        # Let's directly import from the file
        parent_dir = os.path.dirname(os.path.dirname(__file__))
        services_file = os.path.join(parent_dir, 'services.py')

        # Load the parent services.py as a separate module
        spec = importlib.util.spec_from_file_location("apps.blog._parent_services", services_file)
        parent_services_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(parent_services_module)

        return getattr(parent_services_module, name)

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = ['BlogCacheService', 'BlockAutoPopulationService', 'PlantDataLookupService']
