# PlantNet API v2 Integration - Fixed Implementation

## Summary

This document outlines the fixes applied to the PlantNet API v2 integration that was previously getting 400 Bad Request errors.

## Issues Found and Fixed

### 1. **Incorrect Parameter Format**
**Problem**: The original implementation used indexed organ parameters (`organs[0]`, `organs[1]`) and passed parameters as a dictionary.

**Solution**: Use list-style parameters where each organ is added separately using the same field name:
```python
# WRONG - Original implementation
data = {
    'organs': organs,  # Array
    'organs[0]': 'flower',
    'organs[1]': 'leaf'
}

# CORRECT - Fixed implementation  
data = []
for organ in organs:
    data.append(('organs', organ))  # Multiple entries with same name
```

### 2. **Invalid Project IDs**
**Problem**: Used incorrect project identifiers like `'all'` or outdated project keys.

**Solution**: Updated to use valid project IDs from the PlantNet API `/v2/projects` endpoint:
```python
PROJECTS = {
    'world': 'k-world-flora',        # World flora - 74043 species
    'useful': 'useful',              # Useful plants - 5457 species
    'europe': 'k-middle-europe',     # Middle Europe - 5111 species
    # ... other valid project IDs
}
```

### 3. **Response Structure Changes**
**Problem**: The response parsing assumed `commonNames` was an array of objects with `value` keys, but it's actually an array of strings.

**Solution**: Updated parsing to handle both string arrays and object arrays:
```python
# Handle common names - they can be either strings or objects
common_names = []
for name in species.get('commonNames', []):
    if isinstance(name, str):
        common_names.append(name)
    elif isinstance(name, dict):
        common_names.append(name.get('value', ''))
```

### 4. **Test Image Quality**
**Problem**: Synthetic test images weren't realistic enough for the AI to identify.

**Solution**: Use real plant images for testing to ensure the API can actually identify species.

## Working Implementation

### Core API Request Format
```python
def identify_plant(self, images, project='useful', organs=None, include_related_images=False):
    project_key = self.PROJECTS.get(project, self.PROJECTS['world'])
    url = f"{self.BASE_URL}/identify/{project_key}"
    params = {'api-key': self.api_key}
    
    # Prepare files
    files = []
    for i, image in enumerate(images):
        image_bytes = self._prepare_image(image)
        files.append(('images', (f"image_{i}.jpg", image_bytes, 'image/jpeg')))
    
    # Prepare form data as list of tuples
    data = []
    for organ in organs:
        data.append(('organs', organ))
    
    if include_related_images:
        data.append(('include-related-images', 'true'))
    
    # Make request
    response = self.session.post(url, params=params, files=files, data=data, timeout=60)
    response.raise_for_status()
    return response.json()
```

### Response Structure (PlantNet API v2 2025-01-17)
```json
{
  "query": {
    "project": "useful",
    "images": ["hash"],
    "organs": ["flower"],
    "includeRelatedImages": false
  },
  "results": [
    {
      "score": 0.1802,
      "species": {
        "scientificNameWithoutAuthor": "Helianthus annuus",
        "scientificName": "Helianthus annuus L.",
        "family": {
          "scientificNameWithoutAuthor": "Asteraceae"
        },
        "genus": {
          "scientificNameWithoutAuthor": "Helianthus"  
        },
        "commonNames": ["Sunflower", "Common Sunflower"]
      },
      "gbif": {"id": "9206251"},
      "powo": {"id": "119003-2"},
      "iucn": {"id": "19073408", "category": "LC"}
    }
  ],
  "version": "2025-01-17 (7.3)",
  "remainingIdentificationRequests": 488
}
```

## Available Projects

The PlantNet API offers these main projects (as of January 2025):

| Project ID | Name | Species Count | Description |
|------------|------|---------------|-------------|
| `k-world-flora` | World flora | 74,043 | Plants of the world flora |
| `useful` | Useful plants | 5,457 | Cultivated and ornamental plants |
| `weeds` | Weeds | 1,429 | Weeds in agricultural fields |
| `k-middle-europe` | Middle Europe | 5,111 | Plants of Middle Europe |
| `k-northeastern-u-s-a` | Northeastern U.S.A. | 3,931 | Plants of Northeastern U.S.A. |

## Testing

### Test Results
```bash
Testing PlantNet API Integration...
==================================================
✓ PlantNet service initialized successfully
✓ Service is available  
✓ Project info retrieved successfully
✓ Plant identification request successful
   Results found: 1
   Top suggestion: Helianthus annuus
   Confidence: 0.180
✓ Suggestions extracted successfully
==================================================
✓ All tests passed! PlantNet API integration is working correctly.
```

### Example Usage
```python
from apps.plant_identification.services.plantnet_service import PlantNetAPIService

# Initialize service
service = PlantNetAPIService()

# Identify plant from image file
with open('sunflower.jpg', 'rb') as f:
    result = service.identify_plant(
        images=[f],
        project='useful',
        organs=['flower']
    )

# Extract suggestions
suggestions = service.get_top_suggestions(result, min_score=0.1)
if suggestions:
    top_match = suggestions[0]
    print(f"Species: {top_match['scientific_name']}")
    print(f"Common names: {', '.join(top_match['common_names'])}")
    print(f"Confidence: {top_match['confidence_score']:.3f}")
```

## Key Points for Success

1. **Use valid project IDs** - Check `/v2/projects` endpoint for current list
2. **Real images required** - Synthetic images rarely work with the AI
3. **Correct multipart format** - Use list of tuples for repeated field names
4. **Handle response structure** - CommonNames are strings, not objects
5. **Test with 'useful' project** - Smaller dataset, good for initial testing

## File Changes Made

- `/apps/plant_identification/services/plantnet_service.py` - Fixed request format and response parsing
- `test_plantnet_api.py` - Updated to use real plant images for testing
- Added comprehensive test scripts for debugging and validation

The PlantNet API v2 integration is now fully functional and correctly identifies plant species from uploaded images.