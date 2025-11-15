# Services Layer

This directory contains the service layer for the Flutter mobile app. Services encapsulate business logic and API communication.

## ApiService

**Location**: `api_service.dart`

The `ApiService` is a centralized HTTP client for communicating with the Django backend API.

### Features

- **Dio-based HTTP client** with automatic request/response logging
- **Authentication** via Bearer token injection
- **Comprehensive error handling** with custom `ApiException`
- **Interceptors** for:
  - Automatic token injection
  - Debug logging (debug mode only)
  - Error transformation (401, 429, 5xx handling)
- **Multipart file upload** support for images
- **Environment configuration** via `.env` file
- **Type-safe** error messages with HTTP status codes

### Usage

#### Basic Setup

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:plant_community_mobile/services/api_service.dart';

// In your widget
class MyWidget extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final apiService = ref.read(apiServiceProvider);

    // Use apiService for HTTP requests
    return Container();
  }
}
```

#### GET Request

```dart
try {
  final response = await apiService.get(
    '/plant-identification/species/',
    queryParameters: {'page': 1, 'limit': 20},
  );

  final species = response.data as List;
  print('Found ${species.length} species');
} on ApiException catch (e) {
  print('Error: ${e.message}');
  print('Status code: ${e.statusCode}');
}
```

#### POST Request

```dart
try {
  final response = await apiService.post(
    '/plant-identification/identify/',
    data: {
      'image_url': 'https://example.com/image.jpg',
      'latitude': 37.7749,
      'longitude': -122.4194,
    },
  );

  final plant = PlantIdentification.fromJson(response.data);
  print('Identified: ${plant.name}');
} on ApiException catch (e) {
  if (e.statusCode == 429) {
    print('Rate limited! Try again later.');
  } else {
    print('Error: ${e.message}');
  }
}
```

#### File Upload

```dart
try {
  final response = await apiService.uploadFile(
    '/plant-identification/identify/',
    filePath: pickedFile.path,
    data: {'latitude': 37.7749, 'longitude': -122.4194},
    onSendProgress: (sent, total) {
      final progress = (sent / total) * 100;
      print('Upload progress: ${progress.toStringAsFixed(1)}%');
    },
  );

  final result = response.data;
  print('Upload successful!');
} on ApiException catch (e) {
  print('Upload failed: ${e.message}');
}
```

#### Authentication

```dart
// After user logs in with Firebase
final firebaseToken = await user.getIdToken();

// Exchange for Django JWT
final response = await apiService.post(
  '/auth/firebase-token-exchange/',
  data: {'firebase_token': firebaseToken},
);

final jwtToken = response.data['jwt_token'];

// Set token in ApiService
apiService.setAuthToken(jwtToken);

// All subsequent requests will include: Authorization: Bearer {token}
```

### Error Handling

The `ApiService` converts all `DioException` errors into user-friendly `ApiException` objects:

```dart
try {
  await apiService.get('/endpoint');
} on ApiException catch (e) {
  // User-friendly error message
  print(e.message);

  // HTTP status code (null for network errors)
  print(e.statusCode);

  // Handle specific errors
  switch (e.statusCode) {
    case 401:
      // Token expired - redirect to login
      break;
    case 429:
      // Rate limited - show retry message
      break;
    case 500:
      // Server error - show error page
      break;
    default:
      // Generic error handling
      break;
  }
}
```

### Error Types

| Error Type | Status Code | Description |
|------------|-------------|-------------|
| Connection Timeout | `null` | Network timeout (10s connect, 30s receive) |
| Network Error | `null` | No internet connection (SocketException) |
| Unauthorized | `401` | Invalid or expired authentication token |
| Rate Limited | `429` | Too many requests (check `Retry-After` header) |
| Server Error | `500`, `502`, `503`, `504` | Backend server issues |
| Custom Error | varies | Application-specific errors from backend |

### Configuration

The API base URL is configured via the `.env` file:

```env
# .env
API_BASE_URL=http://localhost:8000/api/v1
```

For production:

```env
# .env
API_BASE_URL=https://api.yourapp.com/api/v1
```

### Testing

Unit tests are located in `test/api_service_test.dart`.

Run tests:
```bash
flutter test test/api_service_test.dart
```

Test results:
- ✅ 15 unit tests passing
- ⏭️ 3 integration tests skipped (require backend)

### Best Practices

1. **Always use try-catch** when calling API methods
2. **Handle ApiException** to show user-friendly error messages
3. **Check status codes** for specific error handling
4. **Use loading indicators** during async operations
5. **Implement retry logic** for rate-limited requests (429)
6. **Validate user input** before sending to API
7. **Use query parameters** for filtering, not URL construction
8. **Upload files** using `uploadFile()`, not manual FormData

### Future Enhancements

- [ ] Automatic token refresh on 401
- [ ] Retry logic with exponential backoff for 5xx errors
- [ ] Request cancellation support
- [ ] Response caching for GET requests
- [ ] Network connectivity monitoring
- [ ] Request queuing for offline mode
- [ ] Interceptor for analytics tracking

## MockPlantService

**Location**: `mock_plant_service.dart`

A mock service for plant identification during development. Will be replaced by real backend integration using `ApiService`.

### Usage

```dart
final mockService = MockPlantService();
final plant = await mockService.identifyPlant('/path/to/image.jpg');
```

**Note**: This service will be deprecated once backend integration is complete (Task 3).
