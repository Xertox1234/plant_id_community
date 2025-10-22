"""
AI Image Generation service for botanical content.

Uses OpenAI DALL-E 3 to generate high-quality botanical images when stock photos aren't available.
"""

import openai
import requests
import logging
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.core.cache import cache
from django.core.files.images import ImageFile
from wagtail.images.models import Image
from io import BytesIO
import hashlib
import json

logger = logging.getLogger(__name__)


class AIBotanicalImageService:
    """
    Service for generating botanical images using OpenAI DALL-E 3.
    Creates scientifically accurate plant images when stock photos aren't available.
    """
    
    CACHE_TIMEOUT = 3600 * 24 * 7  # 7 days for generated images
    COST_CACHE_TIMEOUT = 3600 * 24  # 24 hours for cost tracking
    
    # DALL-E 3 pricing (as of 2025)
    DALLE_COSTS = {
        'standard_1024': 0.040,  # $0.040 per image
        'hd_1024': 0.080,        # $0.080 per HD image
        'standard_1792': 0.040,   # Same price for different orientations
        'hd_1792': 0.080
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the AI Image Generation service.
        
        Args:
            api_key: OpenAI API key. If not provided, will use settings.OPENAI_API_KEY
        """
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', None)
        if not self.api_key:
            logger.warning("OpenAI API key not configured - AI image generation will be disabled")
            self.client = None
        else:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.client = None
    
    def _get_cost_cache_key(self) -> str:
        """Get cache key for daily cost tracking."""
        from datetime import date
        return f"ai_image_cost_{date.today().isoformat()}"
    
    def get_daily_cost(self) -> float:
        """Get today's accumulated cost for AI image generation."""
        return cache.get(self._get_cost_cache_key(), 0.0)
    
    def _track_cost(self, cost: float) -> None:
        """Track the cost of AI image generation."""
        cache_key = self._get_cost_cache_key()
        current_cost = cache.get(cache_key, 0.0)
        cache.set(cache_key, current_cost + cost, self.COST_CACHE_TIMEOUT)
        logger.info(f"AI image cost tracked: ${cost:.3f} (daily total: ${current_cost + cost:.3f})")
    
    def _create_botanical_prompt(self, plant_name: str, scientific_name: Optional[str] = None,
                               style: str = 'photographic') -> str:
        """
        Create a detailed botanical prompt for DALL-E 3.
        
        Args:
            plant_name: Common name of the plant
            scientific_name: Scientific name for accuracy
            style: Image style ('photographic', 'illustration', 'watercolor')
            
        Returns:
            Detailed prompt for botanical accuracy
        """
        base_prompts = {
            'photographic': (
                "High-quality botanical photography of {plant_full_name}, "
                "professional macro lens, natural lighting, detailed leaves and textures, "
                "scientific accuracy, clean white background, studio photography style, "
                "sharp focus, botanical reference quality"
            ),
            'illustration': (
                "Scientific botanical illustration of {plant_full_name}, "
                "detailed pen and ink style, accurate botanical features, "
                "clean line art, educational diagram quality, "
                "white background, precise botanical accuracy"
            ),
            'watercolor': (
                "Watercolor botanical illustration of {plant_full_name}, "
                "delicate artistic style, accurate plant anatomy, "
                "soft natural colors, artistic but scientifically correct, "
                "clean white background, botanical art style"
            )
        }
        
        # Build full plant name
        if scientific_name:
            plant_full_name = f"{plant_name} ({scientific_name})"
        else:
            plant_full_name = plant_name
        
        prompt_template = base_prompts.get(style, base_prompts['photographic'])
        prompt = prompt_template.format(plant_full_name=plant_full_name)
        
        # Add specific botanical accuracy instructions
        prompt += (
            f" The image must accurately represent the distinctive characteristics "
            f"of {plant_name}, including proper leaf shape, growth pattern, "
            f"and botanical features. Ensure scientific accuracy and realism."
        )
        
        return prompt
    
    def generate_plant_image(self, plant_name: str, scientific_name: Optional[str] = None,
                           style: str = 'photographic', quality: str = 'standard',
                           size: str = '1024x1024') -> Optional[Dict]:
        """
        Generate a botanical image using DALL-E 3.
        
        Args:
            plant_name: Common name of the plant
            scientific_name: Scientific name for accuracy
            style: Image style ('photographic', 'illustration', 'watercolor')
            quality: Image quality ('standard' or 'hd')
            size: Image size ('1024x1024', '1024x1792', '1792x1024')
            
        Returns:
            Dictionary with image data and metadata, or None if failed
        """
        if not self.client:
            logger.warning("OpenAI client not available")
            return None
        
        # Check daily cost limit (configurable)
        max_daily_cost = getattr(settings, 'AI_IMAGE_DAILY_COST_LIMIT', 5.0)  # $5 default
        current_cost = self.get_daily_cost()
        
        estimated_cost = self.DALLE_COSTS.get(f"{quality}_{size.split('x')[0]}", 0.080)
        
        if current_cost + estimated_cost > max_daily_cost:
            logger.warning(f"Daily AI image cost limit exceeded: ${current_cost:.2f} + ${estimated_cost:.2f} > ${max_daily_cost:.2f}")
            return None
        
        # Create prompt
        prompt = self._create_botanical_prompt(plant_name, scientific_name, style)
        
        # Check cache for identical requests
        prompt_hash = hashlib.md5(f"{prompt}_{quality}_{size}".encode()).hexdigest()
        cache_key = f"ai_plant_image_{prompt_hash}"
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"Using cached AI-generated image for: {plant_name}")
            return cached_result
        
        try:
            logger.info(f"Generating AI image for: {plant_name} (style: {style}, quality: {quality})")
            
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                style="natural",  # More realistic for botanical images
                n=1
            )
            
            image_data = {
                'id': prompt_hash,
                'prompt': prompt,
                'url': response.data[0].url,
                'revised_prompt': response.data[0].revised_prompt,
                'size': size,
                'quality': quality,
                'style': style,
                'plant_name': plant_name,
                'scientific_name': scientific_name,
                'source': 'ai_generated',
                'cost': estimated_cost
            }
            
            # Track cost
            self._track_cost(estimated_cost)
            
            # Cache the result
            cache.set(cache_key, image_data, self.CACHE_TIMEOUT)
            
            logger.info(f"Successfully generated AI image for: {plant_name}")
            return image_data
            
        except Exception as e:
            logger.error(f"Failed to generate AI image for {plant_name}: {e}")
            return None
    
    def download_and_create_wagtail_image(self, image_data: Dict,
                                        title_prefix: str = "AI Generated Plant Image") -> Optional[Image]:
        """
        Download an AI-generated image and create a Wagtail Image object.
        
        Args:
            image_data: Image data dictionary from generate_plant_image
            title_prefix: Prefix for the image title
            
        Returns:
            Wagtail Image object or None if failed
        """
        if not image_data or 'url' not in image_data:
            return None
        
        try:
            # Download the image
            response = requests.get(image_data['url'], timeout=30)
            response.raise_for_status()
            
            # Create file content using BytesIO and ImageFile for proper metadata extraction
            filename = f"ai_generated_{image_data['id']}.png"
            image_io = BytesIO(response.content)
            image_file = ImageFile(image_io, name=filename)
            
            # Create Wagtail Image
            plant_name = image_data.get('plant_name', 'Plant')
            title = f"{title_prefix} - {plant_name}"[:255]
            
            wagtail_image = Image(
                title=title,
                file=image_file
            )
            wagtail_image.save()
            
            # Store additional metadata in tags
            try:
                tags = [
                    'ai_generated',
                    'dall_e_3',
                    'botanical',
                    f"style:{image_data.get('style', 'photographic')}",
                    f"quality:{image_data.get('quality', 'standard')}",
                    f"cost:{image_data.get('cost', 0):.3f}"
                ]
                if image_data.get('scientific_name'):
                    tags.append(f"scientific:{image_data['scientific_name'].replace(' ', '_')}")
                
                wagtail_image.tags.add(*tags)
            except Exception as e:
                logger.warning(f"Could not add tags to AI image: {e}")
            
            logger.info(f"Created Wagtail image from AI generation: {title}")
            return wagtail_image
            
        except Exception as e:
            logger.error(f"Failed to download/create Wagtail image from AI: {e}")
            return None
    
    def get_best_ai_plant_image(self, plant_name: str, scientific_name: Optional[str] = None) -> Optional[Tuple[Dict, Image]]:
        """
        Generate the best AI plant image and create a Wagtail Image object.
        
        Args:
            plant_name: Common name of the plant
            scientific_name: Scientific name for accuracy
            
        Returns:
            Tuple of (image_data, wagtail_image) or None if failed
        """
        # Try photographic style first for most realistic results
        image_data = self.generate_plant_image(
            plant_name=plant_name,
            scientific_name=scientific_name,
            style='photographic',
            quality='standard',  # Use standard to save costs
            size='1024x1024'    # Square format good for spotlight blocks
        )
        
        if not image_data:
            logger.info(f"Failed to generate AI image for: {plant_name}")
            return None
        
        wagtail_image = self.download_and_create_wagtail_image(
            image_data,
            title_prefix=f"AI {plant_name} Plant"
        )
        
        if wagtail_image:
            return image_data, wagtail_image
        else:
            logger.warning(f"Failed to download generated AI image for: {plant_name}")
            return None
    
    def get_generation_stats(self) -> Dict:
        """Get statistics about AI image generation usage."""
        return {
            'daily_cost': self.get_daily_cost(),
            'cost_limit': getattr(settings, 'AI_IMAGE_DAILY_COST_LIMIT', 5.0),
            'remaining_budget': max(0, getattr(settings, 'AI_IMAGE_DAILY_COST_LIMIT', 5.0) - self.get_daily_cost()),
            'api_available': self.client is not None
        }