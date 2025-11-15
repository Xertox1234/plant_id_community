"""
Care Assistant Service

AI-powered plant care recommendations and plans.

Provides:
- Custom care plans based on plant + climate + garden conditions
- Problem diagnosis and solutions
- Seasonal care recommendations
- Integration with OpenAI via existing infrastructure
"""

import logging
from typing import Optional, Dict, Any, List
from django.conf import settings
from django.core.cache import cache

from ..models import GardenPlant, Garden, PlantCareLibrary
from ..constants import (
    CACHE_TIMEOUT_CARE_PLAN,
    CACHE_KEY_CARE_PLAN
)

logger = logging.getLogger(__name__)


class CareAssistantService:
    """
    AI-powered garden care assistant.

    Uses OpenAI (via Wagtail AI infrastructure) to generate:
    - Personalized care plans
    - Problem diagnosis
    - Seasonal recommendations
    """

    @classmethod
    def get_openai_client(cls):
        """Get OpenAI client if available."""
        try:
            import openai
            api_key = getattr(settings, 'OPENAI_API_KEY', None)
            if not api_key:
                return None
            openai.api_key = api_key
            return openai
        except ImportError:
            logger.warning("[AI] OpenAI library not installed")
            return None

    @classmethod
    def generate_care_plan(
        cls,
        plant: GardenPlant,
        include_weather: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Generate AI-powered care plan for a specific plant.

        Args:
            plant: GardenPlant instance
            include_weather: Whether to include weather-based recommendations

        Returns:
            Dict with:
            - care_plan: str (AI-generated care plan)
            - watering_schedule: dict
            - fertilizing_schedule: dict
            - seasonal_tips: list
            - common_issues: list
        """
        # Check cache first
        cache_key = CACHE_KEY_CARE_PLAN.format(
            species=plant.scientific_name or plant.common_name,
            climate=plant.garden.climate_zone or 'unknown'
        )
        cached_plan = cache.get(cache_key)
        if cached_plan:
            logger.info(f"[CACHE] HIT for care plan: {cache_key}")
            return cached_plan

        # Try to get care library data first
        care_library = cls._get_care_library_data(plant)

        # Build context for AI
        context = cls._build_plant_context(plant, care_library, include_weather)

        # Generate AI care plan
        ai_plan = cls._generate_ai_care_plan(context)

        if not ai_plan:
            # Fallback to care library data if AI unavailable
            if care_library:
                plan = cls._fallback_care_plan(plant, care_library)
            else:
                logger.warning(f"[AI] No care data available for {plant.common_name}")
                return None
        else:
            plan = ai_plan

        # Cache the plan (30 days)
        cache.set(cache_key, plan, CACHE_TIMEOUT_CARE_PLAN)
        logger.info(f"[AI] Cached care plan for {plant.common_name}")

        return plan

    @classmethod
    def _get_care_library_data(
        cls,
        plant: GardenPlant
    ) -> Optional[PlantCareLibrary]:
        """Get care library data for plant."""
        if not plant.scientific_name:
            return None

        try:
            return PlantCareLibrary.objects.get(
                scientific_name__iexact=plant.scientific_name
            )
        except PlantCareLibrary.DoesNotExist:
            return None

    @classmethod
    def _build_plant_context(
        cls,
        plant: GardenPlant,
        care_library: Optional[PlantCareLibrary],
        include_weather: bool
    ) -> str:
        """Build context string for AI prompt."""
        context_parts = [
            f"Plant: {plant.common_name}",
            f"Scientific name: {plant.scientific_name or 'Unknown'}",
            f"Planted: {plant.planted_date}",
            f"Current health: {plant.get_health_status_display()}",
        ]

        if plant.garden.climate_zone:
            context_parts.append(f"Climate zone: {plant.garden.climate_zone}")

        if plant.garden.location and 'city' in plant.garden.location:
            context_parts.append(f"Location: {plant.garden.location['city']}")

        if care_library:
            context_parts.extend([
                f"Sunlight needs: {care_library.get_sunlight_display()}",
                f"Water needs: {care_library.get_water_needs_display()}",
                f"Soil type: {care_library.soil_type or 'Not specified'}",
            ])

            if care_library.common_pests:
                context_parts.append(f"Common pests: {', '.join(care_library.common_pests)}")

        if plant.notes:
            context_parts.append(f"Gardener's notes: {plant.notes}")

        return "\n".join(context_parts)

    @classmethod
    def _generate_ai_care_plan(
        cls,
        context: str
    ) -> Optional[Dict[str, Any]]:
        """Generate care plan using OpenAI."""
        client = cls.get_openai_client()
        if not client:
            logger.info("[AI] OpenAI not available, using fallback")
            return None

        try:
            prompt = f"""You are an expert gardener providing personalized plant care advice.

Given the following plant information:
{context}

Please provide a comprehensive care plan including:
1. Watering schedule (frequency, amount, best time of day)
2. Fertilizing schedule (frequency, type of fertilizer)
3. Seasonal care tips (spring, summer, fall, winter)
4. Common issues to watch for and how to address them
5. General care recommendations

Format your response as a structured JSON with the following keys:
- watering_schedule
- fertilizing_schedule
- seasonal_tips (array)
- common_issues (array)
- general_recommendations

Keep recommendations practical and specific to this plant and climate."""

            import openai
            response = openai.chat.completions.create(
                model="gpt-4o-mini",  # Cost-effective model
                messages=[
                    {"role": "system", "content": "You are an expert gardening advisor."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )

            # Parse response
            import json
            content = response.choices[0].message.content

            # Try to extract JSON from response
            if content.startswith('```json'):
                content = content.split('```json')[1].split('```')[0].strip()
            elif content.startswith('```'):
                content = content.split('```')[1].split('```')[0].strip()

            plan_data = json.loads(content)

            logger.info("[AI] Successfully generated AI care plan")
            return plan_data

        except Exception as e:
            logger.error(f"[ERROR] AI care plan generation failed: {str(e)}")
            return None

    @classmethod
    def _fallback_care_plan(
        cls,
        plant: GardenPlant,
        care_library: PlantCareLibrary
    ) -> Dict[str, Any]:
        """Generate basic care plan from library data."""
        from ..constants import WATER_NEED_FREQUENCY

        watering_days = care_library.watering_frequency_days or \
            WATER_NEED_FREQUENCY.get(care_library.water_needs, 3)

        return {
            'watering_schedule': {
                'frequency': f"Every {watering_days} days",
                'amount': 'Water until soil is moist but not waterlogged',
                'best_time': 'Early morning or evening'
            },
            'fertilizing_schedule': {
                'frequency': f"Every {care_library.fertilizing_frequency_days or 14} days during growing season",
                'type': 'Balanced fertilizer appropriate for plant type'
            },
            'seasonal_tips': [
                'Monitor for pests regularly',
                'Adjust watering based on weather conditions',
                'Prune as needed to maintain plant health'
            ],
            'common_issues': [
                {'pest': pest, 'solution': 'Monitor and treat as needed'}
                for pest in (care_library.common_pests or [])
            ],
            'general_recommendations': care_library.care_instructions or 'Follow standard care guidelines for this plant type'
        }

    @classmethod
    def diagnose_problem(
        cls,
        plant: GardenPlant,
        symptoms: str
    ) -> Optional[Dict[str, Any]]:
        """
        Diagnose plant problem using AI.

        Args:
            plant: GardenPlant instance
            symptoms: Description of symptoms (e.g., "yellowing leaves, wilting")

        Returns:
            Dict with:
            - diagnosis: str (likely cause)
            - severity: str ('low', 'medium', 'high')
            - treatment: str (recommended treatment)
            - prevention: str (how to prevent in future)
        """
        client = cls.get_openai_client()
        if not client:
            logger.info("[AI] OpenAI not available for diagnosis")
            return None

        context = cls._build_plant_context(plant, cls._get_care_library_data(plant), False)

        try:
            prompt = f"""You are an expert plant pathologist diagnosing a plant problem.

Plant information:
{context}

Symptoms reported:
{symptoms}

Please provide:
1. Most likely diagnosis (disease, pest, or environmental issue)
2. Severity level (low, medium, high)
3. Recommended treatment steps
4. Prevention measures for the future

Format as JSON with keys: diagnosis, severity, treatment, prevention"""

            import openai
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert plant pathologist."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )

            # Parse response
            import json
            content = response.choices[0].message.content

            if content.startswith('```json'):
                content = content.split('```json')[1].split('```')[0].strip()
            elif content.startswith('```'):
                content = content.split('```')[1].split('```')[0].strip()

            diagnosis = json.loads(content)

            logger.info(f"[AI] Generated diagnosis for {plant.common_name}")
            return diagnosis

        except Exception as e:
            logger.error(f"[ERROR] AI diagnosis failed: {str(e)}")
            return None

    @classmethod
    def get_seasonal_tasks(
        cls,
        garden: Garden,
        season: str
    ) -> List[Dict[str, Any]]:
        """
        Get AI-generated seasonal tasks for entire garden.

        Args:
            garden: Garden instance
            season: 'spring', 'summer', 'fall', or 'winter'

        Returns:
            List of task dicts with:
            - title: str
            - description: str
            - priority: str ('low', 'medium', 'high')
            - category: str
        """
        client = cls.get_openai_client()
        if not client:
            # Return basic seasonal tasks
            return cls._get_default_seasonal_tasks(season)

        # Build garden context
        plants = garden.plants.all()
        plant_list = ", ".join([p.common_name for p in plants[:10]])  # Limit to 10 for context

        context = f"""Garden location: {garden.climate_zone or 'Unknown'}
Number of plants: {plants.count()}
Sample plants: {plant_list}
Season: {season}"""

        try:
            prompt = f"""You are an expert gardener providing seasonal task recommendations.

Garden information:
{context}

Please provide 5-7 important gardening tasks for this season.

Format as JSON array with objects containing:
- title: Short task title
- description: Detailed description
- priority: 'low', 'medium', or 'high'
- category: 'planting', 'maintenance', 'harvesting', or 'preparation'"""

            import openai
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert gardening advisor."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800
            )

            # Parse response
            import json
            content = response.choices[0].message.content

            if content.startswith('```json'):
                content = content.split('```json')[1].split('```')[0].strip()
            elif content.startswith('```'):
                content = content.split('```')[1].split('```')[0].strip()

            tasks = json.loads(content)

            logger.info(f"[AI] Generated {len(tasks)} seasonal tasks for {season}")
            return tasks

        except Exception as e:
            logger.error(f"[ERROR] AI seasonal tasks failed: {str(e)}")
            return cls._get_default_seasonal_tasks(season)

    @classmethod
    def _get_default_seasonal_tasks(cls, season: str) -> List[Dict[str, Any]]:
        """Get default seasonal tasks (fallback)."""
        seasonal_defaults = {
            'spring': [
                {
                    'title': 'Start seeds indoors',
                    'description': 'Begin starting warm-season seeds indoors',
                    'priority': 'high',
                    'category': 'planting'
                },
                {
                    'title': 'Prepare garden beds',
                    'description': 'Turn soil and add compost to beds',
                    'priority': 'high',
                    'category': 'preparation'
                },
                {
                    'title': 'Prune dormant plants',
                    'description': 'Prune fruit trees and shrubs before growth starts',
                    'priority': 'medium',
                    'category': 'maintenance'
                }
            ],
            'summer': [
                {
                    'title': 'Water regularly',
                    'description': 'Increase watering frequency during hot weather',
                    'priority': 'high',
                    'category': 'maintenance'
                },
                {
                    'title': 'Harvest vegetables',
                    'description': 'Harvest mature crops regularly',
                    'priority': 'high',
                    'category': 'harvesting'
                },
                {
                    'title': 'Monitor for pests',
                    'description': 'Check plants for pest damage and treat as needed',
                    'priority': 'medium',
                    'category': 'maintenance'
                }
            ],
            'fall': [
                {
                    'title': 'Plant bulbs',
                    'description': 'Plant spring-flowering bulbs',
                    'priority': 'high',
                    'category': 'planting'
                },
                {
                    'title': 'Clean up garden',
                    'description': 'Remove dead plants and debris',
                    'priority': 'medium',
                    'category': 'maintenance'
                },
                {
                    'title': 'Mulch beds',
                    'description': 'Add mulch to protect plants over winter',
                    'priority': 'medium',
                    'category': 'preparation'
                }
            ],
            'winter': [
                {
                    'title': 'Plan next season',
                    'description': 'Review last year and plan for spring',
                    'priority': 'low',
                    'category': 'preparation'
                },
                {
                    'title': 'Protect sensitive plants',
                    'description': 'Cover or bring indoors plants sensitive to frost',
                    'priority': 'high',
                    'category': 'maintenance'
                },
                {
                    'title': 'Maintain tools',
                    'description': 'Clean and sharpen gardening tools',
                    'priority': 'low',
                    'category': 'maintenance'
                }
            ]
        }

        return seasonal_defaults.get(season, [])
