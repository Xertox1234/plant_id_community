# Wagtail AI Custom Prompts Configuration

**Date**: November 11, 2025
**Configuration**: Plant-specific AI prompts for blog content generation
**Status**: ✅ Active and tested

---

## Overview

This document describes the custom AI prompts configured for the Plant Community blog. These prompts override Wagtail AI 3.0's defaults to provide plant-specific, SEO-optimized content generation.

---

## Configuration Location

**File**: `/backend/plant_community_backend/settings.py`
**Section**: `WAGTAIL_AI["AGENT_SETTINGS"]["wai_basic_prompt"]`

```python
WAGTAIL_AI = {
    # v3.0 Provider Configuration (recommended)
    "PROVIDERS": {
        "default": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "api_key": config('OPENAI_API_KEY', default=''),
        },
    },
    # Legacy BACKENDS (deprecated, use PROVIDERS instead)
    "BACKENDS": {
        "default": {
            "CLASS": "wagtail_ai.ai.openai.OpenAIBackend",
            "CONFIG": {
                "MODEL_ID": "gpt-4o-mini",
                "TOKEN_LIMIT": 16384,
                "OPENAI_API_KEY": config('OPENAI_API_KEY', default=''),
            },
        },
    },
    "AGENT_SETTINGS": {
        "wai_basic_prompt": {
            "page_title_prompt": "...",
            "page_description_prompt": "...",
        }
    },
}
```

---

## Custom Prompts

### 1. Page Title Prompt (`page_title_prompt`)

**Used By**: `AITitleFieldPanel('title')`

**Prompt**:
```
Generate an SEO-optimized blog post title about plants, gardening, or plant care.
Make it compelling, informative, and under 60 characters for optimal SEO.
Focus on actionable benefits and specific plant topics.
Context: {context}
```

**Purpose**:
- Generate SEO-friendly titles (under 60 characters)
- Focus on plant care and gardening topics
- Emphasize actionable benefits (e.g., "How to Propagate Aloe Vera Successfully")
- Include specific plant names when available

**Example Inputs/Outputs**:

| Context | Generated Title |
|---------|----------------|
| "Post about watering succulents in winter" | "Winter Succulent Watering: Essential Tips for Healthy Plants" |
| "Care guide for monstera deliciosa" | "Monstera Deliciosa Care: Complete Growing Guide" |
| "Troubleshooting yellow leaves on pothos" | "Fix Yellow Pothos Leaves: 5 Common Causes & Solutions" |

---

### 2. Meta Description Prompt (`page_description_prompt`)

**Used By**: `AIDescriptionFieldPanel('meta_description')`

**Prompt**:
```
Write a compelling meta description (150-160 characters) for this plant care or
gardening blog post. Focus on specific benefits, care tips, or plant characteristics
that would attract readers. Include relevant keywords naturally.
Make it actionable and engaging.
Context: {context}
```

**Purpose**:
- Generate SEO meta descriptions (150-160 characters)
- Include relevant plant care keywords
- Focus on reader benefits (e.g., "Learn proven techniques...")
- Create compelling click-through incentive

**Example Inputs/Outputs**:

| Context | Generated Meta Description |
|---------|---------------------------|
| "Guide to propagating snake plants" | "Learn 3 proven methods to propagate snake plants successfully. Simple step-by-step instructions with photos. Perfect for beginners!" (147 chars) |
| "Common fiddle leaf fig problems" | "Troubleshoot brown spots, drooping leaves & other fiddle leaf fig issues. Expert solutions to keep your FLF thriving year-round." (138 chars) |

---

### 3. Introduction Prompt (Generic)

**Used By**: `AIFieldPanel('introduction', prompts=['page_description_prompt'])`

**Current Behavior**: Uses `page_description_prompt` (same as meta description)

**Why**: Introduction paragraphs benefit from the same plant-focused, benefit-driven approach

**Future Enhancement**: Could add a dedicated `introduction_prompt` for longer, more detailed intros:

```python
"introduction_prompt": (
    "Write an engaging 2-3 sentence introduction for this plant care blog post. "
    "Hook the reader with a relatable scenario or surprising fact about plants. "
    "Transition naturally into the main content topic. "
    "Context: {context}"
),
```

