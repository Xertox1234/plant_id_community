"""
Management command to populate plant images in blog post spotlight blocks.

This command scans all blog posts for plant_spotlight blocks without images
and automatically fetches appropriate images using the unified image service.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.blog.models import BlogPostPage
from apps.plant_identification.services.plant_image_service import PlantImageService
import json
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Populate missing plant images in blog post spotlight blocks'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        parser.add_argument(
            '--max-ai-images',
            type=int,
            default=3,
            help='Maximum number of AI-generated images to create (default: 3)'
        )
        parser.add_argument(
            '--prefer-source',
            choices=['unsplash', 'pexels', 'ai'],
            help='Preferred image source'
        )
        parser.add_argument(
            '--post-id',
            type=int,
            help='Process only a specific blog post by ID'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Replace existing images in spotlight blocks'
        )
    
    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.max_ai_images = options['max_ai_images']
        self.prefer_source = options['prefer_source']
        self.force = options['force']
        
        # Initialize the image service
        try:
            self.image_service = PlantImageService()
        except Exception as e:
            raise CommandError(f"Failed to initialize image service: {e}")
        
        # Show service status
        self._show_service_status()
        
        # Get blog posts to process
        if options['post_id']:
            try:
                posts = [BlogPostPage.objects.get(id=options['post_id'])]
            except BlogPostPage.DoesNotExist:
                raise CommandError(f"Blog post with ID {options['post_id']} not found")
        else:
            posts = BlogPostPage.objects.live().public()
        
        self.stdout.write(f"Processing {len(posts) if isinstance(posts, list) else posts.count()} blog posts...")
        
        # Process posts
        total_plants_found = 0
        total_images_added = 0
        ai_images_used = 0
        
        for post in posts:
            self.stdout.write(f"\nProcessing: {post.title}")
            
            plants_in_post = self._extract_plants_from_post(post)
            if not plants_in_post:
                self.stdout.write("  No plant spotlight blocks found")
                continue
            
            total_plants_found += len(plants_in_post)
            
            for plant_info in plants_in_post:
                block_id = plant_info['block_id']
                plant_name = plant_info['plant_name']
                scientific_name = plant_info.get('scientific_name')
                has_image = plant_info['has_image']
                
                # Skip if already has image and not forcing
                if has_image and not self.force:
                    self.stdout.write(f"  {plant_name}: Already has image (use --force to replace)")
                    continue
                
                # Check AI limit
                allow_ai = ai_images_used < self.max_ai_images
                
                if self.dry_run:
                    self.stdout.write(f"  {plant_name}: Would fetch image (AI allowed: {allow_ai})")
                    continue
                
                # Fetch image
                try:
                    result = self.image_service.get_best_plant_image(
                        plant_name=plant_name,
                        scientific_name=scientific_name,
                        prefer_source=self.prefer_source,
                        allow_ai_generation=allow_ai
                    )
                    
                    if result:
                        source, image_data, wagtail_image = result
                        
                        # Update the blog post
                        if self._update_post_image(post, block_id, wagtail_image):
                            total_images_added += 1
                            if source == 'ai':
                                ai_images_used += 1
                            
                            attribution = self.image_service.get_attribution_text(source, image_data)
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  {plant_name}: Added image from {source} - {attribution}"
                                )
                            )
                        else:
                            self.stdout.write(
                                self.style.ERROR(f"  {plant_name}: Failed to update post")
                            )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f"  {plant_name}: No suitable image found")
                        )
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  {plant_name}: Error - {str(e)}")
                    )
        
        # Show summary
        self.stdout.write(f"\n{self.style.SUCCESS('Summary:')}")
        self.stdout.write(f"  Total plants found: {total_plants_found}")
        self.stdout.write(f"  Images added: {total_images_added}")
        self.stdout.write(f"  AI images used: {ai_images_used}")
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes made"))
    
    def _show_service_status(self):
        """Display the status of image services."""
        stats = self.image_service.get_source_stats()
        
        self.stdout.write(f"\n{self.style.SUCCESS('Image Service Status:')}")
        for source, info in stats.items():
            status = "✓" if info['available'] else "✗"
            self.stdout.write(f"  {source}: {status} {info['description']}")
            
            if source == 'ai' and info['available']:
                daily_cost = info.get('daily_cost', 0)
                cost_limit = info.get('cost_limit', 5.0)
                self.stdout.write(f"    Daily cost: ${daily_cost:.2f} / ${cost_limit:.2f}")
    
    def _extract_plants_from_post(self, post):
        """
        Extract plant information from plant_spotlight blocks in a blog post.
        
        Args:
            post: BlogPostPage instance
            
        Returns:
            List of plant information dictionaries
        """
        plants = []
        
        for block in post.content_blocks:
            if block.block_type == 'plant_spotlight':
                block_value = block.value
                plant_name = block_value.get('plant_name', '').strip()
                
                if plant_name:
                    plants.append({
                        'block_id': str(block.id),
                        'plant_name': plant_name,
                        'scientific_name': block_value.get('scientific_name', '').strip() or None,
                        'has_image': bool(block_value.get('image'))
                    })
        
        return plants
    
    def _update_post_image(self, post, block_id, wagtail_image):
        """
        Update a plant_spotlight block with a new image.
        
        Args:
            post: BlogPostPage instance
            block_id: Block ID to update
            wagtail_image: Wagtail Image instance
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with transaction.atomic():
                # Find and update the block using StreamField's list interface
                found_block = False
                
                for i, block in enumerate(post.content_blocks):
                    if str(block.id) == block_id and block.block_type == 'plant_spotlight':
                        # Update the block value with the new image
                        new_value = dict(block.value)  # Create a proper dict copy
                        new_value['image'] = wagtail_image
                        
                        # Replace the block using StreamField's tuple interface
                        post.content_blocks[i] = (block.block_type, new_value)
                        found_block = True
                        break
                
                if not found_block:
                    logger.error(f"Block {block_id} not found in post {post.id}")
                    return False
                
                # Save the post
                post.save()
                
                logger.info(f"Updated block {block_id} in post {post.id} with image {wagtail_image.id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update post {post.id} block {block_id}: {e}")
            return False