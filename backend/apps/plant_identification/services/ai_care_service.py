"""
AI-powered plant care instruction service using OpenAI.

Generates comprehensive, personalized care instructions for identified plants.
"""

import os
import json
import logging
from typing import Dict, Optional
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class AIPlantCareService:
    """
    Service for generating AI-powered plant care instructions.
    
    This service uses OpenAI's GPT model to generate comprehensive,
    personalized care instructions based on plant identification results.
    """
    
    def __init__(self):
        """Initialize the AI care service."""
        self.api_key = getattr(settings, 'OPENAI_API_KEY', os.environ.get('OPENAI_API_KEY'))
        self.model = getattr(settings, 'OPENAI_MODEL', 'gpt-3.5-turbo')
        self.max_tokens = getattr(settings, 'OPENAI_MAX_TOKENS', 1500)
        
        if not self.api_key:
            logger.warning("OpenAI API key not configured - AI care instructions will not be available")
    
    def generate_care_instructions(self, plant_name: str, common_names: str = "", 
                                  location: str = "", climate: str = "", 
                                  experience_level: str = "beginner", 
                                  botanical_data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Generate AI-powered care instructions for a plant using rich botanical data.
        
        Args:
            plant_name: Scientific name of the plant
            common_names: Common names of the plant
            location: User's location (for climate-specific advice)
            climate: Climate zone information
            experience_level: User's gardening experience level
            botanical_data: Rich botanical data from PlantNet + Trefle APIs including:
                          - PlantNet: native_regions, taxonomy, growth_form, iucn_category
                          - Trefle: light_requirements, water_requirements, soil_ph, hardiness_zones,
                                   mature_height, bloom_time, flower_color, native_regions
            
        Returns:
            Dictionary containing comprehensive care instructions with 25+ categories or None if generation fails
        """
        if not self.api_key:
            logger.error("OpenAI API key not configured")
            return self._generate_fallback_instructions(plant_name, common_names)
        
        try:
            import openai
            
            # Configure OpenAI client
            client = openai.OpenAI(api_key=self.api_key)
            
            # Create the enhanced prompt using rich botanical data
            prompt = self._create_enhanced_care_prompt(plant_name, common_names, location, climate, experience_level, botanical_data)
            
            # Generate care instructions using OpenAI
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a professional botanist and plant care expert. Generate comprehensive, accurate plant care instructions in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            care_instructions = json.loads(response.choices[0].message.content)
            
            # Add metadata
            care_instructions['generated_at'] = timezone.now().isoformat()
            care_instructions['ai_model'] = self.model
            care_instructions['confidence'] = 'high'
            
            logger.info(f"Successfully generated AI care instructions for {plant_name}")
            return care_instructions
            
        except ImportError:
            logger.error("OpenAI library not installed. Run: pip install openai")
            return self._generate_fallback_instructions(plant_name, common_names)
            
        except Exception as e:
            logger.error(f"Error generating AI care instructions: {str(e)}")
            return self._generate_fallback_instructions(plant_name, common_names)
    
    def _create_care_prompt(self, plant_name: str, common_names: str, 
                           location: str, climate: str, experience_level: str) -> str:
        """
        Create a detailed prompt for generating care instructions.
        
        Args:
            plant_name: Scientific name of the plant
            common_names: Common names of the plant
            location: User's location
            climate: Climate zone
            experience_level: User's experience level
            
        Returns:
            Formatted prompt string
        """
        context_parts = []
        
        if common_names:
            context_parts.append(f"Common names: {common_names}")
        if location:
            context_parts.append(f"Location: {location}")
        if climate:
            context_parts.append(f"Climate: {climate}")
        if experience_level and experience_level != "beginner":
            context_parts.append(f"Experience level: {experience_level}")
        
        context = ". ".join(context_parts) if context_parts else ""
        
        prompt = f"""Generate comprehensive care instructions for {plant_name}. {context}

Please provide the care instructions in the following JSON format:
{{
    "overview": "Brief overview of the plant and its care requirements",
    "difficulty_level": "easy/moderate/difficult",
    "light": {{
        "requirement": "Full sun/Partial shade/Full shade/etc",
        "details": "Specific light requirements and tips",
        "indoor_placement": "Best indoor locations for this plant"
    }},
    "water": {{
        "frequency": "How often to water",
        "amount": "How much water to give",
        "method": "Best watering method",
        "seasonal_changes": "How watering changes by season",
        "signs_of_overwatering": "What to watch for",
        "signs_of_underwatering": "What to watch for"
    }},
    "soil": {{
        "type": "Preferred soil type",
        "ph_range": "Ideal pH range",
        "drainage": "Drainage requirements",
        "mix_recipe": "Recommended soil mix if applicable"
    }},
    "temperature": {{
        "ideal_range": "Ideal temperature range",
        "tolerance": "Temperature tolerance",
        "seasonal_care": "Temperature-related seasonal care"
    }},
    "humidity": {{
        "requirement": "Humidity level needed",
        "tips": "How to maintain proper humidity"
    }},
    "fertilizer": {{
        "type": "Recommended fertilizer type",
        "frequency": "How often to fertilize",
        "seasonal_schedule": "Fertilizing schedule by season",
        "dilution": "Dilution recommendations"
    }},
    "pruning": {{
        "when": "When to prune",
        "how": "How to prune properly",
        "frequency": "How often to prune"
    }},
    "repotting": {{
        "frequency": "How often to repot",
        "signs": "Signs that repotting is needed",
        "best_time": "Best time of year to repot",
        "pot_size": "How to choose pot size"
    }},
    "propagation": {{
        "methods": ["List of propagation methods"],
        "best_method": "Most successful method",
        "instructions": "Step-by-step propagation guide",
        "timing": "Best time to propagate"
    }},
    "common_issues": {{
        "pests": ["Common pests and treatments"],
        "diseases": ["Common diseases and treatments"],
        "problems": ["Common problems and solutions"]
    }},
    "toxicity": {{
        "pets": "Is it toxic to pets?",
        "humans": "Is it toxic to humans?",
        "level": "Toxicity level if applicable"
    }},
    "special_care": ["Any special care tips or considerations"],
    "companion_plants": ["Good companion plants if applicable"],
    "fun_facts": ["Interesting facts about this plant"]
}}

Ensure all information is accurate and helpful for a {experience_level} gardener."""
        
        return prompt
    
    def _create_enhanced_care_prompt(self, plant_name: str, common_names: str, 
                                   location: str, climate: str, experience_level: str,
                                   botanical_data: Optional[Dict] = None) -> str:
        """
        Create an enhanced prompt using rich botanical data from PlantNet + Trefle APIs.
        
        Args:
            plant_name: Scientific name of the plant
            common_names: Common names of the plant
            location: User's location
            climate: Climate zone
            experience_level: User's experience level
            botanical_data: Rich data from PlantNet + Trefle APIs
            
        Returns:
            Enhanced formatted prompt string with comprehensive botanical context
        """
        # Build comprehensive context using rich botanical data
        context_parts = []
        
        if common_names:
            context_parts.append(f"Common names: {common_names}")
        if location:
            context_parts.append(f"User location: {location}")
        if climate:
            context_parts.append(f"Climate zone: {climate}")
        if experience_level and experience_level != "beginner":
            context_parts.append(f"Experience level: {experience_level}")
        
        # Add rich botanical data if available
        if botanical_data:
            # PlantNet data
            plantnet_data = botanical_data.get('plantnet_data', {})
            if plantnet_data.get('native_regions'):
                context_parts.append(f"Native range: {plantnet_data['native_regions']}")
            if plantnet_data.get('iucn_category'):
                context_parts.append(f"Conservation status: {plantnet_data['iucn_category']}")
            if plantnet_data.get('growth_form'):
                context_parts.append(f"Natural growth form: {plantnet_data['growth_form']}")
            
            # Trefle data
            trefle_data = botanical_data.get('trefle_data', {})
            if trefle_data.get('light_requirements'):
                context_parts.append(f"Light preference: {trefle_data['light_requirements']}")
            if trefle_data.get('water_requirements'):
                context_parts.append(f"Water needs: {trefle_data['water_requirements']}")
            if trefle_data.get('mature_height_min') and trefle_data.get('mature_height_max'):
                context_parts.append(f"Mature size: {trefle_data['mature_height_min']}-{trefle_data['mature_height_max']}cm")
            if trefle_data.get('hardiness_zone_min') and trefle_data.get('hardiness_zone_max'):
                context_parts.append(f"Hardiness zones: {trefle_data['hardiness_zone_min']}-{trefle_data['hardiness_zone_max']}")
            if trefle_data.get('bloom_time'):
                context_parts.append(f"Bloom period: {trefle_data['bloom_time']}")
            if trefle_data.get('soil_ph_min') and trefle_data.get('soil_ph_max'):
                context_parts.append(f"Soil pH preference: {trefle_data['soil_ph_min']}-{trefle_data['soil_ph_max']}")
        
        context = ". ".join(context_parts) if context_parts else ""
        
        prompt = f"""Generate comprehensive care instructions for {plant_name}. {context}

Using the rich botanical data provided, create detailed care instructions with 25+ categories. Consider the plant's native habitat, growth characteristics, and environmental preferences when providing advice.

Please provide enhanced care instructions in the following JSON format:

{{
    "overview": "Comprehensive overview including native habitat context and growth characteristics",
    "difficulty_level": "very_easy/easy/moderate/challenging/difficult",
    
    "regional_adaptation": {{
        "local_climate_notes": "Specific advice for user's climate zone based on plant's native range",
        "seasonal_adjustments": "Local seasonal care variations considering native growing patterns",
        "frost_protection": "Cold weather protection based on hardiness zones",
        "heat_stress_prevention": "Hot weather care modifications for climate adaptation"
    }},
    
    "light": {{
        "requirement": "Detailed light requirements based on native habitat",
        "details": "Comprehensive light management using botanical data",
        "indoor_placement": "Optimal indoor locations with scientific reasoning",
        "outdoor_placement": "Outdoor growing considerations based on native conditions",
        "light_troubleshooting": "Signs of light issues and evidence-based solutions"
    }},
    
    "water": {{
        "frequency": "Detailed watering schedule based on water requirements data",
        "amount": "Specific water amounts based on plant size and native rainfall",
        "method": "Best watering techniques for this species' root system",
        "seasonal_changes": "Seasonal watering adaptations based on native climate patterns",
        "water_quality": "Water quality preferences based on native soil conditions",
        "signs_of_overwatering": "Comprehensive overwatering symptoms",
        "signs_of_underwatering": "Comprehensive underwatering symptoms",
        "recovery_methods": "Evidence-based recovery from watering issues"
    }},
    
    "soil": {{
        "type": "Ideal soil composition based on native habitat analysis",
        "ph_range": "Specific pH requirements using botanical pH data",
        "drainage": "Drainage requirements based on native growing conditions", 
        "mix_recipe": "Custom soil mix recipe with scientific ratios",
        "amendments": "Beneficial soil amendments based on native soil analysis",
        "repotting_soil": "Special considerations for container growing"
    }},
    
    "temperature": {{
        "ideal_range": "Optimal temperature range using hardiness zone data",
        "tolerance": "Temperature tolerance limits based on native climate",
        "seasonal_care": "Temperature-based seasonal adjustments",
        "microclimate_tips": "Creating ideal microclimates using native habitat knowledge"
    }},
    
    "humidity": {{
        "requirement": "Specific humidity needs based on native environment",
        "measurement": "How to monitor and measure humidity accurately",
        "tips": "Practical humidity management techniques",
        "seasonal_adjustments": "Humidity changes by season based on native patterns"
    }},
    
    "fertilizer": {{
        "type": "Specific fertilizer recommendations based on native soil nutrients",
        "npk_ratios": "Ideal NPK ratios for different growth stages",
        "frequency": "Detailed feeding schedule aligned with natural growth cycles",
        "seasonal_schedule": "Month-by-month feeding plan based on bloom time",
        "organic_options": "Organic fertilizer alternatives mimicking native nutrients",
        "signs_of_over_fertilizing": "Fertilizer burn symptoms and prevention",
        "signs_of_under_fertilizing": "Nutrient deficiency identification"
    }},
    
    "pruning": {{
        "when": "Optimal pruning timing based on natural growth cycles",
        "how": "Detailed pruning techniques specific to growth form",
        "frequency": "Pruning schedule aligned with plant's natural patterns",
        "tools": "Recommended tools for this plant's stem/branch structure",
        "wound_care": "Post-pruning care based on plant's healing characteristics"
    }},
    
    "repotting": {{
        "frequency": "Repotting schedule based on growth rate data",
        "signs": "Clear signs repotting is needed for this species",
        "best_time": "Optimal repotting season based on growth cycles",
        "pot_size": "Pot sizing based on mature size data",
        "technique": "Species-specific repotting process",
        "post_repot_care": "Recovery care tailored to plant's stress response"
    }},
    
    "propagation": {{
        "methods": "All viable propagation methods for this species",
        "best_method": "Most successful method based on plant biology",
        "advanced_methods": "Advanced techniques for experienced growers",
        "instructions": "Detailed propagation steps with scientific basis",
        "timing": "Best seasons based on natural reproduction cycles",
        "success_rates": "Expected success rates with proper technique",
        "troubleshooting": "Common propagation issues and solutions"
    }},
    
    "native_habitat_simulation": {{
        "ecosystem_context": "How plant grows in native ecosystem",
        "companion_plants": "Native companion species and beneficial relationships",
        "natural_conditions": "Key natural conditions to replicate indoors/outdoors"
    }},
    
    "conservation_awareness": {{
        "status": "Conservation status from IUCN data if available",
        "threats": "Threats to wild populations",
        "ethical_sourcing": "How to source plants sustainably"
    }},
    
    "common_issues": {{
        "pests": "Comprehensive pest identification and evidence-based treatments",
        "diseases": "Disease prevention and treatment based on susceptibilities",
        "environmental_stress": "Stress symptoms and science-based solutions",
        "troubleshooting_guide": "Visual problem diagnosis with botanical reasoning"
    }},
    
    "advanced_care": {{
        "growth_optimization": "Maximizing growth using environmental data",
        "specialty_techniques": "Advanced techniques for optimal cultivation",
        "competition_growing": "Show-quality growing methods"
    }},
    
    "toxicity": {{
        "pets": "Pet safety based on known plant compounds",
        "humans": "Human safety information with severity levels",
        "level": "Toxicity classification with scientific basis",
        "symptoms": "Poisoning symptoms and timeline",
        "first_aid": "Emergency response procedures"
    }},
    
    "commercial_varieties": {{
        "cultivars": "Popular cultivars and their botanical differences",
        "variety_specific_care": "Care variations between cultivars",
        "availability": "Sourcing information for different varieties"
    }},
    
    "seasonal_calendar": {{
        "spring": "Spring care aligned with natural growth resumption",
        "summer": "Summer care based on peak growing season needs",
        "fall": "Fall preparation using natural dormancy patterns",
        "winter": "Winter care based on natural dormancy requirements"
    }},
    
    "troubleshooting_visual_guide": "Comprehensive problem identification with scientific explanations",
    "success_metrics": "Evidence-based indicators of plant health and thriving",
    "community_resources": "Scientific and horticultural resources for continued learning"
}}

Ensure all advice is scientifically accurate, tailored for {experience_level} level, and specifically adapted for {location} climate conditions using the botanical data provided. Prioritize evidence-based recommendations over generic advice."""
        
        return prompt
    
    def _generate_fallback_instructions(self, plant_name: str, common_names: str) -> Dict:
        """
        Generate basic fallback care instructions when AI is not available.
        
        Args:
            plant_name: Scientific name of the plant
            common_names: Common names of the plant
            
        Returns:
            Dictionary containing basic care instructions
        """
        display_name = common_names.split(',')[0].strip() if common_names else plant_name
        
        return {
            "overview": f"Care guide for {display_name}. These are general guidelines - observe your plant and adjust care as needed.",
            "difficulty_level": "moderate",
            "light": {
                "requirement": "Bright, indirect light",
                "details": "Most plants thrive in bright, indirect light. Avoid direct sunlight which can burn leaves.",
                "indoor_placement": "Near an east or west-facing window"
            },
            "water": {
                "frequency": "When top inch of soil is dry",
                "amount": "Water thoroughly until water drains from bottom",
                "method": "Water at soil level, avoiding leaves",
                "seasonal_changes": "Reduce watering in winter months",
                "signs_of_overwatering": "Yellowing leaves, soft stems, mold on soil",
                "signs_of_underwatering": "Drooping leaves, dry soil, brown leaf tips"
            },
            "soil": {
                "type": "Well-draining potting mix",
                "ph_range": "6.0-7.0",
                "drainage": "Good drainage is essential",
                "mix_recipe": "Standard potting soil with added perlite"
            },
            "temperature": {
                "ideal_range": "65-75°F (18-24°C)",
                "tolerance": "Can tolerate brief periods outside this range",
                "seasonal_care": "Keep away from cold drafts in winter"
            },
            "humidity": {
                "requirement": "40-60%",
                "tips": "Mist occasionally or use a humidity tray"
            },
            "fertilizer": {
                "type": "Balanced liquid fertilizer",
                "frequency": "Every 2-4 weeks during growing season",
                "seasonal_schedule": "Spring and summer only",
                "dilution": "Half strength"
            },
            "pruning": {
                "when": "Spring or early summer",
                "how": "Remove dead or damaged growth",
                "frequency": "As needed"
            },
            "repotting": {
                "frequency": "Every 1-2 years",
                "signs": "Roots growing through drainage holes",
                "best_time": "Spring",
                "pot_size": "1-2 inches larger than current pot"
            },
            "propagation": {
                "methods": ["Stem cuttings", "Division"],
                "best_method": "Stem cuttings",
                "instructions": "Take 4-6 inch cuttings, remove lower leaves, root in water or soil",
                "timing": "Spring or summer"
            },
            "common_issues": {
                "pests": ["Check regularly for aphids, spider mites, and mealybugs"],
                "diseases": ["Watch for root rot from overwatering"],
                "problems": ["Yellowing leaves often indicate watering issues"]
            },
            "toxicity": {
                "pets": "Research this specific plant for pet safety",
                "humans": "Research this specific plant for human safety",
                "level": "Unknown - please research"
            },
            "special_care": ["Observe your plant and adjust care based on its response"],
            "companion_plants": [],
            "fun_facts": [f"{display_name} is a wonderful addition to any plant collection!"],
            "generated_at": timezone.now().isoformat(),
            "ai_model": "fallback",
            "confidence": "low",
            "note": "These are general care guidelines. For best results, research your specific plant variety."
        }
    
    def update_result_with_care_instructions(self, result, care_instructions: Dict):
        """
        Update a PlantIdentificationResult with AI-generated care instructions.
        
        Args:
            result: PlantIdentificationResult instance
            care_instructions: Dictionary of care instructions
        """
        result.ai_care_instructions = care_instructions
        result.care_instructions_generated_at = timezone.now()
        result.save(update_fields=['ai_care_instructions', 'care_instructions_generated_at'])
        
        logger.info(f"Updated result {result.id} with AI care instructions")