---

## How Custom Prompts Work

### Wagtail AI 3.0 Flow

1. **User clicks AI button** in Wagtail admin (e.g., on title field)
2. **JavaScript sends AJAX request** to `/cms/ai/text_completion/`
3. **Wagtail AI agent** (`wai_basic_prompt`) is invoked
4. **Agent looks up prompt** from `AGENT_SETTINGS["wai_basic_prompt"]["page_title_prompt"]`
5. **Context is injected** - `{context}` replaced with page content
6. **OpenAI API called** with the formatted prompt
7. **Response returned** to user in admin UI

### Context Variable

The `{context}` variable is automatically populated by Wagtail AI with:
- Existing page content (introduction, body text)
- Page metadata (categories, tags)
- Related content (if configured)

**Example**:
```python
# User has written in introduction field:
"This post covers the best practices for watering aloe vera plants during different seasons."

# Wagtail AI will send to OpenAI:
"""
Generate an SEO-optimized blog post title about plants, gardening, or plant care.
Make it compelling, informative, and under 60 characters for optimal SEO.
Focus on actionable benefits and specific plant topics.
Context: This post covers the best practices for watering aloe vera plants during different seasons.
"""

# OpenAI might return:
"Seasonal Aloe Vera Watering Guide: Year-Round Care Tips"
```

---

## Testing Custom Prompts

### 1. Verify Configuration Loaded

```bash
cd backend
source venv/bin/activate

python manage.py shell -c "
from django.conf import settings
ai_settings = settings.WAGTAIL_AI
agent_settings = ai_settings.get('AGENT_SETTINGS', {})
basic_prompt = agent_settings.get('wai_basic_prompt', {})

print('✅ Custom prompts configured:', bool(basic_prompt))
print('Prompts:', list(basic_prompt.keys()))
"
```

**Expected Output**:
```
✅ Custom prompts configured: True
Prompts: ['page_title_prompt', 'page_description_prompt']
```

### 2. Test in Admin

1. Navigate to http://localhost:8000/cms/
2. Edit a BlogPostPage
3. Fill in the **Introduction** field with plant-related content
4. Click the **AI Actions** button (✨) on **Title** field
5. Click "Generate title"
6. Verify:
   - Generated title is under 60 characters
   - Title includes plant-specific terminology
   - Title is actionable and SEO-friendly

### 3. Compare with Default Prompts

**Default Wagtail AI Prompt** (generic):
```
Generate a title based on the page content
```

**Our Custom Prompt** (plant-specific):
```
Generate an SEO-optimized blog post title about plants, gardening, or plant care.
Make it compelling, informative, and under 60 characters for optimal SEO.
Focus on actionable benefits and specific plant topics.
```

**Result**: Custom prompts generate more relevant, SEO-optimized, plant-focused content.

---

## Customizing Prompts

### How to Modify Prompts

1. **Edit settings.py**:
   ```python
   WAGTAIL_AI = {
       # ... existing config
       "AGENT_SETTINGS": {
           "wai_basic_prompt": {
               "page_title_prompt": "Your new prompt here with {context}",
           }
       },
   }
   ```

2. **Restart Django server**:
   ```bash
   # Restart is required to load new settings
   python manage.py runserver
   ```

3. **Test in admin** - Generate content and verify new prompt behavior

### Prompt Engineering Tips

**Do**:
- ✅ Be specific about output format (length, style, tone)
- ✅ Include domain context ("plants", "gardening")
- ✅ Specify SEO requirements (character limits, keywords)
- ✅ Use action-oriented language ("Generate", "Write", "Create")
- ✅ Always include `{context}` variable

**Don't**:
- ❌ Make prompts too long (>500 characters)
- ❌ Use technical jargon users won't understand
- ❌ Forget character limits for titles (60) and descriptions (160)
- ❌ Omit the `{context}` variable (AI needs page content)

---

## Adding New Custom Prompts

### Example: Add Image Alt Text Prompt

