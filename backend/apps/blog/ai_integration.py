"""
AI integration for BlogPostPage content panels.

Provides custom AI prompts and field configuration for AI-powered
content generation in the Wagtail admin interface.

Integrates with:
- AICacheService for cost optimization
- AIRateLimiter for quota protection
- PlantAIPrompts for plant-specific content

Pattern: Wagtail AI 3.0 Custom Content Panels (WAGTAIL_AI_PATTERNS_CODIFIED.md #6)
"""

from typing import Dict, Any, Optional
from .ai_prompts import PlantAIPrompts


class BlogAIPrompts:
    """
    Custom AI prompts for blog content generation.

    Provides plant-specific, SEO-optimized prompts for blog fields
    with context-aware content generation.
    """

    @staticmethod
    def get_title_prompt(context: Dict[str, Any]) -> str:
        """
        Generate AI prompt for blog post title.

        Args:
            context: Dictionary with keys:
                - introduction: str (optional) - Post introduction
                - related_plants: list (optional) - Related plant species
                - difficulty_level: str (optional) - beginner/intermediate/advanced
                - existing_content: str (optional) - Content blocks preview

        Returns:
            Formatted prompt for AI title generation
        """
        introduction = context.get('introduction', '')
        related_plants = context.get('related_plants', [])
        difficulty_level = context.get('difficulty_level', '')

        # Build plant context
        plant_context = ""
        if related_plants:
            plant_names = ", ".join([p.get('common_name') or p.get('scientific_name', '')
                                    for p in related_plants[:3]])
            plant_context = f"This post is about: {plant_names}. "

        # Build difficulty context
        difficulty_context = ""
        if difficulty_level:
            difficulty_context = f"Content is aimed at {difficulty_level} gardeners. "

        prompt = f"""Generate an engaging, SEO-optimized blog post title for a plant care article.

{plant_context}{difficulty_context}

Content Preview:
{introduction[:300] if introduction else 'No preview available'}

Requirements:
- 40-60 characters (optimal for SEO)
- Include plant name(s) if mentioned
- Use action words: "How to", "Guide", "Tips", "Growing"
- Be specific and descriptive
- Avoid clickbait - focus on value
- Make it beginner-friendly if difficulty is "beginner"

Examples of good titles:
- "How to Care for Monstera Deliciosa: Complete Beginner's Guide"
- "5 Essential Snake Plant Care Tips for Healthy Growth"
- "Growing Pothos: Water, Light, and Propagation Made Easy"

Generate only the title, no additional text."""

        return prompt

    @staticmethod
    def get_introduction_prompt(context: Dict[str, Any]) -> str:
        """
        Generate AI prompt for blog post introduction.

        Args:
            context: Dictionary with keys:
                - title: str (optional) - Post title
                - related_plants: list (optional) - Related plant species
                - difficulty_level: str (optional) - beginner/intermediate/advanced
                - existing_intro: str (optional) - Existing introduction to improve

        Returns:
            Formatted prompt for AI introduction generation
        """
        title = context.get('title', '')
        related_plants = context.get('related_plants', [])
        difficulty_level = context.get('difficulty_level', 'beginner')
        existing_intro = context.get('existing_intro', '')

        # Build plant context with details
        plant_context = ""
        if related_plants:
            plant_details = []
            for plant in related_plants[:2]:
                name = plant.get('common_name') or plant.get('scientific_name', '')
                scientific = plant.get('scientific_name', '')
                if scientific and name != scientific:
                    plant_details.append(f"{name} ({scientific})")
                else:
                    plant_details.append(name)
            plant_context = f"Featured plants: {', '.join(plant_details)}. "

        action_type = "improve the following" if existing_intro else "create a compelling"

        prompt = f"""Generate an engaging introduction for a plant care blog post.

Title: {title or 'Blog Post About Plant Care'}
{plant_context}
Target Audience: {difficulty_level.capitalize()} gardeners

{f"Existing Introduction to Improve:\\n{existing_intro}\\n\\n" if existing_intro else ""}Requirements:
- 2-3 short paragraphs (100-150 words total)
- Hook readers in the first sentence with a relatable problem or benefit
- Briefly mention what readers will learn
- Use friendly, conversational tone
- Include plant name(s) naturally
- End with a teaser for the main content
- Optimize for readability (short sentences, clear language)
- For beginners: Emphasize simplicity and success
- For advanced: Mention nuanced techniques or expert insights

Generate only the introduction text, no meta commentary."""

        return prompt

    @staticmethod
    def get_meta_description_prompt(context: Dict[str, Any]) -> str:
        """
        Generate AI prompt for SEO meta description.

        Args:
            context: Dictionary with keys:
                - title: str (optional) - Post title
                - introduction: str (optional) - Post introduction
                - related_plants: list (optional) - Related plant species
                - difficulty_level: str (optional) - beginner/intermediate/advanced

        Returns:
            Formatted prompt for AI meta description generation
        """
        title = context.get('title', '')
        introduction = context.get('introduction', '')
        related_plants = context.get('related_plants', [])
        difficulty_level = context.get('difficulty_level', '')

        # Extract plant names
        plant_names = []
        if related_plants:
            plant_names = [p.get('common_name') or p.get('scientific_name', '')
                          for p in related_plants[:2]]

        prompt = f"""Generate an SEO-optimized meta description for a plant care blog post.

Title: {title or 'Plant Care Guide'}
Plant(s): {', '.join(plant_names) if plant_names else 'Various plants'}
{f"Difficulty: {difficulty_level}" if difficulty_level else ""}

Content Preview:
{introduction[:200] if introduction else 'Plant care guide'}

Requirements:
- Exactly 140-160 characters (strict SEO requirement)
- Include primary plant name
- Use action verbs: "Learn", "Discover", "Master"
- Include benefit or outcome
- Natural keyword placement (no stuffing)
- Compelling call-to-action phrase
- No ellipsis or incomplete sentences

Examples of good meta descriptions:
- "Learn how to care for Monstera Deliciosa with our complete guide. Master watering, light, and propagation for healthy, thriving plants."
- "Discover 5 essential Snake Plant care tips. Perfect for beginners! Get expert advice on water, light, soil, and common problems."

Generate only the meta description, no additional text."""

        return prompt

    @staticmethod
    def get_content_block_prompt(block_type: str, context: Dict[str, Any]) -> str:
        """
        Generate AI prompt for StreamField content blocks.

        Args:
            block_type: Type of content block (heading, paragraph, care_tips, etc.)
            context: Dictionary with block-specific context

        Returns:
            Formatted prompt for AI content generation
        """
        plant_name = context.get('plant_name', '')
        difficulty_level = context.get('difficulty_level', 'beginner')

        if block_type == 'heading':
            return f"""Generate a clear, descriptive heading for a plant care article section.

Plant: {plant_name or 'Various plants'}
Context: {context.get('section_context', 'Plant care information')}

Requirements:
- 3-8 words
- Use title case
- Action-oriented or benefit-focused
- No punctuation except necessary colons

Examples:
- Essential Watering Guidelines
- Common Problems and Solutions
- Light Requirements: Finding the Perfect Spot

Generate only the heading text."""

        elif block_type == 'paragraph':
            section_topic = context.get('section_topic', 'plant care')

            return f"""Generate informative paragraph content for a plant care article.

Plant: {plant_name or 'Various plants'}
Topic: {section_topic}
Audience: {difficulty_level.capitalize()} gardeners

Requirements:
- 3-5 sentences
- Clear, actionable information
- Conversational but authoritative tone
- Include specific tips or techniques
- Use simple language for beginners, technical terms for advanced
- No promotional language

Generate only the paragraph content."""

        elif block_type == 'care_instructions':
            care_aspect = context.get('care_aspect', 'general')

            # Use PlantAIPrompts for plant-specific care instructions
            if plant_name and care_aspect in ['watering', 'lighting', 'fertilizing']:
                return PlantAIPrompts.get_care_instructions_prompt(
                    plant_name, care_aspect, context
                )

            return f"""Generate specific care instructions for {care_aspect}.

Plant: {plant_name or 'Various plants'}
Aspect: {care_aspect}

Requirements:
- Bullet-point format
- 3-5 specific, actionable points
- Include frequency/amount details
- Mention seasonal variations if relevant
- Warning about common mistakes

Generate only the care instruction points."""

        else:
            return f"""Generate {block_type} content for a plant care article.

Context: {context}

Generate clear, helpful content appropriate for the block type."""


