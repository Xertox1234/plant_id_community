# TypeScript Migration Checklist

**Quick Reference**: Use this checklist for migrating a React codebase to TypeScript
**Full Documentation**: See `TYPESCRIPT_MIGRATION_PATTERNS_CODIFIED.md`
**Status**: ✅ Verified (Issue #134 - 100% success, zero regressions)

---

## Pre-Migration Setup

- [ ] **Install TypeScript dependencies**
  ```bash
  npm install --save-dev typescript @types/react @types/react-dom
  ```

- [ ] **Create lenient tsconfig.json**
  ```json
  {
    "compilerOptions": {
      "target": "ES2022",
      "lib": ["ES2022", "DOM", "DOM.Iterable"],
      "jsx": "react-jsx",
      "module": "ESNext",
      "moduleResolution": "bundler",

      "strict": false,        // ← Lenient during migration
      "allowJs": true,        // ← CRITICAL: Allow JS files
      "checkJs": false,

      "isolatedModules": true,
      "esModuleInterop": true,
      "skipLibCheck": true,
      "noEmit": true
    }
  }
  ```

- [ ] **Convert build configs to TypeScript**
  ```bash
  mv vite.config.js vite.config.ts
  mv vitest.config.js vitest.config.ts
  mv playwright.config.js playwright.config.ts
  ```

- [ ] **Run baseline tests, document results**
  ```bash
  npm run test > baseline-tests.txt
  # Document: X passing, Y failing
  ```

- [ ] **Verify build still works**
  ```bash
  npm run build
  npm run dev
  ```

- [ ] **Commit setup changes**
  ```bash
  git add tsconfig.json *.config.ts
  git commit -m "chore: setup TypeScript (Phase 1)"
  ```

---

## Phase 2: Utilities & Constants (11 files)

**Strategy**: Convert pure functions first (no React dependencies)

- [ ] `utils/validation.ts`
- [ ] `utils/sanitize.ts`
- [ ] `utils/logger.ts`
- [ ] `utils/constants.ts`
- [ ] `utils/httpClient.ts`
- [ ] `utils/csrf.ts`
- [ ] `utils/domSanitizer.ts`
- [ ] `utils/formatDate.ts`
- [ ] `utils/imageCompression.ts`
- [ ] `utils/plantUtils.ts`
- [ ] `tests/forumUtils.ts`

**After conversion**:
- [ ] `npx tsc --noEmit` passes
- [ ] `npm run test` - same pass rate as baseline
- [ ] Commit: `git commit -m "feat: migrate utilities to TypeScript (Phase 2)"`

---

## Phase 3: Type Definitions (6 files)

**Strategy**: Create centralized type system

- [ ] Create `src/types/` directory
- [ ] `types/api.ts` - HTTP response wrappers
- [ ] `types/auth.ts` - User, LoginCredentials, AuthResponse
- [ ] `types/forum.ts` - Thread, Post, Category, Attachment
- [ ] `types/blog.ts` - BlogPost, StreamFieldBlock variants
- [ ] `types/diagnosis.ts` - DiagnosisCard, DiagnosisReminder
- [ ] `types/plantId.ts` - PlantIdentificationResult
- [ ] `types/index.ts` - Barrel export

**Barrel export** (`types/index.ts`):
```typescript
export type { User, LoginCredentials, AuthResponse } from './auth';
export type { Thread, Post, Category } from './forum';
export type { BlogPost, StreamFieldBlock } from './blog';
// ... all types
```

**Configure path alias** (tsconfig.json):
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

**After creation**:
- [ ] All domain entities have type definitions
- [ ] Barrel export works: `import type { User } from '@/types'`
- [ ] Commit: `git commit -m "feat: create TypeScript type definitions (Phase 3)"`

---

## Phase 4: Services (5 files)

**Strategy**: Type API layer with proper error handling

- [ ] `services/authService.ts`
- [ ] `services/blogService.ts`
- [ ] `services/forumService.ts`
- [ ] `services/plantIdService.ts`
- [ ] `services/diagnosisService.ts`

**Pattern**: Add type annotations to function signatures
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
```

**After conversion**:
- [ ] All service methods have type annotations
- [ ] Return types specified for all functions
- [ ] `npx tsc --noEmit` passes
- [ ] `npm run test` - same pass rate as baseline
- [ ] Commit: `git commit -m "feat: migrate services to TypeScript (Phase 4)"`

---

## Phase 5: Contexts & Hooks (3 files)

**Strategy**: Type React context and custom hooks

- [ ] `contexts/AuthContext.tsx`
- [ ] `contexts/RequestContext.tsx`
- [ ] `hooks/useAuth.ts`

**Pattern**: Define context value interface
```typescript
import type { User } from '@/types';
import { ReactNode } from 'react';

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
  // ...
}
```

**After conversion**:
- [ ] Context values have type definitions
- [ ] Custom hooks have return type annotations
- [ ] `npx tsc --noEmit` passes
- [ ] `npm run test` - same pass rate as baseline
- [ ] Commit: `git commit -m "feat: migrate contexts & hooks to TypeScript (Phase 5)"`

---

## Phase 6: UI Components (29 files)

**Strategy**: Convert components bottom-up (simple → complex)

**Simple UI** (3 files):
- [ ] `components/ui/Button.tsx`
- [ ] `components/ui/Input.tsx`
- [ ] `components/ui/LoadingSpinner.tsx`

**Card Components** (4 files):
- [ ] `components/BlogCard.tsx`
- [ ] `components/forum/CategoryCard.tsx`
- [ ] `components/forum/PostCard.tsx`
- [ ] `components/forum/ThreadCard.tsx`

**Layout Components** (4 files):
- [ ] `components/layout/Header.tsx`
- [ ] `components/layout/Footer.tsx`
- [ ] `components/layout/UserMenu.tsx`
- [ ] `layouts/RootLayout.tsx`
- [ ] `layouts/ProtectedLayout.tsx`

**Complex Components** (4 files):
- [ ] `components/forum/TipTapEditor.tsx`
- [ ] `components/forum/ImageUploadWidget.tsx`
- [ ] `components/StreamFieldRenderer.tsx`
- [ ] `components/ErrorBoundary.tsx`

**Diagnosis Components** (4 files):
- [ ] `components/diagnosis/DiagnosisCard.tsx`
- [ ] `components/diagnosis/ReminderManager.tsx`
- [ ] `components/diagnosis/SaveDiagnosisModal.tsx`
- [ ] `components/diagnosis/StreamFieldEditor.tsx`

**PlantIdentification Components** (2 files):
- [ ] `components/PlantIdentification/FileUpload.tsx`
- [ ] `components/PlantIdentification/IdentificationResults.tsx`

**Pattern**: Define props interface, remove PropTypes
```typescript
import type { BlogPost } from '@/types';

