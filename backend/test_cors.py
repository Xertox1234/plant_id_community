#!/usr/bin/env python3
import urllib.request

# Test CORS from localhost:5174
req = urllib.request.Request(
    'http://localhost:8000/api/v2/blog-posts/?limit=1',
    headers={'Origin': 'http://localhost:5174'}
)

try:
    response = urllib.request.urlopen(req)
    print(f"Status: {response.status}")
    print("\nResponse Headers:")
    for header, value in response.headers.items():
        if 'access-control' in header.lower() or 'origin' in header.lower() or 'vary' in header.lower():
            print(f"  {header}: {value}")

    # Check for CORS headers
    cors_headers = [h for h in response.headers if 'access-control' in h.lower()]
    if not cors_headers:
        print("\n❌ NO CORS HEADERS FOUND!")
    else:
        print(f"\n✅ Found {len(cors_headers)} CORS headers")
except Exception as e:
    print(f"Error: {e}")
