# Type Definitions

This directory contains shared TypeScript type definitions for the Plant ID Community web application.

## Structure

Type definitions are organized by domain:

- `api.ts` - Generic API response types and HTTP wrappers
- `auth.ts` - Authentication and user types
- `forum.ts` - Forum entities (threads, posts, categories, attachments)
- `blog.ts` - Blog/Wagtail CMS types
- `diagnosis.ts` - Plant diagnosis and identification types
- `index.ts` - Central export point for all types

## Usage

Import types from the central index:

```typescript
import type { User, Thread, Post, ApiResponse } from '@/types';
```

Or import directly from specific modules:

```typescript
import type { User, Credentials } from '@/types/auth';
import type { Thread, Post } from '@/types/forum';
```

## Guidelines

1. **Use interfaces over types** for object shapes (better error messages)
2. **Export all types** for reusability
3. **Document complex types** with JSDoc comments
4. **Prefer `unknown` over `any`** for truly dynamic data
5. **Use discriminated unions** for polymorphic data (e.g., different StreamField blocks)

## Migration Notes

During Phase 3 of the TypeScript migration, these type definitions will be created based on:
- Existing PropTypes definitions (7 components have them)
- Backend API contracts (Django REST Framework serializers)
- Wagtail API v2 responses

See: GitHub Issue #134 - Phase 3 for implementation details