interface BlogCardProps {
  post: BlogPost;
  showImage?: boolean;
}

function BlogCard({ post, showImage = true }: BlogCardProps) {
  return (
    <article>
      {showImage && <img src={post.featured_image} alt={post.title} />}
      <h2>{post.title}</h2>
    </article>
  );
}

// ⚠️ KEEP PropTypes for now (remove in Phase 8)
BlogCard.propTypes = { /* ... */ };
```

**After conversion**:
- [ ] All components have props interfaces
- [ ] PropTypes still present (defense in depth)
- [ ] `npx tsc --noEmit` passes
- [ ] `npm run test` - same pass rate as baseline
- [ ] Commit: `git commit -m "feat: migrate UI components to TypeScript (Phase 6)"`

---

## Phase 7: Pages (18 files)

**Strategy**: Convert route components last

**Auth Pages** (2 files):
- [ ] `pages/auth/LoginPage.tsx`
- [ ] `pages/auth/SignupPage.tsx`

**Simple Pages** (4 files):
- [ ] `pages/HomePage.tsx`
- [ ] `pages/IdentifyPage.tsx`
- [ ] `pages/ProfilePage.tsx`
- [ ] `pages/SettingsPage.tsx`

**Blog Pages** (4 files):
- [ ] `pages/BlogPage.tsx`
- [ ] `pages/BlogListPage.tsx`
- [ ] `pages/BlogDetailPage.tsx`
- [ ] `pages/BlogPreview.tsx`

**Forum Pages** (5 files):
- [ ] `pages/ForumPage.tsx`
- [ ] `pages/forum/CategoryListPage.tsx`
- [ ] `pages/forum/ThreadListPage.tsx`
- [ ] `pages/forum/ThreadDetailPage.tsx`
- [ ] `pages/forum/SearchPage.tsx`

**Diagnosis Pages** (2 files):
- [ ] `pages/diagnosis/DiagnosisListPage.tsx`
- [ ] `pages/diagnosis/DiagnosisDetailPage.tsx`

**App Entry** (2 files):
- [ ] `App.tsx`
- [ ] `main.tsx`

**Config** (1 file):
- [ ] `config/sentry.ts`

**Pattern**: Type route params
```typescript
import type { Thread } from '@/types';