class BlogAIIntegration:
    """
    Integration layer between Wagtail AI and blog services.

    Handles AI generation requests with caching and rate limiting.
    """

    @classmethod
    def generate_content(
        cls,
        field_name: str,
        context: Dict[str, Any],
        user: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Generate AI content for a blog field with caching and rate limiting.

        Args:
            field_name: Name of field to generate content for
            context: Context dictionary for prompt generation
            user: User making the request (for rate limiting)

        Returns:
            Dict with keys:
                - success: bool
                - content: str (if successful)
                - error: str (if failed)
                - cached: bool
                - remaining_calls: int
        """
        from .services import AICacheService, AIRateLimiter

        # Check rate limits
        if user:
            user_id = user.id if hasattr(user, 'id') else 0
            is_staff = user.is_staff if hasattr(user, 'is_staff') else False

            if not AIRateLimiter.check_user_limit(user_id, is_staff):
                remaining = AIRateLimiter.get_remaining_calls(user_id, is_staff)
                return {
                    'success': False,
                    'error': f'AI rate limit exceeded. You can make {AIRateLimiter.USER_LIMIT if not is_staff else AIRateLimiter.STAFF_LIMIT} requests per hour. Try again later.',
                    'remaining_calls': remaining
                }

            if not AIRateLimiter.check_global_limit():
                return {
                    'success': False,
                    'error': 'Global AI rate limit exceeded. Please try again in a few minutes.'
                }

        # Generate appropriate prompt
        prompt_generators = {
            'title': BlogAIPrompts.get_title_prompt,
            'introduction': BlogAIPrompts.get_introduction_prompt,
            'meta_description': BlogAIPrompts.get_meta_description_prompt,
        }

        if field_name not in prompt_generators:
            return {
                'success': False,
                'error': f'Unsupported field: {field_name}'
            }

        prompt = prompt_generators[field_name](context)

        # Check cache
        cached_response = AICacheService.get_cached_response(field_name, prompt)
        if cached_response:
            remaining = AIRateLimiter.get_remaining_calls(
                user_id if user else 0,
                is_staff if user else False
            )
            return {
                'success': True,
                'content': cached_response.get('text', ''),
                'cached': True,
                'remaining_calls': remaining
            }

        # Generate AI content
        try:
            from wagtail_ai.utils import get_ai_text

            ai_content = get_ai_text(prompt)

            # Cache the response
            response = {'text': ai_content}
            AICacheService.set_cached_response(field_name, prompt, response)

            remaining = AIRateLimiter.get_remaining_calls(
                user_id if user else 0,
                is_staff if user else False
            )

            return {
                'success': True,
                'content': ai_content,
                'cached': False,
                'remaining_calls': remaining
            }

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"[AI] Content generation failed for {field_name}: {str(e)}")

            return {
                'success': False,
                'error': f'AI content generation failed: {str(e)}'
            }
