"""
Custom AI prompts for plant-related content generation in Wagtail AI.

This module defines specialized prompts for generating plant care content,
descriptions, and gardening advice using the Wagtail AI system.
"""

from typing import Dict, List, Optional


class PlantAIPrompts:
    """
    Collection of AI prompts specifically designed for plant content generation.
    """
    
    @staticmethod
    def get_plant_description_prompt(plant_name: str, existing_data: Optional[Dict] = None) -> str:
        """
        Generate a prompt for creating plant descriptions.
        
        Args:
            plant_name: Name of the plant (scientific or common)
            existing_data: Any existing plant data to inform the description
            
        Returns:
            Formatted AI prompt string
        """
        base_prompt = f"""Write a concise, engaging description for {plant_name} that would appeal to home gardeners and plant enthusiasts.

The description should include:
- Key identifying characteristics (leaves, flowers, growth habit)
- Why this plant is popular with gardeners
- Notable features or benefits
- Keep it accessible and encouraging for beginners

Style guidelines:
- Write in an enthusiastic but informative tone
- Use 2-3 sentences maximum
- Avoid overly technical botanical terms
- Focus on what makes this plant special"""

        if existing_data:
            additional_context = []
            if existing_data.get('plant_type'):
                additional_context.append(f"Plant type: {existing_data['plant_type']}")
            if existing_data.get('growth_habit'):
                additional_context.append(f"Growth habit: {existing_data['growth_habit']}")
            if existing_data.get('native_regions'):
                additional_context.append(f"Native to: {existing_data['native_regions']}")
            if existing_data.get('bloom_time'):
                additional_context.append(f"Blooms: {existing_data['bloom_time']}")
            
            if additional_context:
                base_prompt += f"\n\nPlant details to reference:\n" + "\n".join(additional_context)
        
        return base_prompt
    
    @staticmethod
    def get_care_instructions_prompt(plant_name: str, care_type: str, existing_data: Optional[Dict] = None) -> str:
        """
        Generate a prompt for specific care instructions.
        
        Args:
            plant_name: Name of the plant
            care_type: Type of care (watering, lighting, fertilizing, etc.)
            existing_data: Existing plant data for context
            
        Returns:
            Formatted AI prompt string
        """
        care_prompts = {
            'general': f"""Write comprehensive care instructions for {plant_name}.

Cover all essential care aspects:
- Watering requirements and schedule
- Light and placement needs
- Temperature preferences
- Soil and fertilizing requirements
- Common care mistakes to avoid
- Signs of a healthy plant

Write practical, encouraging guidance for home gardeners.""",

            'watering': f"""Write detailed watering instructions for {plant_name}.

Include:
- How often to water
- How to check if the plant needs water
- Signs of overwatering and underwatering
- Seasonal adjustments
- Water quality considerations if relevant

Write in a helpful, practical tone for home gardeners. Be specific about timing and techniques.""",

            'lighting': f"""Write comprehensive lighting requirements for {plant_name}.

Cover:
- Ideal light conditions (bright indirect, full sun, etc.)
- How to position near windows
- Signs the plant is getting too much/too little light
- Artificial light options if needed
- Seasonal light changes

Make it practical for indoor and outdoor growing.""",

            'fertilizing': f"""Create a fertilizing guide for {plant_name}.

Include:
- Best type of fertilizer (liquid, granular, organic)
- Feeding schedule and frequency
- Seasonal fertilizing adjustments
- Signs of over/under-fertilization
- When to avoid fertilizing

Write for home gardeners who want healthy, thriving plants.""",

            'temperature': f"""Write temperature and climate guidance for {plant_name}.

Cover:
- Ideal temperature range
- Temperature tolerance limits
- Seasonal considerations
- Indoor vs outdoor temperature needs
- Protection from temperature extremes

Keep it practical for typical home environments.""",

            'humidity': f"""Create humidity guidance for {plant_name}.

Include:
- Ideal humidity levels
- How to increase humidity naturally
- Signs of humidity problems
- Seasonal humidity changes
- Simple tools for monitoring humidity

Focus on easy solutions for home growers.""",

            'special_notes': f"""Write special care tips and notes for {plant_name}.

Include:
- Common problems and solutions
- Seasonal care changes
- Propagation tips if applicable
- Companion planting suggestions
- Any unique characteristics or quirks
- Beginner-friendly success tips

Write encouraging, practical advice that helps ensure success."""
        }
        
        base_prompt = care_prompts.get(care_type, f"Write {care_type} care instructions for {plant_name}.")
        
        if existing_data:
            context_info = []
            if care_type == 'watering' and existing_data.get('water_requirements'):
                context_info.append(f"Water needs: {existing_data['water_requirements']}")
            elif care_type == 'lighting' and existing_data.get('light_requirements'):
                context_info.append(f"Light needs: {existing_data['light_requirements']}")
            elif care_type == 'temperature' and existing_data.get('hardiness_zones'):
                context_info.append(f"Hardy in zones: {existing_data['hardiness_zones']}")
            
            if existing_data.get('plant_type'):
                context_info.append(f"Plant type: {existing_data['plant_type']}")
            
            if context_info:
                base_prompt += f"\n\nPlant characteristics to consider:\n" + "\n".join(context_info)
        
        return base_prompt
    
    @staticmethod
    def get_troubleshooting_prompt(plant_name: str, problem_type: str) -> str:
        """
        Generate a prompt for plant troubleshooting content.
        
        Args:
            plant_name: Name of the plant
            problem_type: Type of problem (yellowing, drooping, pests, etc.)
            
        Returns:
            Formatted AI prompt string
        """
        return f"""Write troubleshooting guidance for {plant_name} experiencing {problem_type}.

Provide:
- Most likely causes of this problem
- Step-by-step diagnosis process
- Practical solutions for home gardeners
- Prevention tips for the future
- When to seek expert help

Write in a calm, helpful tone that reassures worried plant parents while providing actionable advice."""
    
    @staticmethod
    def get_seasonal_care_prompt(plant_name: str, season: str) -> str:
        """
        Generate a prompt for seasonal plant care.
        
        Args:
            plant_name: Name of the plant
            season: Season (spring, summer, fall, winter)
            
        Returns:
            Formatted AI prompt string
        """
        return f"""Write {season} care guidance for {plant_name}.

Include:
- Seasonal care adjustments needed
- What to watch for during {season}
- Maintenance tasks for this time of year
- Common {season} problems and solutions
- Preparation for the next season

Write practical, season-specific advice for home gardeners."""
    
    @staticmethod
    def get_plant_comparison_prompt(plant_names: List[str]) -> str:
        """
        Generate a prompt for comparing multiple plants.
        
        Args:
            plant_names: List of plant names to compare
            
        Returns:
            Formatted AI prompt string
        """
        plants_list = ", ".join(plant_names)
        
        return f"""Compare these plants for home gardeners: {plants_list}.

Create a helpful comparison covering:
- Care difficulty and requirements
- Growth habits and sizes
- Best growing conditions
- Unique features of each
- Which is best for beginners
- Complementary pairing suggestions

Write in an engaging tone that helps readers choose the right plant for their needs."""
    
    @staticmethod
    def get_beginner_guide_prompt(plant_name: str) -> str:
        """
        Generate a prompt for beginner-friendly plant guides.
        
        Args:
            plant_name: Name of the plant
            
        Returns:
            Formatted AI prompt string
        """
        return f"""Write a beginner's guide to growing {plant_name}.

Make it encouraging and comprehensive:
- Why this plant is good for beginners
- Essential supplies needed
- Step-by-step getting started guide
- Most important care tips
- Common beginner mistakes to avoid
- Signs of a healthy, happy plant

Write in an encouraging, non-intimidating tone that builds confidence in new plant parents."""


