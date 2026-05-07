# Firebase Cloud Functions Patterns

**Stack**: Node.js / TypeScript, Firebase SDK, default region `us-central1`

---

## Idempotency — Required for All Functions

Firebase retries functions on failure. Every function must be safe to execute multiple times with the same event.

```typescript
// Firestore-triggered — check processed flag before acting
export const processPlantIdentification = functions.firestore
  .document('identifications/{docId}')
  .onCreate(async (snap, context) => {
    const data = snap.data();

    // Idempotency guard
    if (data.processed === true) return null;

    // ... do work ...

    await snap.ref.update({ processed: true });
    return null;
  });
```

HTTP functions must return 200 for idempotent re-processing:

```typescript
if (alreadyProcessed) {
  return res.status(200).json({ message: 'Already processed' });
}
```

---

## Cold Start Optimisation

SDK initialisation MUST be at module scope, never inside handler:

```typescript
// ✅ Module scope — initialised once per instance
import * as admin from 'firebase-admin';
admin.initializeApp();
const db = admin.firestore();

// ❌ Inside handler — re-initialised on every invocation
export const myFunction = functions.https.onCall(async (data, context) => {
  admin.initializeApp(); // ❌
  const db = admin.firestore(); // ❌
});
```

---

## Error Handling — Prevent Infinite Retries

Unhandled promise rejections cause infinite retries. Distinguish retriable from permanent errors:

```typescript
export const sendNotification = functions.pubsub
  .topic('notifications')
  .onPublish(async (message) => {
    try {
      await sendPush(message.json);
    } catch (err) {
      if (err instanceof PermanentError) {
        // Log and return — do NOT throw (stops retries)
        console.error('Permanent error, not retrying:', err);
        return;
      }
      // Retriable error — throw to trigger retry
      throw err;
    }
  });
```

---

## Security — Callable Functions

Always check `context.auth` before processing in callable functions:

```typescript
export const identifyPlant = functions.https.onCall(async (data, context) => {
  if (!context.auth) {
    throw new functions.https.HttpsError('unauthenticated', 'Must be signed in');
  }
  // ...
});
```

Firestore writes from functions bypass security rules — enforce permission logic manually.

---

## Cost Control

- Use targeted `doc()` reads, not `collection().get()` inside functions.
- Functions that may fan-out to many users must use batching or rate limiting.
- Avoid Firestore reads inside loops — use `getAll()` for batch fetches.

---

## Region Configuration

Specify region explicitly for non-default deployments:

```typescript
export const myFunction = functions.region('europe-west1').https.onCall(...);
```
