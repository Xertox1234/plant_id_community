# Firebase Authentication Patterns (Flutter + Django Backend)

**Stack**: Firebase Auth 5.3.3, `flutter_secure_storage`, Django JWT token exchange at `/api/v1/auth/firebase-token-exchange/`

---

## Token Storage — Secure Storage Only

JWT tokens MUST be stored in `flutter_secure_storage`. NEVER use `SharedPreferences` (plaintext, accessible without authentication on non-rooted devices).

```dart
final storage = const FlutterSecureStorage();

// Store after successful token exchange
await storage.write(key: 'access_token', value: tokens.accessToken);
await storage.write(key: 'refresh_token', value: tokens.refreshToken);

// Retrieve for API calls
final accessToken = await storage.read(key: 'access_token');
```

Firebase ID tokens must NOT be stored persistently — always retrieved fresh via `user.getIdToken()`.

---

## Memory Leak — Auth State Subscription

```dart
@riverpod
class AuthService extends _$AuthService {
  StreamSubscription<User?>? _authStateSubscription;

  @override
  AuthState build() {
    _authStateSubscription = FirebaseAuth.instance
        .authStateChanges()
        .listen((user) async {
      if (user != null) {
        await _exchangeFirebaseTokenForJWT(user);
      } else {
        await _clearJWT();
      }
    });

    // CRITICAL — missing this causes persistent Firebase listener after widget disposal
    ref.onDispose(() {
      _authStateSubscription?.cancel();
    });

    return AuthState(firebaseUser: FirebaseAuth.instance.currentUser);
  }
}
```

---

## Backend Token Exchange Flow

1. User signs in via Firebase
2. Get Firebase ID token: `await user.getIdToken()`
3. POST to `/api/v1/auth/firebase-token-exchange/` with `{ "firebase_token": idToken }`
4. Backend validates token with firebase-admin, creates/retrieves Django user
5. Returns Django JWT access + refresh tokens
6. Store in `flutter_secure_storage`

---

## GDPR — Email Redaction in Backend Logs

The backend must never log full email addresses. Use the `redact_email()` helper:
- `william@example.com` → `wi***@example.com`

```python
def redact_email(email: str) -> str:
    local, _, domain = email.partition('@')
    return f"{local[:2]}***@{domain}"
```

---

## Backend — Username Collision Handling

When two Firebase users have the same username base (e.g. `john@gmail.com` and `john@yahoo.com`), a UUID suffix resolves the collision:

```python
def get_or_create_user_from_firebase(firebase_uid, firebase_email, display_name):
    base_username = display_name or firebase_email.split('@')[0]
    username = base_username
    if User.objects.filter(username=username).exclude(firebase_uid=firebase_uid).exists():
        username = f"{base_username}_{uuid.uuid4().hex[:8]}"
```

---

## Firestore Listener Scope

Scope Firestore listeners to minimum required documents — never full collection snapshots:

```dart
// ✅ Targeted listener
_firestore.collection('plants').where('userId', isEqualTo: userId).snapshots()

// ❌ Full collection — expensive and grows unbounded
_firestore.collection('plants').snapshots()
```

---

## Firebase Storage Upload Validation

Validate file type and size client-side before uploading:

```dart
Future<void> uploadPlantImage(File file) async {
  final fileSize = await file.length();
  if (fileSize > 10 * 1024 * 1024) throw 'File too large (max 10MB)';

  final ext = file.path.split('.').last.toLowerCase();
  if (!['jpg', 'jpeg', 'png', 'webp'].contains(ext)) throw 'Invalid file type';

  await _storage.ref('plants/$userId/${uuid.v4()}.$ext').putFile(file);
}
```
