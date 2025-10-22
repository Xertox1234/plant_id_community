"""
Django management command to migrate PlantCareGuide data to Blog system.

This command:
1. Creates the 'Plant Care' blog category if it doesn't exist
2. Converts all PlantCareGuide entries to BlogPostPage entries
3. Preserves all plant species relationships and content
4. Maps care guide StreamField content to blog StreamField content
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.utils import timezone
from django.db import transaction

from apps.blog.models import BlogCategory, BlogPostPage, BlogIndexPage
from apps.plant_identification.models import PlantCareGuide

User = get_user_model()


class Command(BaseCommand):
    help = 'Migrate PlantCareGuide data to BlogPostPage entries under Plant Care category'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without making changes',
        )
        parser.add_argument(
            '--author-email',
            type=str,
            default='admin@plantcommunity.com',
            help='Email of user to assign as blog post author (default: admin@plantcommunity.com)',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        author_email = options['author_email']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Check if PlantCareGuide model exists
        try:
            care_guides = PlantCareGuide.objects.all()
            guide_count = care_guides.count()
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'PlantCareGuide model not found or accessible: {e}')
            )
            return
        
        if guide_count == 0:
            self.stdout.write(self.style.SUCCESS('No plant care guides found to migrate.'))
            return
        
        self.stdout.write(f'Found {guide_count} plant care guides to migrate.')
        
        # Get or create the blog author
        try:
            author = User.objects.get(email=author_email)
            self.stdout.write(f'Using author: {author.username} ({author.email})')
        except User.DoesNotExist:
            if not dry_run:
                # Create a default admin user if none exists
                author = User.objects.create_user(
                    username='plant_care_admin',
                    email=author_email,
                    password='temp_password_change_immediately',
                    is_staff=True,
                    is_superuser=True
                )
                self.stdout.write(
                    self.style.WARNING(f'Created new admin user: {author.username}')
                )
                self.stdout.write(
                    self.style.WARNING('IMPORTANT: Change the default password immediately!')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Would create admin user with email: {author_email}')
                )
                return
        
        # Find blog index page for adding blog posts
        try:
            blog_index = BlogIndexPage.objects.get()
            self.stdout.write(f'Using blog index: {blog_index.title}')
        except BlogIndexPage.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('No BlogIndexPage found. Please create a blog index page first.')
            )
            return
        except BlogIndexPage.MultipleObjectsReturned:
            blog_index = BlogIndexPage.objects.first()
            self.stdout.write(
                self.style.WARNING(f'Multiple blog indexes found, using: {blog_index.title}')
            )
        
        with transaction.atomic():
            # Step 1: Create or get the 'Plant Care' category
            plant_care_category = self.create_plant_care_category(dry_run)
            
            # Step 2: Migrate each care guide
            migrated_count = 0
            
            for care_guide in care_guides:
                try:
                    blog_post = self.migrate_care_guide_to_blog_post(
                        care_guide, author, blog_index, plant_care_category, dry_run
                    )
                    if blog_post:
                        migrated_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ Migrated: {care_guide.plant_species.scientific_name}')
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'⚠ Skipped: {care_guide.plant_species.scientific_name}')
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'✗ Failed to migrate {care_guide.plant_species.scientific_name}: {e}')
                    )
                    if not dry_run:
                        raise CommandError(f'Migration failed for {care_guide.plant_species.scientific_name}: {e}')
            
            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(f'DRY RUN: Would migrate {migrated_count} care guides to blog posts')
                )
                transaction.set_rollback(True)
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully migrated {migrated_count} care guides to blog posts')
                )
    
    def create_plant_care_category(self, dry_run):
        """Create or get the Plant Care blog category."""
        if dry_run:
            try:
                category = BlogCategory.objects.get(slug='plant-care')
                self.stdout.write(f'Plant Care category already exists: {category.name}')
                return category
            except BlogCategory.DoesNotExist:
                self.stdout.write('Would create Plant Care category')
                return None
        
        category, created = BlogCategory.objects.get_or_create(
            slug='plant-care',
            defaults={
                'name': 'Plant Care',
                'description': 'Comprehensive plant care guides and tips for growing healthy plants',
                'icon': 'fas fa-seedling',
                'color': '#28a745',  # Green color appropriate for plants
                'is_featured': True,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created Plant Care category'))
        else:
            self.stdout.write('Plant Care category already exists')
        
        return category
    
    def migrate_care_guide_to_blog_post(self, care_guide, author, blog_index, category, dry_run):
        """Convert a PlantCareGuide to a BlogPostPage."""
        plant_species = care_guide.plant_species
        
        # Create slug from plant name
        title = f"{plant_species.display_name} Care Guide"
        slug = slugify(title)
        
        # Check if blog post already exists
        existing_post = BlogPostPage.objects.filter(slug=slug).first()
        if existing_post:
            self.stdout.write(f'Blog post already exists for {plant_species.scientific_name}')
            return existing_post
        
        if dry_run:
            self.stdout.write(f'Would create blog post: {title}')
            return None
        
        # Build introduction from care guide summary
        introduction = care_guide.quick_care_summary or f"Complete care guide for {plant_species.display_name}"
        
        # Convert care guide content to blog content blocks
        content_blocks = self.convert_care_guide_content_to_blog_blocks(care_guide)
        
        # Create the blog post
        blog_post = BlogPostPage(
            title=title,
            slug=slug,
            author=author,
            publish_date=timezone.now().date(),
            introduction=introduction,
            content_blocks=content_blocks,
            difficulty_level=care_guide.care_difficulty if care_guide.care_difficulty != 'very_easy' else 'beginner',
            is_featured=care_guide.is_featured,
            allow_comments=True,
        )
        
        # Add to blog index
        blog_index.add_child(instance=blog_post)
        
        # Associate with Plant Care category
        blog_post.categories.add(category)
        
        # Associate with the plant species
        blog_post.related_plant_species.add(plant_species)
        
        # Save and publish
        blog_post.save_revision().publish()
        
        return blog_post
    
    def convert_care_guide_content_to_blog_blocks(self, care_guide):
        """Convert PlantCareGuide content to blog StreamField blocks."""
        blocks = []
        
        # Add care instructions block with detailed care info
        if any([
            care_guide.light_description,
            care_guide.watering_description,
            care_guide.soil_description,
            care_guide.temperature_description,
            care_guide.humidity_description,
            care_guide.fertilizing_description
        ]):
            care_block = ('care_instructions', {
                'care_title': f"{care_guide.plant_species.display_name} Care Requirements",
                'watering': care_guide.watering_description or 'Watering information not specified.',
                'lighting': care_guide.light_description or 'Light requirements not specified.',
                'temperature': care_guide.temperature_description or '',
                'humidity': care_guide.humidity_description or '',
                'fertilizing': care_guide.fertilizing_description or '',
                'special_notes': care_guide.seasonal_notes or care_guide.common_problems or ''
            })
            blocks.append(care_block)
        
        # Add plant spotlight block
        plant_spotlight_block = ('plant_spotlight', {
            'plant_name': care_guide.plant_species.display_name,
            'scientific_name': care_guide.plant_species.scientific_name,
            'description': (
                care_guide.plant_species.description or 
                f"Beautiful {care_guide.plant_species.plant_type or 'plant'} with {care_guide.care_difficulty} care requirements."
            ),
            'care_difficulty': care_guide.care_difficulty if care_guide.care_difficulty != 'very_easy' else 'easy',
        })
        blocks.append(plant_spotlight_block)
        
        # Add propagation information if available
        if care_guide.propagation_methods:
            blocks.append(('heading', 'Propagation'))
            blocks.append(('paragraph', care_guide.propagation_methods))
        
        # Add common problems if available
        if care_guide.common_problems:
            blocks.append(('heading', 'Common Problems & Solutions'))
            blocks.append(('paragraph', care_guide.common_problems))
        
        # Add seasonal care notes if available
        if care_guide.seasonal_notes:
            blocks.append(('heading', 'Seasonal Care Notes'))
            blocks.append(('paragraph', care_guide.seasonal_notes))
        
        # Convert original StreamField content if it exists
        if care_guide.care_content:
            try:
                for block in care_guide.care_content:
                    # Map care guide blocks to blog blocks where possible
                    if block.block_type == 'heading':
                        blocks.append(('heading', block.value))
                    elif block.block_type == 'paragraph':
                        blocks.append(('paragraph', block.value))
                    elif block.block_type == 'image':
                        blocks.append(('image', block.value))
                    elif block.block_type == 'care_tip':
                        # Convert care tip to heading + paragraph
                        tip_data = block.value
                        blocks.append(('heading', f"💡 {tip_data.get('tip_title', 'Care Tip')}"))
                        blocks.append(('paragraph', tip_data.get('tip_content', '')))
                    elif block.block_type == 'seasonal_care':
                        # Convert seasonal care to heading + paragraph
                        seasonal_data = block.value
                        season = seasonal_data.get('season', '').title()
                        blocks.append(('heading', f"🌿 {season} Care\"))
                        blocks.append(('paragraph', seasonal_data.get('care_instructions', '')))
                        if seasonal_data.get('special_notes'):
                            blocks.append(('paragraph', f"Special notes: {seasonal_data['special_notes']}\"))
                    elif block.block_type == 'problem_solution':
                        # Convert problem/solution to structured content
                        problem_data = block.value
                        blocks.append(('heading', f"⚠️ Problem: {problem_data.get('problem', '')}\"))
                        if problem_data.get('symptoms'):
                            blocks.append(('paragraph', f"Symptoms: {problem_data['symptoms']}\"))
                        if problem_data.get('solution'):
                            blocks.append(('paragraph', f"Solution: {problem_data['solution']}\"))
                        if problem_data.get('prevention'):
                            blocks.append(('paragraph', f"Prevention: {problem_data['prevention']}\"))
                    elif block.block_type == 'gallery':
                        blocks.append(('gallery', block.value))
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'Could not convert StreamField content: {e}')
                )
        
        return blocks