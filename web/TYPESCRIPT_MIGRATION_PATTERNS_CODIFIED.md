# TypeScript Migration Patterns - Codified Implementation Guide

**Document Version**: 1.0.0
**Last Updated**: November 9, 2025
**Migration Status**: 100% Complete (Issue #134)
**Code Review Grade**: A (95/100)
**Test Stability**: 492 passing (zero regressions)

## Executive Summary

This document codifies the implementation patterns from a successful TypeScript migration of a React 19 web frontend. The migration converted 50+ files (~10,000 lines) from JavaScript to TypeScript with **zero regressions** in functionality or test coverage. These patterns represent production-ready approaches to incremental TypeScript adoption that can be applied to any React codebase.

### Key Achievements

- **100% Conversion**: All source files migrated from JavaScript to TypeScript
- **Zero Compilation Errors**: `npx tsc --noEmit` passes cleanly
- **Zero Test Regressions**: 492 tests passing (stable throughout migration)
- **Incremental Approach**: 7-phase bottom-up strategy enabling continuous development
- **Type Safety**: Comprehensive type definitions covering all domain entities
- **PropTypes Removed**: 100% replacement with TypeScript interfaces

### Migration Timeline

- **Duration**: Completed in phases over Issue #134
- **Files Converted**: 50+ files
- **Lines Migrated**: ~10,000 lines
- **Approach**: Bottom-up (utils → services → contexts → components → pages)
- **Downtime**: Zero (each phase independently deployable)

---

## Table of Contents

1. [Migration Strategy Pattern](#pattern-1-migration-strategy-bottom-up-approach)
2. [TypeScript Configuration Pattern](#pattern-2-typescript-configuration-lenient-first)
3. [Type Definition Organization](#pattern-3-type-definition-organization)
4. [React Router Import Fix](#pattern-4-react-router-import-fix-v7)
5. [Memory Leak Prevention Pattern](#pattern-5-memory-leak-prevention-useref-for-timers)
6. [Logger Type Safety Pattern](#pattern-6-logger-type-safety)
7. [Readonly Type Compatibility](#pattern-7-readonly-type-compatibility)
8. [PropTypes Migration Pattern](#pattern-8-proptypes-removal-timing)
9. [Test Stability During Migration](#pattern-9-test-stability-during-migration)
10. [Verification Checklist](#verification-checklist)

---

## Pattern 1: Migration Strategy (Bottom-Up Approach)

**Grade Impact**: Critical foundation for successful migration
**Why This Matters**: Dependencies flow upward, so converting foundations first eliminates cascading type errors

### The Pattern

Migrate code in dependency order from lowest-level utilities to highest-level pages:

```
Phase Order:
1. Foundation Setup (tsconfig, types, configs)
2. Utilities & Constants (pure functions)
3. Type Definitions (domain entities)
4. Services (API layer)
5. Contexts & Hooks (state management)
6. UI Components (reusable)
7. Pages (route components)
8. Error Resolution & Cleanup
```

### Why Bottom-Up Works

**Dependency Flow**:
```
Pages
  ↓ depends on
Components
  ↓ depends on
Contexts/Hooks
  ↓ depends on
Services
  ↓ depends on
Utils/Types
```

**Migration Flow** (reverse order):
```
Utils/Types (no dependencies)
  ↓ enables
Services (depends on utils)
  ↓ enables
Contexts (depends on services)
  ↓ enables
Components (depends on contexts)
  ↓ enables
Pages (depends on components)
```

### Implementation

**Phase 1: Foundation Setup** (No code changes)
```bash
# Install TypeScript dependencies
npm install --save-dev typescript @types/react @types/react-dom

# Create tsconfig.json with lenient settings
cat > tsconfig.json << 'EOF'
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "jsx": "react-jsx",
    "module": "ESNext",
    "moduleResolution": "bundler",

    // LENIENT - Allow incremental migration
    "strict": false,
    "allowJs": true,      // Allow JS files during migration
    "checkJs": false,     // Don't type-check JS files

    // Type safety
    "isolatedModules": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "noEmit": true
  }
}
EOF

# Convert build configs to TypeScript
mv vite.config.js vite.config.ts
mv vitest.config.js vitest.config.ts
mv playwright.config.js playwright.config.ts

# Verify build still works
npm run build
npm run test
```

**Phase 2: Utilities & Constants** (11 files)
```bash
# Pure functions with no React dependencies
# Convert in any order (no interdependencies)

# Example: validation.js → validation.ts
# Before:
export function validateEmail(email) {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

# After:
export function validateEmail(email: unknown): boolean {
  if (typeof email !== 'string') return false;
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

# Files converted:
# - utils/validation.ts
# - utils/sanitize.ts
# - utils/logger.ts
# - utils/constants.ts
# - utils/httpClient.ts
# - utils/csrf.ts
# - utils/domSanitizer.ts
# - utils/formatDate.ts
# - utils/imageCompression.ts
# - utils/plantUtils.ts
# - tests/forumUtils.ts
```

**Phase 3: Type Definitions** (Central type system)
```typescript
// src/types/auth.ts
export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_moderator: boolean;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface AuthResponse {
  user: User;
  access: string;
  refresh: string;
}

// src/types/forum.ts
export interface Thread {
  id: number;
  title: string;
  content: string;
  author: User;
  category: Category;
  created_at: string;
  updated_at: string;
  is_pinned: boolean;
  is_locked: boolean;
  post_count: number;
}

// src/types/index.ts (barrel export)
export type { User, LoginCredentials, AuthResponse } from './auth';
export type { Thread, Post, Category } from './forum';
export type { BlogPost, StreamFieldBlock } from './blog';
```

**Phase 4: Services** (API layer)
```typescript
// Before (JavaScript):
export async function loginUser(credentials) {
  const response = await httpClient.post('/api/v1/auth/login/', credentials);
  return response.data;
}

// After (TypeScript):
import type { LoginCredentials, AuthResponse } from '@/types';

export async function loginUser(credentials: LoginCredentials): Promise<AuthResponse> {
  const response = await httpClient.post<AuthResponse>(
    '/api/v1/auth/login/',
    credentials
  );
  return response.data;
}

// Files converted:
// - services/authService.ts
// - services/blogService.ts
// - services/forumService.ts
// - services/plantIdService.ts
// - services/diagnosisService.ts
```

**Phase 5: Contexts & Hooks**
```typescript
// Before (JavaScript with PropTypes):
import PropTypes from 'prop-types';

export const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // ... implementation
}

AuthProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

// After (TypeScript):
import type { User } from '@/types';
import { ReactNode } from 'react';

interface AuthContextValue {
  user: User | null;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  // ... implementation
}
```

**Phase 6: UI Components** (29 files)
```typescript
// Before (JavaScript):
function BlogCard({ post, showImage = true }) {
  return (
    <div>
      {showImage && <img src={post.featured_image} alt={post.title} />}
      <h2>{post.title}</h2>
    </div>
  );
}

BlogCard.propTypes = {
  post: PropTypes.shape({
    title: PropTypes.string.isRequired,
    featured_image: PropTypes.string,
  }).isRequired,
  showImage: PropTypes.bool,
};

// After (TypeScript):
import type { BlogPost } from '@/types';

interface BlogCardProps {
  post: BlogPost;
  showImage?: boolean;
}

function BlogCard({ post, showImage = true }: BlogCardProps) {
  return (
    <div>
      {showImage && <img src={post.featured_image} alt={post.title} />}
      <h2>{post.title}</h2>
    </div>
  );
}
```

**Phase 7: Pages** (18 files)
```typescript
// Before (JavaScript):
export default function ThreadDetailPage() {
  const { threadId } = useParams();
  const [thread, setThread] = useState(null);
  // ...
}

// After (TypeScript):
import type { Thread } from '@/types';

export default function ThreadDetailPage() {
  const { threadId } = useParams<{ threadId: string }>();
  const [thread, setThread] = useState<Thread | null>(null);
  // ...
}
```

### Migration Progress Tracking

Create a checklist to track progress:

```markdown
## Phase 2: Utilities (11 files)
- [x] utils/validation.ts
- [x] utils/sanitize.ts
- [x] utils/logger.ts
- [x] utils/constants.ts
- [x] utils/httpClient.ts
- [x] utils/csrf.ts
- [x] utils/domSanitizer.ts
- [x] utils/formatDate.ts
- [x] utils/imageCompression.ts
- [x] utils/plantUtils.ts
- [x] tests/forumUtils.ts

## Phase 3: Type Definitions (6 files)
- [x] types/api.ts
- [x] types/auth.ts
- [x] types/forum.ts
- [x] types/blog.ts
- [x] types/diagnosis.ts
- [x] types/plantId.ts

## Phase 4: Services (5 files)
- [x] services/authService.ts
- [x] services/blogService.ts
- [x] services/forumService.ts
- [x] services/plantIdService.ts
- [x] services/diagnosisService.ts
```

### Benefits

1. **No Cascading Errors**: Lower-level code is typed before higher-level code uses it
2. **Independent Testing**: Each phase can be tested and deployed independently
3. **Continuous Development**: Feature work can continue during migration
4. **Clear Progress**: Phase completion provides visible milestones
5. **Easier Debugging**: Errors are isolated to the current phase

### Anti-Patterns (What NOT to Do)

❌ **Top-Down Migration**:
```typescript
// BAD: Convert pages first
// Problem: Pages depend on untyped services/utils
// Result: Type errors cascade, forcing `any` types

// pages/BlogPage.tsx
const posts = await fetchBlogPosts(); // service not typed yet
// Type error: Cannot infer type of 'posts'
const posts: any = await fetchBlogPosts(); // Forced to use 'any'!
```

❌ **Random Order Migration**:
```bash
# BAD: Convert files randomly
✓ pages/HomePage.tsx
✓ utils/validation.ts
✓ components/BlogCard.tsx
✗ services/blogService.js (not converted yet)
# Problem: BlogCard depends on untyped blogService
# Result: Incomplete type safety, technical debt
```

❌ **Big Bang Migration**:
```bash
# BAD: Convert all files at once
# Problem: Too many errors to debug
# Result: Overwhelming, high risk of bugs
```

### Testing After Each Phase

**Run After Every 5-10 File Conversions**:
```bash
# 1. TypeScript compilation check
npx tsc --noEmit

# 2. Run test suite
npm run test

# 3. Build verification
npm run build

# 4. Commit if all pass
git add .
git commit -m "feat: migrate utilities to TypeScript (Phase 2)"
```

---

## Pattern 2: TypeScript Configuration (Lenient First)

**Grade Impact**: Enables smooth incremental migration
**Why This Matters**: Strict mode during migration creates overwhelming errors

### The Pattern

Start with **lenient TypeScript settings** to allow incremental migration, then tighten incrementally after completion.

### Implementation

**Initial tsconfig.json** (During Migration):
```json
{
  "compilerOptions": {
    /* Language and Environment */
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "jsx": "react-jsx",

    /* Modules */
    "module": "ESNext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,

    /* Type Checking - LENIENT (Migration in progress) */
    "strict": false,              // ✅ Disable during migration
    "noImplicitAny": false,       // ✅ Allow implicit any
    "strictNullChecks": false,    // ✅ Allow null/undefined

    /* JavaScript Support */
    "allowJs": true,              // ✅ CRITICAL: Allow JS files
    "checkJs": false,             // ✅ Don't type-check JS

    /* Interop Constraints */
    "isolatedModules": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,

    /* Skip Checking */
    "skipLibCheck": true,

    /* Emit */
    "noEmit": true
  },
  "include": [
    "src/**/*",
    "e2e/**/*",
    "vite.config.ts",
    "vitest.config.ts"
  ]
}
```

**Post-Migration tsconfig.json** (100% TypeScript):
```json
{
  "compilerOptions": {
    /* Same as above... */

    /* Type Checking - Still lenient but JS removed */
    "strict": false,              // Keep false for now
    "allowJs": false,             // ✅ CHANGED: No more JS files
    "checkJs": false,             // No JS to check

    /* Everything else unchanged */
  }
}
```

**Future: Incremental Strict Mode Enablement**:
```json
// Step 1: Enable noImplicitAny (1-2 weeks)
{
  "compilerOptions": {
    "strict": false,
    "noImplicitAny": true,     // ← Fix all implicit 'any' types
  }
}

// Step 2: Enable strictNullChecks (2-3 weeks)
{
  "compilerOptions": {
    "strict": false,
    "noImplicitAny": true,
    "strictNullChecks": true,  // ← Add null/undefined safety
  }
}

// Step 3: Enable full strict mode (1-2 weeks)
{
  "compilerOptions": {
    "strict": true,            // ← All strict checks
  }
}
```

### Why Lenient Settings Work

**Without `allowJs: true`**:
```bash
# Trying to migrate without allowJs
npx tsc --noEmit

# Result: 500+ errors for all JS files
❌ src/services/blogService.js - Cannot use JSX unless...
❌ src/components/BlogCard.jsx - File extension not allowed...
❌ src/utils/validation.js - Implicit any types...
# Migration is blocked!
```

**With `allowJs: true`**:
```bash
# Lenient settings allow mixed JS/TS
npx tsc --noEmit

# Result: Only errors in TS files you're actively converting
✓ All JS files ignored
✓ TS files type-checked
✓ Incremental progress possible
```

### Benefits

1. **Incremental Progress**: Convert files one at a time without breaking the build
2. **Continuous Development**: Feature work continues during migration
3. **Manageable Errors**: Only see errors in files you're actively working on
4. **Safe Rollback**: Each phase can be committed independently
5. **Team Velocity**: No "migration freeze" period required

### Anti-Patterns (What NOT to Do)

❌ **Enable Strict Mode During Migration**:
```json
// BAD: Too many errors to manage
{
  "compilerOptions": {
    "strict": true,           // 500+ errors immediately
    "allowJs": true
  }
}

// Result:
// - Overwhelming number of errors
// - Can't tell which are new vs. pre-existing
// - Migration paralyzed
```

❌ **Disable Safety Features**:
```json
// BAD: Removes value of TypeScript
{
  "compilerOptions": {
    "noUnusedLocals": false,     // Allows dead code
    "noUnusedParameters": false, // Allows unused params
    "allowUnreachableCode": true // Allows dead code paths
  }
}
```

### Verification

After migration complete, set `allowJs: false`:
```bash
# 1. Change tsconfig.json
{
  "allowJs": false  // No more JS files allowed
}

# 2. Verify no JS files remain
find src -name "*.js" -o -name "*.jsx"
# Should return nothing

# 3. Verify TypeScript compilation
npx tsc --noEmit
# Should exit with code 0 (success)

# 4. Commit
git add tsconfig.json
git commit -m "chore: disable allowJs after migration complete"
```

---

## Pattern 3: Type Definition Organization

**Grade Impact**: Foundation for type safety across entire codebase
**Why This Matters**: Centralized types ensure consistency and reusability

### The Pattern

Create a centralized `src/types/` directory with **domain-specific type files** and a **barrel export**.

### Directory Structure

```
src/
├── types/
│   ├── index.ts        # Barrel export (import from here)
│   ├── api.ts          # HTTP response wrappers
│   ├── auth.ts         # Authentication & user types
│   ├── forum.ts        # Forum entities (Thread, Post, Category)
│   ├── blog.ts         # Blog/Wagtail types
│   ├── diagnosis.ts    # Plant diagnosis types
│   └── plantId.ts      # Plant identification types
├── services/
├── components/
└── pages/
```

### Implementation

**1. Create Domain-Specific Type Files**

**`types/auth.ts`** (Authentication domain):
```typescript
/**
 * Authentication & User Types
 */

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  is_staff: boolean;
  is_moderator: boolean;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface SignupData {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
}

export interface AuthResponse {
  user: User;
  access: string;   // JWT access token
  refresh: string;  // JWT refresh token
}
```

**`types/forum.ts`** (Forum domain):
```typescript
/**
 * Forum Types (Community Discussion)
 */

import type { User } from './auth';

export interface Category {
  id: number;
  name: string;
  slug: string;
  description: string;
  parent: number | null;
  thread_count: number;
  post_count: number;
}

export interface Thread {
  id: number;
  title: string;
  content: string;
  author: User;
  category: Category;
  created_at: string;
  updated_at: string;
  is_pinned: boolean;
  is_locked: boolean;
  post_count: number;
}

export interface Post {
  id: number;
  thread: number;
  author: User;
  content: string;
  created_at: string;
  updated_at: string;
  attachments: Attachment[];
}

export interface Attachment {
  id: number;
  file: string;
  uploaded_at: string;
}

// Create types for API requests
export interface CreateThreadData {
  title: string;
  content: string;
  category: number;
}

export interface CreatePostData {
  thread: number;
  content: string;
}
```

**`types/blog.ts`** (Wagtail CMS domain):
```typescript
/**
 * Blog & Wagtail StreamField Types
 */

export interface BlogPost {
  id: number;
  title: string;
  slug: string;
  excerpt: string;
  content: StreamFieldBlock[];
  featured_image: string;
  author: {
    id: number;
    username: string;
  };
  published_date: string;
  categories: BlogCategory[];
}

export interface BlogCategory {
  id: number;
  name: string;
  slug: string;
}

// StreamField block types
export type StreamFieldBlock =
  | ParagraphBlock
  | HeadingBlock
  | ImageBlock
  | QuoteBlock
  | CodeBlock
  | ListBlock;

export interface ParagraphBlock {
  type: 'paragraph';
  value: string;
  id: string;
}

export interface HeadingBlock {
  type: 'heading';
  value: {
    level: 'h2' | 'h3' | 'h4';
    text: string;
  };
  id: string;
}

export interface ImageBlock {
  type: 'image';
  value: {
    url: string;
    alt: string;
    caption?: string;
  };
  id: string;
}

export interface QuoteBlock {
  type: 'quote';
  value: {
    text: string;
    attribution?: string;
  };
  id: string;
}

export interface CodeBlock {
  type: 'code';
  value: {
    language: string;
    code: string;
  };
  id: string;
}

export interface ListBlock {
  type: 'list';
  value: {
    items: string[];
    ordered: boolean;
  };
  id: string;
}
```

**`types/api.ts`** (HTTP response wrappers):
```typescript
/**
 * Generic API Response Types
 */

export interface ApiResponse<T> {
  data: T;
  status: number;
  statusText: string;
}

export interface WagtailApiResponse<T> {
  meta: {
    total_count: number;
  };
  items: T[];
}

export interface DRFPaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ApiError {
  message: string;
  status?: number;
  errors?: Record<string, string[]>;
}
```

**2. Create Barrel Export** (`types/index.ts`):
```typescript
/**
 * Central Type Definitions Export
 *
 * Import types from here for consistency:
 * import type { User, Thread, BlogPost } from '@/types';
 */

// API types
export type {
  ApiResponse,
  WagtailApiResponse,
  DRFPaginatedResponse,
  ApiError,
} from './api';

// Authentication types
export type {
  User,
  LoginCredentials,
  SignupData,
  AuthResponse,
} from './auth';

// Forum types
export type {
  Category,
  Thread,
  Post,
  Attachment,
  CreateThreadData,
  CreatePostData,
} from './forum';

// Blog types
export type {
  StreamFieldBlock,
  ParagraphBlock,
  HeadingBlock,
  ImageBlock,
  QuoteBlock,
  CodeBlock,
  ListBlock,
  BlogPost,
  BlogCategory,
} from './blog';

// Plant Identification types
export type {
  PlantIdentificationResult,
  Collection,
  UserPlant,
} from './plantId';

// Diagnosis types
export type {
  DiagnosisCard,
  DiagnosisReminder,
  HealthAssessment,
} from './diagnosis';
```

**3. Configure Path Alias** (`tsconfig.json`):
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

**4. Configure Vite** (`vite.config.ts`):
```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
```

### Usage in Code

**Services** (Type function signatures):
```typescript
import type { User, LoginCredentials, AuthResponse } from '@/types';

export async function loginUser(
  credentials: LoginCredentials
): Promise<AuthResponse> {
  const response = await httpClient.post<AuthResponse>(
    '/api/v1/auth/login/',
    credentials
  );
  return response.data;
}

export async function fetchCurrentUser(): Promise<User> {
  const response = await httpClient.get<User>('/api/v1/auth/me/');
  return response.data;
}
```

**Components** (Type props):
```typescript
import type { BlogPost } from '@/types';

interface BlogCardProps {
  post: BlogPost;
  showImage?: boolean;
}

export default function BlogCard({ post, showImage = true }: BlogCardProps) {
  return (
    <article>
      {showImage && <img src={post.featured_image} alt={post.title} />}
      <h2>{post.title}</h2>
      <p>{post.excerpt}</p>
    </article>
  );
}
```

**Contexts** (Type context values):
```typescript
import type { User } from '@/types';
import { createContext, useState, ReactNode } from 'react';

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  // ... implementation
}
```

### Type Extension Pattern

**When backend adds new fields**, extend existing types:

```typescript
// Backend adds new User fields
// Before:
export interface User {
  id: number;
  username: string;
  email: string;
}

// After:
export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;      // ← New
  last_name: string;       // ← New
  is_staff: boolean;       // ← New
  is_moderator: boolean;   // ← New
}

// All components using User type get updated automatically!
```

### Benefits

1. **Single Source of Truth**: All types defined in one place
2. **Consistent Imports**: `import type { User } from '@/types'` everywhere
3. **Easy Refactoring**: Change type once, updates everywhere
4. **Domain Separation**: Clear organization by feature/domain
5. **Discoverability**: Easy to find all types for a domain
6. **Type Reuse**: Share types between services, components, pages

### Anti-Patterns (What NOT to Do)

❌ **Inline Type Definitions**:
```typescript
// BAD: Type defined inside component file
// components/BlogCard.tsx
interface BlogPost {  // ← Should be in types/blog.ts
  id: number;
  title: string;
}

interface BlogCardProps {
  post: BlogPost;
}

// Problem: Type not reusable, duplicated across files
```

❌ **No Barrel Export**:
```typescript
// BAD: Direct imports from type files
import { User } from '../types/auth';
import { Thread } from '../types/forum';
import { BlogPost } from '../types/blog';

// Problem: Verbose imports, inconsistent paths
```

❌ **Mixed Type Locations**:
```typescript
// BAD: Types scattered across codebase
// services/blogService.ts
interface BlogPost { /* ... */ }

// components/BlogCard.tsx
interface BlogPost { /* ... */ }  // Duplicate!

// pages/BlogPage.tsx
interface BlogPost { /* ... */ }  // Duplicate!

// Problem: Duplicate definitions, inconsistencies, no single source of truth
```

### Verification

```bash
# 1. Check all type files exist
ls -la src/types/
# Should show: index.ts, api.ts, auth.ts, forum.ts, blog.ts, etc.

# 2. Verify imports use @/types alias
grep -r "from '@/types'" src/
# Should see consistent usage across codebase

# 3. Verify no inline interface duplicates
grep -r "interface User" src/
# Should only appear in src/types/auth.ts

# 4. TypeScript compilation check
npx tsc --noEmit
# Should pass with no errors
```

---

## Pattern 4: React Router Import Fix (v7)

**Grade Impact**: Critical for React Router v7 compatibility
**Why This Matters**: Breaking change in React Router v7 causes runtime errors

### The Problem

React Router v7 removed the `'react-router'` package exports. All imports must use `'react-router-dom'` instead.

**Error Message**:
```
TypeError: Cannot destructure property 'basename' of 'useContext(...)' as it is null
  at useLocation (react-router.development.js:380:1)
```

### The Pattern

**Before** (React Router v6):
```typescript
// ❌ BAD: Imports from 'react-router' (removed in v7)
import { useParams, useNavigate } from 'react-router';
```

**After** (React Router v7):
```typescript
// ✅ GOOD: Import from 'react-router-dom' instead
import { useParams, useNavigate } from 'react-router-dom';
```

### Migration Strategy

**Global Search and Replace** using `sed`:
```bash
# 1. Find all files importing from 'react-router'
grep -r "from 'react-router'" src/

# 2. Global replace with sed (macOS)
find src -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" \) \
  -exec sed -i '' "s/from 'react-router'/from 'react-router-dom'/g" {} +

# Linux version (no empty string after -i)
find src -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" \) \
  -exec sed -i "s/from 'react-router'/from 'react-router-dom'/g" {} +

# 3. Verify no 'react-router' imports remain
grep -r "from 'react-router'" src/
# Should return nothing

# 4. Test the app
npm run dev
# Navigate to routes, ensure no errors
```

### Files Affected (Example)

**Before Fix**:
```typescript
// src/pages/forum/ThreadDetailPage.tsx
import { useParams, useNavigate } from 'react-router';  // ❌

// src/pages/BlogDetailPage.tsx
import { useParams } from 'react-router';  // ❌

// src/components/layout/Header.tsx
import { Link, useLocation } from 'react-router';  // ❌

// ... 15+ files total
```

**After Fix**:
```typescript
// src/pages/forum/ThreadDetailPage.tsx
import { useParams, useNavigate } from 'react-router-dom';  // ✅

// src/pages/BlogDetailPage.tsx
import { useParams } from 'react-router-dom';  // ✅

// src/components/layout/Header.tsx
import { Link, useLocation } from 'react-router-dom';  // ✅
```

### Prevention

**1. ESLint Rule** (Prevent future regressions):
```javascript
// .eslintrc.cjs
module.exports = {
  rules: {
    'no-restricted-imports': [
      'error',
      {
        paths: [
          {
            name: 'react-router',
            message: "Import from 'react-router-dom' instead (React Router v7)",
          },
        ],
      },
    ],
  },
};
```

**2. Pre-commit Hook** (Block commits with wrong imports):
```bash
#!/bin/bash
# .git/hooks/pre-commit

# Check for react-router imports
if git diff --cached --name-only | grep -E '\.(ts|tsx|js|jsx)$' | xargs grep -l "from 'react-router'"; then
  echo "Error: Found imports from 'react-router'"
  echo "Use 'react-router-dom' instead (React Router v7)"
  exit 1
fi
```

### Testing After Fix

```bash
# 1. No TypeScript errors
npx tsc --noEmit

# 2. All tests pass
npm run test

# 3. Dev server starts without errors
npm run dev

# 4. Navigate to routes in browser
# - /forum
# - /forum/search
# - /blog
# - /blog/post-slug
# All should load without "Cannot destructure property 'basename'" error
```

### Impact

**Files Fixed**: 15+ files across pages, components, layouts
**Error Type**: Runtime error (hard to debug)
**Fix Complexity**: Simple (global search-replace)
**Prevention**: ESLint rule + pre-commit hook

---

## Pattern 5: Memory Leak Prevention (useRef for Timers)

**Grade Impact**: Critical for production stability
**Why This Matters**: Using `useState` for timers causes re-renders and memory leaks

### The Problem

**❌ WRONG** - Using `useState` for debounce timer:
```typescript
// SearchPage.tsx (BEFORE FIX)
const [debounceTimer, setDebounceTimer] = useState<NodeJS.Timeout | null>(null);

const handleInput = useCallback((e: ChangeEvent<HTMLInputElement>) => {
  const value = e.target.value;

  // Clear existing timer
  if (debounceTimer) {
    clearTimeout(debounceTimer);  // ← Reads state
  }

  // Set new timer
  const newTimer = setTimeout(() => {
    // Perform search
  }, 500);

  setDebounceTimer(newTimer);  // ← Triggers re-render!
}, [debounceTimer]);  // ← Dependency causes callback recreation

// Problems:
// 1. Setting timer state triggers re-render (unnecessary)
// 2. Callback dependency on debounceTimer causes recreation
// 3. Stale closures capture old timer values
// 4. Timer not cleaned up on unmount (memory leak!)
```

**Why This Causes Memory Leaks**:
1. `setDebounceTimer` triggers re-render
2. Component re-renders → `handleInput` recreated
3. Old `handleInput` references captured in setTimeout closures
4. Timers not cleaned up → memory leak

### The Solution

**✅ CORRECT** - Use `useRef` for timer:
```typescript
// SearchPage.tsx (AFTER FIX)
import { useRef, useCallback, useEffect, ChangeEvent } from 'react';

// Use ref for timer (no re-renders)
const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

const handleInput = useCallback((e: ChangeEvent<HTMLInputElement>) => {
  const value = e.target.value;

  // Clear existing timer
  if (debounceTimerRef.current) {
    clearTimeout(debounceTimerRef.current);
  }

  // Set new timer
  debounceTimerRef.current = setTimeout(() => {
    // Perform search
    setSearchParams(prev => {
      const newParams = new URLSearchParams(prev);
      newParams.set('q', value.trim());
      return newParams;
    });
  }, 500);
}, [setSearchParams]);  // ✅ Stable dependencies

// ✅ CRITICAL: Cleanup on unmount
useEffect(() => {
  return () => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
  };
}, []);
```

### Why useRef Works

**useRef vs. useState for Timers**:
```typescript
// useState:
// - Triggers re-render on every update
// - Callback dependencies change
// - Callback recreated on every render
// - Stale closures capture old values

// useRef:
// - No re-render on .current update
// - Stable reference across renders
// - Callback dependencies stay stable
// - No stale closures
```

### Complete Pattern

**Full implementation** (all required pieces):
```typescript
import { useState, useRef, useCallback, useEffect, ChangeEvent } from 'react';
import { useSearchParams } from 'react-router-dom';

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchInput, setSearchInput] = useState<string>('');

  // ✅ 1. Use ref for timer (not state)
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  // ✅ 2. Stable callback with no timer dependency
  const handleInput = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchInput(value);  // Update input immediately (no debounce)

    // Clear existing timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Set new timer
    debounceTimerRef.current = setTimeout(() => {
      if (value.trim()) {
        setSearchParams(prev => {
          const newParams = new URLSearchParams(prev);
          newParams.set('q', value.trim());
          newParams.set('page', '1');  // Reset pagination
          return newParams;
        });
      } else {
        setSearchParams(prev => {
          const newParams = new URLSearchParams(prev);
          newParams.delete('q');
          return newParams;
        });
      }
    }, 500);
  }, [setSearchParams]);

  // ✅ 3. Cleanup on unmount (REQUIRED)
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  return (
    <input
      type="text"
      value={searchInput}
      onChange={handleInput}
      placeholder="Search..."
    />
  );
}
```

### Other Timer Use Cases

**Intervals** (same pattern):
```typescript
const intervalRef = useRef<NodeJS.Timeout | null>(null);

useEffect(() => {
  // Start interval
  intervalRef.current = setInterval(() => {
    // Periodic task
  }, 1000);

  // Cleanup
  return () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
  };
}, []);
```

**Animation Frames**:
```typescript
const rafRef = useRef<number | null>(null);

useEffect(() => {
  const animate = () => {
    // Animation logic
    rafRef.current = requestAnimationFrame(animate);
  };

  rafRef.current = requestAnimationFrame(animate);

  // Cleanup
  return () => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }
  };
}, []);
```

### Benefits

1. **No Re-renders**: Updating `.current` doesn't trigger re-render
2. **Stable Callbacks**: Dependencies don't change, callbacks stay stable
3. **No Memory Leaks**: Cleanup function cancels pending timers
4. **Performance**: Fewer re-renders = better performance
5. **Correctness**: No stale closures capturing old values

### Anti-Patterns (What NOT to Do)

❌ **useState for Timer**:
```typescript
// BAD: Triggers re-renders
const [timer, setTimer] = useState<NodeJS.Timeout | null>(null);

const debouncedFn = useCallback(() => {
  if (timer) clearTimeout(timer);  // Stale closure!
  setTimer(setTimeout(...));       // Re-render!
}, [timer]);  // Dependency changes every time!
```

❌ **No Cleanup**:
```typescript
// BAD: Memory leak on unmount
const timerRef = useRef<NodeJS.Timeout | null>(null);

const debouncedFn = useCallback(() => {
  if (timerRef.current) clearTimeout(timerRef.current);
  timerRef.current = setTimeout(...);
}, []);

// ❌ MISSING: No cleanup on unmount
// Timer continues running after component unmounts!
```

❌ **Let Variable Instead of Ref**:
```typescript
// BAD: Lost on re-render
let timer: NodeJS.Timeout | null = null;

const debouncedFn = useCallback(() => {
  if (timer) clearTimeout(timer);  // ❌ Always null!
  timer = setTimeout(...);         // ❌ Lost on re-render!
}, []);

// Problem: `let` variable resets to null on every render
```

### Verification

**Memory Leak Detection** (Chrome DevTools):
```javascript
// 1. Open Chrome DevTools → Memory tab
// 2. Take heap snapshot
// 3. Trigger search input multiple times
// 4. Take another heap snapshot
// 5. Compare snapshots

// With useState (BEFORE):
// - Detached DOM nodes increase
// - Timer count increases
// - Memory grows linearly

// With useRef (AFTER):
// - Stable DOM nodes
// - One active timer at a time
// - Memory stable
```

**React DevTools Profiler**:
```javascript
// 1. Open React DevTools → Profiler
// 2. Start recording
// 3. Type in search input
// 4. Stop recording

// With useState (BEFORE):
// - Component re-renders on every timer set
// - Callback recreated multiple times
// - High render count

// With useRef (AFTER):
// - No re-renders from timer updates
// - Callback stable
// - Low render count
```

---

## Pattern 6: Logger Type Safety

**Grade Impact**: Prevents type errors in error logging
**Why This Matters**: Passing raw Error objects violates logger index signatures

### The Problem

**TypeScript Error**:
```
TS7053: Element implicitly has an 'any' type because expression of type 'string'
can't be used to index type 'Error'.
```

**❌ WRONG** - Passing raw Error:
```typescript
// ReminderManager.tsx (BEFORE)
try {
  await createReminder(data);
} catch (error) {
  logger.error('[REMINDER]', error);  // ❌ Type error!
  // Error: Can't index Error type with string keys
}
```

**Why This Fails**:
```typescript
// logger.ts signature (simplified)
function error(prefix: string, context?: Record<string, any>): void {
  // ...
}

// Error object is NOT Record<string, any>
// Error has prototype properties that aren't indexable
```

### The Solution

**✅ CORRECT** - Wrap error in context object:
```typescript
// ReminderManager.tsx (AFTER)
import { logger } from '../../utils/logger';

try {
  await createReminder(data);
  logger.info('[REMINDER] Created reminder successfully');
} catch (error) {
  logger.error('[REMINDER] Failed to create reminder', { error });
  // ✅ error wrapped in context object
  setError(error instanceof Error ? error.message : 'Failed to create reminder');
}
```

### Pattern Application

**All error logging** should use this pattern:
```typescript
// ✅ CORRECT: Wrap in context object
logger.error('[PREFIX] Error message', { error });
logger.error('[PREFIX] Error message', { error, context: { userId, action } });

// ❌ WRONG: Raw error object
logger.error('[PREFIX]', error);
logger.error('[PREFIX]', { message: error.message });  // Loses stack trace
```

### Complete Examples

**Service Error Handling**:
```typescript
// services/diagnosisService.ts
export async function createReminder(data: CreateReminderInput): Promise<DiagnosisReminder> {
  try {
    const response = await httpClient.post<DiagnosisReminder>(
      '/api/v1/diagnosis/reminders/',
      data
    );

    logger.info('[REMINDER] Created reminder', {
      context: {
        diagnosisCardId: data.diagnosis_card,
        reminderType: data.reminder_type
      }
    });

    return response.data;
  } catch (error) {
    logger.error('[REMINDER] Create failed', {
      error,
      context: {
        diagnosisCardId: data.diagnosis_card
      }
    });
    throw error;
  }
}
```

**Component Error Handling**:
```typescript
// components/diagnosis/SaveDiagnosisModal.tsx
const handleSave = async () => {
  try {
    setIsLoading(true);
    const result = await createDiagnosisCard(formData);

    logger.info('[DIAGNOSIS] Saved diagnosis card', {
      context: { cardId: result.id }
    });

    onSave(result);
    onClose();
  } catch (error) {
    logger.error('[DIAGNOSIS] Save failed', {
      error,
      context: {
        plantName: formData.plant_name
      }
    });

    setError(error instanceof Error ? error.message : 'Failed to save diagnosis');
  } finally {
    setIsLoading(false);
  }
};
```

**API Call Error Handling**:
```typescript
// utils/httpClient.ts
export async function get<T>(url: string): Promise<AxiosResponse<T>> {
  try {
    const response = await axios.get<T>(url);
    return response;
  } catch (error) {
    logger.error('[HTTP] GET request failed', {
      error,
      context: { url }
    });
    throw error;
  }
}
```

### Logger Implementation Reference

**Proper logger signature** (supports context object):
```typescript
// utils/logger.ts
interface LogContext {
  component?: string;
  error?: unknown;
  context?: Record<string, unknown>;
  [key: string]: unknown;
}

export const logger = {
  info: (message: string, context?: LogContext): void => {
    console.log(message, context);
  },

  error: (message: string, context?: LogContext): void => {
    console.error(message, context);

    // Optionally send to error tracking service
    if (context?.error instanceof Error) {
      // Send to Sentry, etc.
      Sentry.captureException(context.error, {
        extra: context.context,
      });
    }
  },

  warn: (message: string, context?: LogContext): void => {
    console.warn(message, context);
  },

  debug: (message: string, context?: LogContext): void => {
    if (import.meta.env.DEV) {
      console.debug(message, context);
    }
  },
};
```

### Benefits

1. **Type Safety**: No TypeScript errors when logging errors
2. **Structured Logging**: Context object is easily serialized to JSON
3. **Stack Traces**: Error object preserved with full stack trace
4. **Searchable**: Bracket prefixes enable log filtering
5. **Error Tracking**: Easy integration with Sentry, Datadog, etc.

### Anti-Patterns (What NOT to Do)

❌ **Raw Error Object**:
```typescript
// BAD: Type error
logger.error('[PREFIX]', error);
```

❌ **String Interpolation**:
```typescript
// BAD: Loses stack trace
logger.error(`[PREFIX] Error: ${error.message}`);
```

❌ **Manual Stringification**:
```typescript
// BAD: Hard to parse, loses type info
logger.error('[PREFIX]', JSON.stringify(error));
```

### Verification

```bash
# 1. Search for raw error logging
grep -r "logger\.error.*error)" src/
# Should find no instances passing error directly

# 2. Verify all use context object
grep -r "logger\.error.*{ error" src/
# Should find all error logs

# 3. TypeScript compilation check
npx tsc --noEmit
# Should pass with no TS7053 errors

# 4. Test error logging in browser
# - Trigger error condition
# - Check browser console
# - Verify error object logged with full context
```

---

## Pattern 7: Readonly Type Compatibility

**Grade Impact**: Enables type safety with const assertions
**Why This Matters**: Const assertions create readonly types incompatible with mutable interfaces

### The Problem

**TypeScript Error**:
```
TS2322: Type 'readonly string[]' is not assignable to type 'string[]'.
The type 'readonly string[]' is 'readonly' and cannot be assigned to the mutable type 'string[]'.
```

**Root Cause**:
```typescript
// sanitize.ts

// ❌ BEFORE: Interface expects mutable array
interface SanitizeConfig {
  ALLOWED_TAGS: string[];      // Mutable
  ALLOWED_ATTR: string[];      // Mutable
}

// Const assertion creates readonly arrays
export const SANITIZE_PRESETS = {
  MINIMAL: {
    ALLOWED_TAGS: ['p', 'br', 'strong'],  // Type: readonly string[]
    ALLOWED_ATTR: [],                      // Type: readonly string[]
  } as const,  // ← 'as const' makes arrays readonly
};

// ❌ Type error: readonly string[] not assignable to string[]
```

**Why `as const` Creates Readonly Arrays**:
```typescript
// Without 'as const'
const arr1 = ['a', 'b', 'c'];
// Type: string[] (mutable)
arr1.push('d');  // ✅ Allowed

// With 'as const'
const arr2 = ['a', 'b', 'c'] as const;
// Type: readonly ['a', 'b', 'c'] (immutable)
arr2.push('d');  // ❌ Error: push does not exist on readonly array
```

### The Solution

**✅ CORRECT** - Accept both mutable and readonly arrays:
```typescript
// sanitize.ts (AFTER)

interface SanitizeConfig {
  ALLOWED_TAGS: readonly string[] | string[];  // ✅ Accept both
  ALLOWED_ATTR: readonly string[] | string[];  // ✅ Accept both
  ALLOWED_CLASSES?: Record<string, readonly string[] | string[]>;
  ALLOW_DATA_ATTR?: boolean;
}

// Now const assertions work
export const SANITIZE_PRESETS = {
  MINIMAL: {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u'],
    ALLOWED_ATTR: [],
  } as const,  // ✅ No type error

  BASIC: {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 'a'],
    ALLOWED_ATTR: ['href', 'target', 'rel'],
  } as const,  // ✅ No type error

  FORUM: {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'u', 'a',
      'ul', 'ol', 'li', 'h1', 'h2', 'h3',
      'blockquote', 'code', 'pre', 'img',
    ],
    ALLOWED_ATTR: [
      'href', 'target', 'rel', 'class',
      'src', 'alt', 'title',
      'data-mention', 'data-mention-id',
    ],
    ALLOWED_CLASSES: {
      span: ['mention'],
      code: ['language-*'],
    },
    ALLOW_DATA_ATTR: false,
  } as const,  // ✅ No type error
};
```

### When to Use This Pattern

**Use `as const` when**:
1. Config values should never change at runtime
2. You want literal types (not widened types)
3. You want TypeScript to infer exact values

**Example - Without `as const`**:
```typescript
const CONFIG = {
  API_URL: 'https://api.example.com',  // Type: string (wide)
  MAX_ITEMS: 10,                        // Type: number (wide)
  ALLOWED_TAGS: ['p', 'br'],            // Type: string[] (mutable)
};

CONFIG.API_URL = 'https://hacker.com';  // ✅ Allowed (not const)
CONFIG.ALLOWED_TAGS.push('script');     // ✅ Allowed (mutable)
```

**Example - With `as const`**:
```typescript
const CONFIG = {
  API_URL: 'https://api.example.com',  // Type: 'https://api.example.com' (literal)
  MAX_ITEMS: 10,                        // Type: 10 (literal)
  ALLOWED_TAGS: ['p', 'br'],            // Type: readonly ['p', 'br'] (immutable)
} as const;

CONFIG.API_URL = 'https://hacker.com';  // ❌ Error: Cannot assign to readonly
CONFIG.ALLOWED_TAGS.push('script');     // ❌ Error: push does not exist
```

### Complete Pattern

**Full implementation** with proper types:
```typescript
// utils/sanitize.ts

import DOMPurify from 'dompurify';

/**
 * DOMPurify configuration options
 *
 * Accepts both readonly and mutable arrays for flexibility.
 * Use readonly arrays for const assertions.
 */
interface SanitizeConfig {
  ALLOWED_TAGS: readonly string[] | string[];
  ALLOWED_ATTR: readonly string[] | string[];
  ALLOWED_CLASSES?: Record<string, readonly string[] | string[]>;
  ALLOW_DATA_ATTR?: boolean;
}

/**
 * Sanitization preset configurations
 *
 * Uses 'as const' to ensure values are immutable at runtime.
 * Provides type safety for preset selection.
 */
export const SANITIZE_PRESETS = {
  /**
   * MINIMAL: Only basic inline formatting
   * Use for: Simple text excerpts, user comments
   */
  MINIMAL: {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u'],
    ALLOWED_ATTR: [],
  } as const,

  /**
   * BASIC: Basic formatting + links
   * Use for: Blog card excerpts, short descriptions
   */
  BASIC: {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 'a'],
    ALLOWED_ATTR: ['href', 'target', 'rel'],
  } as const,

  /**
   * FORUM: Rich forum posts with mentions, code blocks, images
   * Use for: Forum posts, thread content
   */
  FORUM: {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'u', 'a',
      'ul', 'ol', 'li', 'h1', 'h2', 'h3',
      'blockquote', 'code', 'pre', 'img', 'span', 'div',
    ],
    ALLOWED_ATTR: [
      'href', 'target', 'rel', 'class', 'src', 'alt', 'title',
      'data-mention', 'data-mention-id',
    ],
    ALLOWED_CLASSES: {
      span: ['mention'],
      code: ['language-*'],
      div: ['code-block'],
    },
    ALLOW_DATA_ATTR: false,
  } as const,
} as const;  // ← Const assertion on entire object

/**
 * Sanitize HTML content with preset or custom configuration
 */
export function sanitizeHtml(
  html: unknown,
  options: Partial<SanitizeConfig> | null = null
): string {
  if (!html || typeof html !== 'string') {
    return '';
  }

  try {
    const config = options || SANITIZE_PRESETS.BASIC;
    return DOMPurify.sanitize(html, config as any) as string;
  } catch (error) {
    logger.error('DOMPurify sanitization failed', {
      error,
      context: { htmlLength: (html as string)?.length },
    });
    return '';
  }
}
```

### Usage Examples

```typescript
// Component usage
import { sanitizeHtml, SANITIZE_PRESETS } from '../utils/sanitize';

// Use preset
const safeHTML = sanitizeHtml(userContent, SANITIZE_PRESETS.FORUM);

// Use custom config (mutable arrays work too)
const safeHTML = sanitizeHtml(userContent, {
  ALLOWED_TAGS: ['p', 'br'],      // Mutable array
  ALLOWED_ATTR: ['class'],        // Mutable array
});

// Default (BASIC preset)
const safeHTML = sanitizeHtml(userContent);
```

### Benefits

1. **Type Safety**: Both readonly and mutable arrays accepted
2. **Immutability**: Const assertions prevent runtime modifications
3. **Literal Types**: TypeScript infers exact values for better checking
4. **Flexibility**: Supports custom mutable configs when needed
5. **Security**: Prevents accidental config modifications

### Anti-Patterns (What NOT to Do)

❌ **Mutable-Only Interface**:
```typescript
// BAD: Rejects const assertions
interface SanitizeConfig {
  ALLOWED_TAGS: string[];  // Only accepts mutable
}

const PRESET = {
  ALLOWED_TAGS: ['p', 'br'],
} as const;  // ❌ Type error!
```

❌ **No Const Assertion**:
```typescript
// BAD: Values can be modified at runtime
export const SANITIZE_PRESETS = {
  MINIMAL: {
    ALLOWED_TAGS: ['p', 'br', 'strong'],  // Mutable!
  },
};

// Allows runtime modification (security risk)
SANITIZE_PRESETS.MINIMAL.ALLOWED_TAGS.push('script');  // ✅ Allowed (bad!)
```

❌ **Type Casting Without Fix**:
```typescript
// BAD: Hides the problem instead of fixing it
interface SanitizeConfig {
  ALLOWED_TAGS: string[];  // Mutable only
}

const PRESET = {
  ALLOWED_TAGS: ['p', 'br'] as const,
} as SanitizeConfig;  // ❌ Type assertion hides incompatibility
```

### Verification

```bash
# 1. TypeScript compilation check
npx tsc --noEmit
# Should pass with no TS2322 errors

# 2. Test const assertion immutability
# In TypeScript playground or console:
import { SANITIZE_PRESETS } from './utils/sanitize';
SANITIZE_PRESETS.MINIMAL.ALLOWED_TAGS.push('script');
# Should show TypeScript error: push does not exist on readonly array

# 3. Verify runtime immutability
# In browser console:
import { SANITIZE_PRESETS } from './utils/sanitize';
try {
  SANITIZE_PRESETS.MINIMAL.ALLOWED_TAGS.push('script');
} catch (e) {
  console.log(e);  // TypeError: Cannot add property
}
```

---

## Pattern 8: PropTypes Removal Timing

**Grade Impact**: Critical for clean migration completion
**Why This Matters**: Removing PropTypes too early causes runtime errors

### The Pattern

**DO NOT remove PropTypes until 100% TypeScript conversion complete**

### Migration Phases

**Phase 1-7: Keep PropTypes** (Incremental conversion)
```typescript
// DURING MIGRATION: Keep both TypeScript types AND PropTypes

import PropTypes from 'prop-types';
import type { BlogPost } from '@/types';

interface BlogCardProps {
  post: BlogPost;      // ← TypeScript type
  showImage?: boolean;
}

function BlogCard({ post, showImage = true }: BlogCardProps) {
  // ... implementation
}

// ← Keep PropTypes for now (defense in depth)
BlogCard.propTypes = {
  post: PropTypes.object.isRequired,
  showImage: PropTypes.bool,
};

export default BlogCard;
```

**Phase 8: Remove PropTypes** (After 100% conversion)
```bash
# 1. Verify ALL files converted to TypeScript
find src -name "*.js" -o -name "*.jsx"
# Should return NOTHING

# 2. Verify zero TypeScript errors
npx tsc --noEmit
# Should exit with code 0

# 3. Run full test suite
npm run test
# Should pass 100%

# 4. Set allowJs: false in tsconfig.json
{
  "compilerOptions": {
    "allowJs": false  // ← Enforce TypeScript only
  }
}

# 5. Remove prop-types package
npm uninstall prop-types

# 6. Remove all PropTypes imports and definitions
# (Can use automated script - see below)

# 7. Verify build still works
npm run build

# 8. Commit
git add .
git commit -m "chore: remove PropTypes after TypeScript migration"
```

### Automated PropTypes Removal

**Script to remove PropTypes** (run after verification):
```bash
#!/bin/bash
# remove-proptypes.sh

# Remove PropTypes imports
find src -type f \( -name "*.ts" -o -name "*.tsx" \) \
  -exec sed -i '' "/import.*PropTypes.*from 'prop-types'/d" {} +

# Remove PropTypes definitions
find src -type f \( -name "*.ts" -o -name "*.tsx" \) \
  -exec sed -i '' "/\.propTypes = {/,/^};$/d" {} +

# Remove standalone PropTypes blocks
find src -type f \( -name "*.ts" -o -name "*.tsx" \) \
  -exec sed -i '' "/^.*\.propTypes = {/,/^}/d" {} +

echo "PropTypes removed. Verify with: git diff"
```

### Why Wait Until 100% Conversion?

**Scenario 1: Remove PropTypes Too Early**
```typescript
// File 1: Converted to TypeScript (PropTypes removed)
// components/BlogCard.tsx
interface BlogCardProps {
  post: BlogPost;
}
function BlogCard({ post }: BlogCardProps) { /* ... */ }
// No PropTypes

// File 2: Still JavaScript (not converted yet)
// pages/BlogPage.jsx
function BlogPage() {
  return <BlogCard post={invalidData} />;  // ❌ Runtime error!
  // No PropTypes to catch invalid prop at runtime
  // TypeScript can't check JSX files
}
```

**Scenario 2: Wait Until 100% (Correct)**
```typescript
// All files converted to TypeScript
// PropTypes can be safely removed

// components/BlogCard.tsx
interface BlogCardProps {
  post: BlogPost;
}
function BlogCard({ post }: BlogCardProps) { /* ... */ }

// pages/BlogPage.tsx (TypeScript now)
function BlogPage() {
  return <BlogCard post={invalidData} />;  // ✅ TypeScript error!
  // Caught at compile time
}
```

### Benefits

1. **Defense in Depth**: PropTypes catch runtime errors during migration
2. **Incremental Safety**: Both TypeScript and PropTypes validate props
3. **No Regression**: Runtime validation continues until 100% TypeScript
4. **Clear Milestone**: PropTypes removal signals migration complete
5. **Verification**: `allowJs: false` prevents new JS files

### Anti-Patterns (What NOT to Do)

❌ **Remove PropTypes Before 100% Conversion**:
```bash
# BAD: Still have JS files
find src -name "*.js" -o -name "*.jsx"
# Output: pages/BlogPage.jsx (not converted yet)

npm uninstall prop-types  # ❌ Too early!
# Result: Runtime errors in JS files
```

❌ **Remove PropTypes Without Verification**:
```bash
# BAD: No testing before removal
npm uninstall prop-types
# (Didn't run tests or check for JS files)

npm run build  # ❌ Build fails!
# Too late to recover
```

❌ **Keep allowJs: true After PropTypes Removal**:
```json
// BAD: Allows new JS files after migration
{
  "compilerOptions": {
    "allowJs": true  // ❌ Should be false
  }
}

// Problem: Developers can add new .js files
// Defeating the purpose of TypeScript migration
```

### Verification Checklist

**Before Removing PropTypes**:
- [ ] All `.js` files converted to `.ts`
- [ ] All `.jsx` files converted to `.tsx`
- [ ] `npx tsc --noEmit` passes (zero errors)
- [ ] Full test suite passes (`npm run test`)
- [ ] Build completes successfully (`npm run build`)
- [ ] `allowJs: false` set in tsconfig.json

**After Removing PropTypes**:
- [ ] `npm run test` passes (no runtime errors)
- [ ] `npm run build` passes (no build errors)
- [ ] Dev server starts (`npm run dev`)
- [ ] All routes render without errors
- [ ] No PropTypes imports remain (`grep -r "PropTypes" src/`)
- [ ] `prop-types` removed from package.json

### Testing After Removal

```bash
# 1. Full test suite
npm run test
# Should pass 100%

# 2. Build verification
npm run build
# Should complete without errors

# 3. Dev server
npm run dev
# Navigate to all routes, verify no errors

# 4. Search for remaining PropTypes
grep -r "PropTypes" src/
# Should return nothing

# 5. Verify package.json
grep "prop-types" package.json
# Should return nothing
```

---

## Pattern 9: Test Stability During Migration

**Grade Impact**: Critical for confidence in migration success
**Why This Matters**: Tests prove no regressions introduced

### The Pattern

**Maintain 100% test pass rate throughout migration**

### Test Strategy

**Baseline Before Migration**:
```bash
# 1. Run full test suite before starting
npm run test

# Baseline:
# ✓ 492 tests passing
# ✗ 41 tests failing (pre-existing React Router mocking issues)
# Total: 533 tests

# Document baseline
echo "Baseline: 492 passing, 41 failing" > MIGRATION_BASELINE.txt
git add MIGRATION_BASELINE.txt
git commit -m "docs: document test baseline before TypeScript migration"
```

**Test After Each Phase**:
```bash
# After Phase 2 (Utilities)
npm run test
# Expected: 492 passing, 41 failing (same as baseline)

# After Phase 3 (Type Definitions)
npm run test
# Expected: 492 passing, 41 failing

# After Phase 4 (Services)
npm run test
# Expected: 492 passing, 41 failing

# ... and so on for each phase
```

### Handling Pre-existing Failures

**Track Pre-existing vs. New Failures**:
```bash
# Before migration
npm run test > baseline-results.txt

# After Phase N
npm run test > phase-N-results.txt

# Compare
diff baseline-results.txt phase-N-results.txt

# Expected: No new failures
# Acceptable: Same 41 failures (React Router mocking)
# ❌ BLOCK: Any new failures must be fixed before continuing
```

**Document Known Failures**:
```markdown
# KNOWN_TEST_FAILURES.md

## Pre-existing Failures (41 tests)

These failures existed before TypeScript migration and are NOT caused by migration:

**Category**: React Router v7 Hook Mocking (41 tests)
**Root Cause**: `useNavigate`, `useParams`, `useLocation` mocks not working in Vitest
**Impact**: Navigation tests fail, but functionality works in browser
**Status**: Tracking in separate issue #XYZ
**Workaround**: Manual E2E testing for navigation flows

**Files Affected**:
- `src/pages/forum/ThreadDetailPage.test.tsx` (15 tests)
- `src/pages/BlogDetailPage.test.tsx` (10 tests)
- `src/components/layout/Header.test.tsx` (8 tests)
- ... (8 more files)

**Migration Rule**: These 41 failures are acceptable. ANY NEW failures block migration.
```

### Test Update Strategy

**Update Import Paths** (TypeScript extensions):
```typescript
// BEFORE (JavaScript):
// BlogCard.test.jsx
import BlogCard from '../BlogCard';  // .jsx extension

// AFTER (TypeScript):
// BlogCard.test.tsx
import BlogCard from '../BlogCard';  // .tsx extension (extension omitted)
```

**Update Test Type Annotations**:
```typescript
// BEFORE (JavaScript):
// BlogCard.test.jsx
describe('BlogCard', () => {
  it('renders post title', () => {
    const post = { title: 'Test', ... };
    render(<BlogCard post={post} />);
    expect(screen.getByText('Test')).toBeInTheDocument();
  });
});

// AFTER (TypeScript):
// BlogCard.test.tsx
import type { BlogPost } from '@/types';

describe('BlogCard', () => {
  it('renders post title', () => {
    const post: BlogPost = {
      id: 1,
      title: 'Test',
      slug: 'test',
      excerpt: 'Test excerpt',
      content: [],
      featured_image: '',
      author: { id: 1, username: 'test' },
      published_date: '2025-01-01',
      categories: [],
    };

    render(<BlogCard post={post} />);
    expect(screen.getByText('Test')).toBeInTheDocument();
  });
});
```

### Zero New Failures Rule

**BLOCK migration if**:
- New test failures introduced
- Build breaks
- TypeScript compilation errors appear
- Runtime errors in browser

**Example - Phase 4 blocked**:
```bash
# After converting services to TypeScript
npm run test

# Result:
# ✓ 480 tests passing  # ❌ 12 fewer than baseline!
# ✗ 53 tests failing    # ❌ 12 more than baseline!

# Action: STOP migration
# Debug: Find which service conversion broke tests
# Fix: Correct TypeScript types causing failures
# Verify: npm run test → 492 passing (back to baseline)
# Continue: Proceed to Phase 5
```

### Test Coverage Verification

**Ensure coverage doesn't drop**:
```bash
# Before migration
npm run test:coverage

# Coverage baseline:
# Statements: 85%
# Branches: 78%
# Functions: 82%
# Lines: 85%

# After migration (should be same or better)
npm run test:coverage

# Coverage after TypeScript:
# Statements: 87% ✅ (improved)
# Branches: 79% ✅
# Functions: 84% ✅
# Lines: 87% ✅
```

### Benefits

1. **Regression Detection**: Catch breaking changes immediately
2. **Confidence**: Migration success proven by stable tests
3. **Incremental Progress**: Each phase independently verified
4. **Documentation**: Test results document migration quality
5. **Rollback**: Easy to revert if tests fail

### Anti-Patterns (What NOT to Do)

❌ **Skip Testing Between Phases**:
```bash
# BAD: Convert multiple phases without testing
# Phase 2: Utilities converted
# Phase 3: Type Definitions converted
# Phase 4: Services converted
npm run test  # ❌ First test in 3 phases!

# Result: 100+ failures
# Problem: Which phase introduced failures?
# Debug time: Hours to isolate root cause
```

❌ **Ignore Pre-existing Failures**:
```bash
# BAD: Not tracking baseline
# Before migration: 492 passing, 41 failing
npm run test  # (Didn't document baseline)

# After Phase 5: 485 passing, 48 failing
# Question: Did we introduce 7 new failures? Or 14?
# Problem: Can't tell without baseline
```

❌ **Disable Failing Tests**:
```typescript
// BAD: Hide failures instead of fixing
describe.skip('BlogCard', () => {  // ❌ Disabled test
  it('renders post title', () => {
    // Test broken by TypeScript migration
  });
});

// Problem: Lost test coverage, hidden regressions
```

### Verification

**After Each Phase**:
```bash
# 1. Run full test suite
npm run test

# 2. Compare to baseline
# Expected: 492 passing, 41 failing (stable)
# ❌ Block if: Any new failures

# 3. Run TypeScript compiler
npx tsc --noEmit
# Expected: Zero errors
# ❌ Block if: Any compilation errors

# 4. Test build
npm run build
# Expected: Success
# ❌ Block if: Build fails

# 5. Manual smoke test
npm run dev
# Navigate to: /, /blog, /forum, /forum/search
# Expected: All routes render without errors
# ❌ Block if: Runtime errors in console

# 6. Commit if all pass
git add .
git commit -m "feat: migrate Phase N to TypeScript (492 tests passing)"
```

---

## Verification Checklist

Use this checklist to verify TypeScript migration success:

### Pre-Migration Setup
- [ ] Install TypeScript dependencies (`typescript`, `@types/react`, `@types/react-dom`)
- [ ] Create `tsconfig.json` with lenient settings (`strict: false`, `allowJs: true`)
- [ ] Convert build configs to TypeScript (`vite.config.ts`, `vitest.config.ts`)
- [ ] Run baseline tests, document results
- [ ] Commit setup changes

### Phase-by-Phase Migration
- [ ] Phase 1: Foundation setup complete (no code changes)
- [ ] Phase 2: Utilities & constants converted (11 files)
- [ ] Phase 3: Type definitions created (6 files)
- [ ] Phase 4: Services converted (5 files)
- [ ] Phase 5: Contexts & hooks converted (3 files)
- [ ] Phase 6: UI components converted (29 files)
- [ ] Phase 7: Pages converted (18 files)
- [ ] All tests passing after each phase (no regressions)

### Error Resolution
- [ ] Fix React Router v7 imports (sed global replace)
- [ ] Fix memory leaks (useRef for timers)
- [ ] Fix logger type safety (wrap errors in context objects)
- [ ] Fix readonly type compatibility (accept both readonly and mutable)
- [ ] All TypeScript compilation errors resolved (`npx tsc --noEmit` passes)

### Final Cleanup
- [ ] Remove `prop-types` package (`npm uninstall prop-types`)
- [ ] Set `allowJs: false` in tsconfig.json
- [ ] Verify no `.js` or `.jsx` files remain in src/
- [ ] All tests passing (same as baseline)
- [ ] Build succeeds (`npm run build`)
- [ ] Dev server starts (`npm run dev`)
- [ ] Manual smoke testing (all routes render)

### Documentation
- [ ] Create `TYPESCRIPT_MIGRATION_COMPLETE.md`
- [ ] Update `CLAUDE.md` with TypeScript patterns
- [ ] Document any deviations from plan
- [ ] Create migration lessons learned doc

### Deployment Readiness
- [ ] TypeScript compilation check passes in CI/CD
- [ ] Test suite passes in CI/CD
- [ ] Build succeeds in CI/CD
- [ ] Production bundle size acceptable (<2% increase)
- [ ] Code review completed
- [ ] Merge to main approved

### Future: Strict Mode Enablement
- [ ] Plan strict mode enablement (separate issue)
- [ ] Incrementally enable: `noImplicitAny` → `strictNullChecks` → `strict: true`
- [ ] Remove remaining `any` types (~10-15 occurrences)
- [ ] Add stricter event handler types
- [ ] Update documentation with strict mode patterns

---

## Summary

These 9 TypeScript migration patterns form a comprehensive guide for migrating any React codebase to TypeScript:

1. **Bottom-Up Migration Strategy**: Utilities → Services → Contexts → Components → Pages
2. **Lenient TypeScript Config**: `strict: false`, `allowJs: true` during migration
3. **Type Definition Organization**: Centralized `src/types/` with barrel exports
4. **React Router v7 Fix**: Import from `'react-router-dom'` not `'react-router'`
5. **Memory Leak Prevention**: Use `useRef` for timers, not `useState`
6. **Logger Type Safety**: Wrap errors in context objects `{ error }`
7. **Readonly Compatibility**: Accept `readonly string[] | string[]` for const assertions
8. **PropTypes Removal Timing**: Remove ONLY after 100% TypeScript conversion
9. **Test Stability**: Maintain baseline test pass rate throughout migration

### Key Metrics Achieved

- **Files Converted**: 50+ files
- **Lines Migrated**: ~10,000 lines
- **TypeScript Errors**: 0 (zero compilation errors)
- **Test Regressions**: 0 (492 tests passing, stable)
- **Downtime**: 0 (incremental deployment)
- **Code Review Grade**: A (95/100)

### Next Steps

**After Migration Complete**:
1. Merge TypeScript migration to main
2. Enable `allowJs: false` to prevent new JS files
3. Plan incremental strict mode enablement
4. Remove remaining `any` types
5. Update team documentation

**Future Enhancements**:
1. Enable `noImplicitAny: true` (1-2 weeks)
2. Enable `strictNullChecks: true` (2-3 weeks)
3. Enable full `strict: true` (1-2 weeks)
4. Add utility types for common patterns
5. Improve generic type constraints

---

**Document End**