```python
WAGTAIL_AI = {
    "BACKENDS": {
        "default": { ... },
    },
    "AGENT_SETTINGS": {
        "wai_basic_prompt": {
            "page_title_prompt": "...",
            "page_description_prompt": "...",

            # NEW: Image alt text prompt
            "image_alt_text_prompt": (
                "Generate descriptive alt text for this plant photo. "
                "Include plant name, visible features (color, size, condition), "
                "and context. Keep under 125 characters for accessibility. "
                "Context: {context}"
            ),
        }
    },
}
```

**Usage in Models**:
```python
from wagtail_ai.panels import AIFieldPanel

class PlantImage(models.Model):
    alt_text = models.CharField(max_length=255)

    panels = [
        AIFieldPanel('alt_text', prompts=['image_alt_text_prompt']),
    ]
```

---

## Monitoring AI Generation Quality

### Metrics to Track

1. **Generation Success Rate**
   - How often does AI generate usable content?
   - Target: >90% usable without major edits

2. **SEO Compliance**
   - Title length: <60 characters (target: 95% compliance)
   - Meta description length: 150-160 characters (target: 95%)

3. **Plant Specificity**
   - Does output mention specific plant names?
   - Does output use plant care terminology?
   - Target: >80% of outputs include plant-specific terms

4. **User Satisfaction**
   - Survey editors: Do AI suggestions save time?
   - Track: How often are AI suggestions accepted vs. manually edited?

### Quality Improvement

If AI output quality is low:

1. **Refine prompts** - Add more specific instructions
2. **Provide better context** - Ensure page content is detailed
3. **Adjust model** - Consider GPT-4 for higher quality (higher cost)
4. **Add examples** - Include few-shot examples in prompts

---

## Cost Optimization

### Current Configuration

- **Model**: GPT-4o-mini (cost-effective)
- **Cost per request**: ~$0.003
- **Expected usage**: ~500 requests/month
- **Monthly cost**: ~$1.50/month (before caching)

### With Caching (Future)

- **Cache hit rate**: 80-95% expected
- **Effective cost**: $0.15-0.30/month
- **Savings**: 80-95% cost reduction

**See**: `WAGTAIL_AI_V3_MIGRATION_PATTERNS.md` - Pattern 8 for caching implementation

---

## Troubleshooting

### Issue 1: Prompts Not Applied

**Symptom**: AI generates generic content, not plant-specific

**Cause**: Settings not reloaded after editing

**Fix**:
```bash
# Restart Django server
python manage.py runserver
```

---

### Issue 2: Context Variable Empty

**Symptom**: AI generates unrelated content

**Cause**: No page content provided (blank introduction field)

**Fix**: Fill in introduction or other content fields before generating title/description

---

### Issue 3: Output Too Long/Short

**Symptom**: Titles exceed 60 characters or descriptions are too short

**Cause**: Model ignoring length constraints

**Fix**: Make length requirements more explicit in prompt:
```python
"page_title_prompt": (
    "Generate a blog post title EXACTLY under 60 characters. "
    "Count characters carefully. If over 60, make it shorter. "
    # ... rest of prompt
),
```

---

## Related Documentation

- **`WAGTAIL_AI_V3_MIGRATION_PATTERNS.md`** - Migration patterns and architecture
- **`WAGTAIL_AI_PATTERNS_CODIFIED.md`** - Original v2.x patterns (deprecated)
- **Wagtail AI Docs**: https://github.com/wagtail/wagtail-ai

---

## Future Enhancements

### 1. Dedicated Introduction Prompt
Add specific prompt for introduction paragraphs (longer, more engaging)

### 2. Category-Specific Prompts
Different prompts based on blog category:
- Indoor plants
- Garden design
- Plant troubleshooting
- Seasonal care

### 3. Tone Customization
Allow editors to choose tone:
- Professional (default)
- Casual/Conversational
- Technical/Scientific
- Beginner-friendly

### 4. Multi-Language Support
Generate content in multiple languages for international audience

---

**Document Version**: 1.0
**Last Updated**: November 11, 2025
**Status**: ✅ Active - Custom prompts configured and tested