# Wagtail AI integration helper functions
def get_ai_prompt_for_block(block_type: str, field_name: str, context: Dict) -> str:
    """
    Get the appropriate AI prompt for a specific block field.
    
    Args:
        block_type: Type of block (plant_spotlight, care_instructions, etc.)
        field_name: Name of the field being populated
        context: Context data including plant name and existing data
        
    Returns:
        Formatted AI prompt string
    """
    plant_name = context.get('plant_name', 'this plant')
    existing_data = context.get('existing_data', {})
    
    if block_type == 'plant_spotlight':
        if field_name == 'description':
            return PlantAIPrompts.get_plant_description_prompt(plant_name, existing_data)
    
    elif block_type == 'care_instructions':
        if field_name in ['watering', 'lighting', 'fertilizing', 'temperature', 'humidity', 'special_notes']:
            return PlantAIPrompts.get_care_instructions_prompt(plant_name, field_name, existing_data)
    
    # Fallback generic prompt
    return f"Write helpful, accurate content about {field_name} for {plant_name}. Keep it practical and encouraging for home gardeners."


def get_available_ai_prompts() -> Dict[str, List[str]]:
    """
    Get a list of available AI prompts organized by category.
    
    Returns:
        Dictionary of prompt categories and their available options
    """
    return {
        'plant_spotlight': [
            'description',
        ],
        'care_instructions': [
            'watering',
            'lighting', 
            'fertilizing',
            'temperature',
            'humidity',
            'special_notes'
        ],
        'general': [
            'troubleshooting',
            'seasonal_care',
            'beginner_guide',
            'plant_comparison'
        ]
    }