export default function ThreadDetailPage() {
  const { threadId } = useParams<{ threadId: string }>();
  const [thread, setThread] = useState<Thread | null>(null);
  // ...
}
```

**After conversion**:
- [ ] All pages have proper type annotations
- [ ] Route params typed with useParams<T>
- [ ] `npx tsc --noEmit` passes
- [ ] `npm run test` - same pass rate as baseline
- [ ] Commit: `git commit -m "feat: migrate pages to TypeScript (Phase 7)"`

---

## Phase 8: Error Resolution

**Critical Fixes**:

- [ ] **React Router v7 Import Fix**
  ```bash
  # Global find-replace
  find src -type f \( -name "*.ts" -o -name "*.tsx" \) \
    -exec sed -i '' "s/from 'react-router'/from 'react-router-dom'/g" {} +

  # Verify
  grep -r "from 'react-router'" src/
  # Should return nothing
  ```

- [ ] **Memory Leak Prevention** (useRef for timers)
  ```typescript
  // Find all useState timers
  grep -r "useState.*Timeout" src/

  // Convert to useRef
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Add cleanup
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);
  ```

- [ ] **Logger Type Safety**
  ```typescript
  // Find raw error logging
  grep -r "logger\.error.*error)" src/

  // Wrap in context object
  logger.error('[PREFIX]', { error });
  ```

- [ ] **Readonly Type Compatibility**
  ```typescript
  // Update interfaces to accept readonly arrays
  interface Config {
    ALLOWED_TAGS: readonly string[] | string[];
  }
  ```

**Verification**:
- [ ] `npx tsc --noEmit` - ZERO errors
- [ ] `npm run test` - same pass rate as baseline
- [ ] `npm run build` - succeeds
- [ ] Manual testing - all routes render without errors
- [ ] Commit: `git commit -m "fix: resolve TypeScript compilation errors (Phase 8)"`

---

## Phase 9: Final Cleanup

**Remove PropTypes**:
- [ ] Verify 100% TypeScript conversion
  ```bash
  find src -name "*.js" -o -name "*.jsx"
  # Should return NOTHING
  ```

- [ ] Verify zero TypeScript errors
  ```bash
  npx tsc --noEmit
  # Exit code 0 (success)
  ```

- [ ] Run full test suite
  ```bash
  npm run test
  # Should match baseline pass rate
  ```

- [ ] Set `allowJs: false` in tsconfig.json
  ```json
  {
    "compilerOptions": {
      "allowJs": false  // ← Enforce TypeScript only
    }
  }
  ```

- [ ] Remove prop-types package
  ```bash
  npm uninstall prop-types
  ```

- [ ] Remove PropTypes imports/definitions
  ```bash
  # Remove imports
  find src -type f \( -name "*.ts" -o -name "*.tsx" \) \
    -exec sed -i '' "/import.*PropTypes.*from 'prop-types'/d" {} +

  # Verify
  grep -r "PropTypes" src/
  # Should return nothing
  ```

- [ ] Final verification
  ```bash
  npx tsc --noEmit   # Zero errors
  npm run test       # Tests pass
  npm run build      # Build succeeds
  npm run dev        # Dev server starts
  ```

- [ ] Commit cleanup
  ```bash
  git add .
  git commit -m "chore: remove PropTypes after TypeScript migration (Phase 9)"
  ```

---

## Documentation

- [ ] Create `TYPESCRIPT_MIGRATION_COMPLETE.md`
  - Migration metrics (files, lines, duration)
  - Key achievements
  - Lessons learned
  - Future: strict mode enablement plan

- [ ] Update `CLAUDE.md` or project README
  - Document TypeScript migration complete
  - Update development setup instructions
  - Add TypeScript-specific patterns

- [ ] Create migration lessons learned doc (optional)
  - Document challenges overcome
  - Best practices discovered
  - Anti-patterns to avoid

---

## Deployment Readiness

- [ ] TypeScript compilation check passes in CI/CD
- [ ] Test suite passes in CI/CD
- [ ] Build succeeds in CI/CD
- [ ] Production bundle size acceptable (<2% increase)
- [ ] Code review completed
- [ ] Merge to main approved

---

## Future: Strict Mode Enablement

**NOT part of initial migration - separate issue**

- [ ] Create issue for strict mode enablement
- [ ] Plan incremental approach:
  1. Enable `noImplicitAny: true` (1-2 weeks)
  2. Enable `strictNullChecks: true` (2-3 weeks)
  3. Enable full `strict: true` (1-2 weeks)
- [ ] Remove remaining `any` types (~10-15 occurrences)
- [ ] Add stricter event handler types
- [ ] Update documentation with strict mode patterns

---

## Common Issues & Solutions

### Issue: TypeScript errors in JS files during migration
**Solution**: Ensure `allowJs: true` and `checkJs: false` in tsconfig.json

### Issue: Tests fail after converting files
**Solution**: Run tests after every 5-10 file conversions to isolate failures

### Issue: Memory leaks from debounce timers
**Solution**: Use `useRef` instead of `useState` for timers, add cleanup in useEffect

### Issue: React Router context errors
**Solution**: Change imports from `'react-router'` to `'react-router-dom'`

### Issue: Logger type errors with Error objects
**Solution**: Wrap errors in context objects: `logger.error('[PREFIX]', { error })`

### Issue: Readonly type incompatibility
**Solution**: Accept both: `readonly T[] | T[]` in interfaces

### Issue: Runtime errors after removing PropTypes
**Solution**: Only remove PropTypes after 100% TypeScript conversion and `allowJs: false`

---

## Success Metrics

**Migration Complete When**:
- ✅ Zero `.js` or `.jsx` files in `src/`
- ✅ `npx tsc --noEmit` exits with code 0
- ✅ `allowJs: false` in tsconfig.json
- ✅ PropTypes package removed
- ✅ Test pass rate matches baseline (no regressions)
- ✅ Build succeeds
- ✅ Production deployment successful

**Example Success**:
- Files Converted: 50+ files
- Lines Migrated: ~10,000 lines
- TypeScript Errors: 0
- Test Regressions: 0
- Downtime: 0 hours
- Code Review Grade: A (95/100)

---

**Full Documentation**: `/web/TYPESCRIPT_MIGRATION_PATTERNS_CODIFIED.md`
**Issue Reference**: #134
**Last Updated**: November 9, 2025
