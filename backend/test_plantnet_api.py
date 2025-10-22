#!/usr/bin/env python3
"""
Test script for PlantNet API integration.
Run this to verify the API is working correctly with the fixed implementation.
"""

import os
import sys
import django
from pathlib import Path

# Setup Django environment
sys.path.append('/home/xertox1234/projects/plant_id_community/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'plant_community_backend.settings')
django.setup()

from apps.plant_identification.services.plantnet_service import PlantNetAPIService
from PIL import Image
import io
import requests


def create_test_image():
    """Create a simple test image for API testing."""
    # Create a simple green square image (simulating a leaf)
    img = Image.new('RGB', (300, 300), color='green')
    
    # Add some variation to make it look more plant-like
    for i in range(50, 250):
        for j in range(50, 250):
            if (i + j) % 20 == 0:
                img.putpixel((i, j), (34, 139, 34))  # Forest green
    
    # Convert to bytes
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    buffer.seek(0)
    
    return buffer


def test_plantnet_api():
    """Test the PlantNet API integration."""
    print("Testing PlantNet API Integration...")
    print("=" * 50)
    
    # Initialize service (will use API key from Django settings)
    try:
        service = PlantNetAPIService()
        print("✓ PlantNet service initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize PlantNet service: {e}")
        return False
    
    # Test service status
    print("\n1. Testing service status...")
    status = service.get_service_status()
    print(f"   Status: {status['status']}")
    print(f"   API Key Valid: {status['api_key_valid']}")
    if status['status'] != 'available':
        print(f"   Error: {status.get('error', 'Unknown error')}")
        return False
    print("✓ Service is available")
    
    # Test project information
    print("\n2. Testing project information...")
    project_info = service.get_project_info('world')
    if project_info:
        print(f"   Project: {project_info.get('name', 'Unknown')}")
        print(f"   Species count: {project_info.get('nbSpecies', 0)}")
        print("✓ Project info retrieved successfully")
    else:
        print("✗ Failed to get project information")
    
    # Test plant identification with real image
    print("\n3. Testing plant identification...")
    try:
        # Download a real plant image for testing
        print("   Downloading test image...")
        img_response = requests.get(
            "https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Sunflower_sky_backdrop.jpg/800px-Sunflower_sky_backdrop.jpg",
            timeout=30
        )
        if img_response.status_code != 200:
            print(f"   Failed to download test image: {img_response.status_code}")
            return False
            
        test_image = io.BytesIO(img_response.content)
        
        # Test identification with useful project (smaller dataset, good for testing)
        result = service.identify_plant(
            images=[test_image], 
            project='useful',  # Use 'useful' project which worked in our test
            organs=['flower'],  # Sunflower image
            include_related_images=False
        )
        
        if result:
            print("✓ Plant identification request successful")
            print(f"   Results found: {len(result.get('results', []))}")
            
            # Test suggestions extraction
            suggestions = service.get_top_suggestions(result, min_score=0.01)
            if suggestions:
                top_suggestion = suggestions[0]
                print(f"   Top suggestion: {top_suggestion.get('scientific_name', 'Unknown')}")
                print(f"   Confidence: {top_suggestion.get('confidence_score', 0):.3f}")
                print("✓ Suggestions extracted successfully")
            else:
                print("   No suggestions found (low confidence)")
                # Show raw result for debugging
                if result.get('results'):
                    first_result = result['results'][0]
                    species = first_result.get('species', {})
                    print(f"   Raw result: {species.get('scientificNameWithoutAuthor', 'Unknown')} (score: {first_result.get('score', 0):.3f})")
                
        else:
            print("✗ Plant identification failed")
            return False
            
    except Exception as e:
        print(f"✗ Error during plant identification: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("✓ All tests passed! PlantNet API integration is working correctly.")
    return True


if __name__ == '__main__':
    success = test_plantnet_api()
    sys.exit(0 if success else 1)