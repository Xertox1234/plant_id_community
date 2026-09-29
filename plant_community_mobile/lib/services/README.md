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
- **Environment configuration** via `--dart-define`
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
    '/plant-identification/plants/',
    queryParameters: {'page': 1, 'limit': 20},
  );

  final plants = response.data as List;
  print('Found ${plants.length} plants');
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

final jwtToken = response.data['access_token'];

// Set token in ApiService
apiService.setAuthToken(jwtToken);

// All subsequent requests will include: Authorization: Bearer {token}
```

#### Access-token refresh on 401 (todo 462)

The Django access token is short-lived, so a user who keeps the app open
past its lifetime gets a 401 on their next request. `ApiService` recovers
from that silently:

1. On a 401 it calls the refresher `AuthService` registered with
   `setAccessTokenRefresher`. That re-exchanges the current Firebase ID token
   at `/auth/firebase-token-exchange/`, as launch does. `getIdToken()` renews
   the Firebase token itself when it has expired. The stored Django refresh
   token is not used.
2. Every 401 that arrives while a refresh is running waits on that same
   refresh, so concurrent 401s cost one exchange. A 401 for a request sent
   with a token that has since been replaced retries with the new token and
   does not refresh again.
3. The original request is re-sent once with the new token and its body
   intact. A multipart `FormData` is cloned first, because Dio will not send
   the same `FormData` twice.
4. Only a failed refresh, or a second 401 on the re-sent request, signs the
   user out, with the same "Your session expired. Please sign in again."
   message as before. A refresh overtaken by a sign-out or user switch does
   not report an expired session.

Request-extra flags opt out: `ApiService.skipSessionExpiryKey` ignores the
401 entirely (sign-out's own FCM clear), and `ApiService.skipAuthRefreshKey`
skips the refresh and goes straight to sign-out (the token exchange itself).

**Production access lifetime: 15 minutes.** `SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]`
reads `JWT_ACCESS_TOKEN_LIFETIME` with a default of 15
(`backend/plant_community_backend/settings.py`), and the production service's
variable set in `.railway/railway.ts` has no `JWT_ACCESS_TOKEN_LIFETIME`, so
production runs the default (recorded 2026-09-29). Expect a refresh roughly
every 15 minutes of use.

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
      // Only after a failed token refresh (see above) - AuthService has
      // already cleared local tokens and signed the user out
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
| ------------ | ------------- | ------------- |
| Connection Timeout | `null` | Network timeout (10s connect, 30s receive) |
| Network Error | `null` | No internet connection (SocketException) |
| Unauthorized | `401` | Invalid or expired authentication token |
| Rate Limited | `429` | Too many requests (check `Retry-After` header) |
| Server Error | `500`, `502`, `503`, `504` | Backend server issues |
| Custom Error | varies | Application-specific errors from backend |

### Configuration

The API base URL is configured with `--dart-define`:

```bash
flutter run --dart-define=API_BASE_URL=http://localhost:8000/api/v1
```

For production:

```bash
flutter build apk --release --dart-define=API_BASE_URL=https://api.yourapp.com/api/v1
```

### Testing

Unit tests are located in `test/api_service_test.dart`.

Run tests:

```bash
flutter test test/api_service_test.dart
```

Expected test behavior:

- ✅ API service unit tests pass in a Flutter-capable environment
- ⏭️ 3 integration tests skipped (require backend)

### Best Practices

1. **Always use try-catch** when calling API methods
2. **Handle ApiException** to show user-friendly error messages
3. **Check status codes** for specific error handling
4. **Use loading indicators** during async operations
5. **Rely on built-in bounded retries** for safe `429` and retryable `5xx` requests
6. **Validate user input** before sending to API
7. **Use query parameters** for filtering, not URL construction
8. **Upload files** using `uploadFile()`, not manual FormData

### Future Enhancements

- [ ] Mobile bearer-token refresh endpoint support for recoverable 401 retries
- [x] Retry logic with exponential backoff for 429 and retryable 5xx errors
- [ ] Request cancellation support
- [ ] Response caching for GET requests
- [ ] Network connectivity monitoring
- [ ] Request queuing for offline mode
- [ ] Interceptor for analytics tracking

## PlantIdentificationService

**Location**: `plant_identification_service.dart`

Coordinates plant image upload, backend identification, result parsing, and
cleanup. Tests use local mock `ApiService` and `FirebaseStorageService`
implementations rather than a separate `mock_plant_service.dart` file.
