# TypeScript Migration Completion Guide

## Migration Status Summary

### ✅ Completed (Phases 1-6.3)
- **Phase 1-5**: Foundation, Utilities, Types, Services, Contexts
- **Phase 6.1**: Basic UI components (Button, Input, LoadingSpinner)
- **Phase 6.2**: Card components (CategoryCard, PostCard, ThreadCard, BlogCard)
- **Phase 6.3**: Layout components (Header, Footer, UserMenu, RootLayout, ProtectedLayout)

### 🔄 Remaining Work

#### Phase 6.4-6.6: Complex Components (11 files)
- `components/forum/TipTapEditor.jsx` → `.tsx`
- `components/forum/ImageUploadWidget.jsx` → `.tsx`
- `components/StreamFieldRenderer.jsx` → `.tsx`
- `components/ErrorBoundary.jsx` → `.tsx`
- `components/diagnosis/DiagnosisCard.jsx` → `.tsx`
- `components/diagnosis/ReminderManager.jsx` → `.tsx`
- `components/diagnosis/SaveDiagnosisModal.jsx` → `.tsx`
- `components/diagnosis/StreamFieldEditor.jsx` → `.tsx`
- `components/PlantIdentification/FileUpload.jsx` → `.tsx`
- `components/PlantIdentification/IdentificationResults.jsx` → `.tsx`
- `contexts/RequestContext.jsx` → `.tsx` (if not done)

#### Phase 7: Pages (18 files)
**Auth Pages (2):**
- `pages/auth/LoginPage.jsx` → `.tsx`
- `pages/auth/SignupPage.jsx` → `.tsx`

**Simple Pages (4):**
- `pages/HomePage.jsx` → `.tsx`
- `pages/IdentifyPage.jsx` → `.tsx`
- `pages/ProfilePage.jsx` → `.tsx`
- `pages/SettingsPage.jsx` → `.tsx`

**Blog Pages (4):**
- `pages/BlogPage.jsx` → `.tsx`
- `pages/BlogListPage.jsx` → `.tsx`
- `pages/BlogDetailPage.jsx` → `.tsx`
- `pages/BlogPreview.jsx` → `.tsx`

**Forum Pages (5):**
- `pages/ForumPage.jsx` → `.tsx`
- `pages/forum/CategoryListPage.jsx` → `.tsx`
- `pages/forum/ThreadListPage.jsx` → `.tsx`
- `pages/forum/ThreadDetailPage.jsx` → `.tsx`
- `pages/forum/SearchPage.jsx` → `.tsx`

**Diagnosis Pages (2):**
- `pages/diagnosis/DiagnosisListPage.jsx` → `.tsx`
- `pages/diagnosis/DiagnosisDetailPage.jsx` → `.tsx`

**Miscellaneous Pages (1):**
- `App.jsx` → `App.tsx`
- `main.jsx` → `main.tsx`

## Conversion Pattern

For each JSX file, follow this pattern:

### 1. Remove PropTypes Import
```typescript
// REMOVE
import PropTypes from 'prop-types';
```

### 2. Add Type Imports
```typescript
// ADD (use existing types from src/types/)
import type { Post, Thread, Category, User } from '@/types';
```

### 3. Convert Props to Interface
```typescript
// BEFORE (JSX)
function MyComponent({ title, count, onSave }) {
  // ...
}

MyComponent.propTypes = {
  title: PropTypes.string.isRequired,
  count: PropTypes.number,
  onSave: PropTypes.func,
};

// AFTER (TSX)
interface MyComponentProps {
  title: string;
  count?: number;
  onSave?: (data: SomeType) => void;
}

function MyComponent({ title, count, onSave }: MyComponentProps) {
  // ...
}
```

### 4. Convert Event Handlers
```typescript
// BEFORE
const handleClick = (event) => {
  // ...
};

// AFTER
const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
  // ...
};

// Common event types:
// - React.MouseEvent<HTMLButtonElement>
// - React.ChangeEvent<HTMLInputElement>
// - React.FormEvent<HTMLFormElement>
// - React.KeyboardEvent<HTMLInputElement>
```

### 5. Convert State with Types
```typescript
// BEFORE
const [data, setData] = useState(null);
const [items, setItems] = useState([]);

// AFTER
const [data, setData] = useState<MyDataType | null>(null);
const [items, setItems] = useState<ItemType[]>([]);
```

### 6. Convert Refs
```typescript
// BEFORE
const inputRef = useRef(null);

// AFTER
const inputRef = useRef<HTMLInputElement>(null);
```

### 7. Update Router Imports
```typescript
// BEFORE
import { Link, useNavigate } from 'react-router-dom';

// AFTER
import { Link, useNavigate } from 'react-router';
```

### 8. Remove PropTypes Declaration
```typescript
// REMOVE entire block
MyComponent.propTypes = {
  // ...
};
```

## Example: Complete Conversion

### Before (JSX)
```jsx
import { useState } from 'react';
import PropTypes from 'prop-types';

function PostEditor({ post, onSave, onCancel }) {
  const [content, setContent] = useState(post?.content || '');

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({ ...post, content });
  };

  return (
    <form onSubmit={handleSubmit}>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
      />
      <button type="submit">Save</button>
      <button type="button" onClick={onCancel}>Cancel</button>
    </form>
  );
}

PostEditor.propTypes = {
  post: PropTypes.shape({
    id: PropTypes.string,
    content: PropTypes.string,
  }),
  onSave: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
};

export default PostEditor;
```

### After (TSX)
```typescript
import { useState } from 'react';
import type { Post } from '@/types';

interface PostEditorProps {
  post?: Partial<Post>;
  onSave: (post: Partial<Post>) => void;
  onCancel: () => void;
}

function PostEditor({ post, onSave, onCancel }: PostEditorProps) {
  const [content, setContent] = useState(post?.content || '');

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    onSave({ ...post, content });
  };

  return (
    <form onSubmit={handleSubmit}>
      <textarea
        value={content}
        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setContent(e.target.value)}
      />
      <button type="submit">Save</button>
      <button type="button" onClick={onCancel}>Cancel</button>
    </form>
  );
}

export default PostEditor;
```

## Key Type Interfaces Available

All types are exported from `@/types`:

```typescript
// Authentication
import type { User, LoginCredentials, SignupData, AuthResponse } from '@/types';

// Forum
import type { Category, Thread, Post, Attachment, CreateThreadData, CreatePostData } from '@/types';

// Blog
import type { BlogPost, StreamFieldBlock } from '@/types';

// Plant ID
import type { PlantIdentificationResult, Collection, UserPlant } from '@/types';

// Diagnosis
import type { DiagnosisCard, DiagnosisReminder, HealthAssessment } from '@/types';

// API
import type { ApiResponse, ApiError, DRFPaginatedResponse } from '@/types';
```

## Common Type Additions Needed

You may need to extend existing types for specific components:

```typescript
// For components with additional props beyond the core type
interface ThreadCardProps extends Thread {
  compact?: boolean;
  onEdit?: (thread: Thread) => void;
}

// For partial data scenarios
interface CreatePostFormProps {
  thread: string;
  initialData?: Partial<Post>;
}

// For callback props
interface PostListProps {
  posts: Post[];
  onPostClick?: (post: Post) => void;
  onPostDelete?: (postId: string) => Promise<void>;
}
```

## Batch Conversion Script

Use this bash script to help with the conversion:

```bash
#!/bin/bash

# Find all remaining JSX files (excluding tests)
find src -name "*.jsx" -type f ! -name "*.test.jsx" | while read file; do
  # Get the new filename
  newfile="${file%.jsx}.tsx"

  echo "Converting: $file -> $newfile"

  # Copy to new file
  cp "$file" "$newfile"

  # Remove old file
  # rm "$file"  # Uncomment when ready
done

echo "Conversion complete! Remember to:"
echo "1. Add type interfaces for props"
echo "2. Remove PropTypes imports and declarations"
echo "3. Update imports from 'react-router-dom' to 'react-router'"
echo "4. Run: npm run test"
```

## Phase 8: Enable Strict Mode

After all conversions, enable strict TypeScript checking:

### Update `tsconfig.json`:
```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "strictFunctionTypes": true,
    "strictBindCallApply": true,
    "strictPropertyInitialization": true,
    "noImplicitThis": true,
    "alwaysStrict": true,
    "allowJs": false  // Disable JS files
  }
}
```

### Fix Type Errors:
1. Run `npm run build` to see all errors
2. Fix errors one by one:
   - Add missing type annotations
   - Handle null/undefined cases with optional chaining
   - Add proper return types to functions
   - Fix `any` types with specific types

## Phase 9: Final Cleanup

1. **Remove all PropTypes**:
   ```bash
   # Search for remaining PropTypes usage
   grep -r "PropTypes" src --include="*.tsx"
   ```

2. **Remove `any` types**:
   ```bash
   # Find any usage
   grep -r ": any" src --include="*.tsx"
   grep -r "<any>" src --include="*.tsx"
   ```

3. **Fix import paths**:
   ```bash
   # Update react-router-dom to react-router
   find src -name "*.tsx" -exec sed -i '' 's/from '\''react-router-dom'\''/from '\''react-router'\''/g' {} +
   ```

4. **Run full test suite**:
   ```bash
   npm run test
   npm run test:e2e
   npm run lint
   ```

5. **Verify build**:
   ```bash
   npm run build
   ```

## Common Issues and Solutions

### Issue: "Cannot find module '@/types'"
**Solution**: Ensure `tsconfig.json` has path mapping:
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

### Issue: "Type 'null' is not assignable to type 'X'"
**Solution**: Use optional chaining and null checks:
```typescript
// BEFORE
const name = user.name;

// AFTER
const name = user?.name ?? 'Unknown';
```

### Issue: "Property 'X' does not exist on type 'Y'"
**Solution**: Extend the type or use optional properties:
```typescript
interface ExtendedUser extends User {
  customField?: string;
}
```

### Issue: Test files fail with "react-router" import
**Solution**: Update test utilities to import from 'react-router':
```typescript
// In test files
import { MemoryRouter } from 'react-router';
```

## Testing Strategy

1. **Component-by-component**: After converting each component, run its tests
2. **Page-by-page**: After converting each page, test navigation
3. **Full suite**: Run complete test suite after all conversions
4. **E2E tests**: Run Playwright tests to ensure app works end-to-end

## Verification Checklist

- [ ] All `.jsx` files converted to `.tsx` (excluding tests)
- [ ] All PropTypes removed
- [ ] All type interfaces added
- [ ] No `any` types remain
- [ ] All imports updated to 'react-router'
- [ ] `tsconfig.json` strict mode enabled
- [ ] `allowJs: false` in tsconfig
- [ ] All tests passing (npm run test)
- [ ] E2E tests passing (npm run test:e2e)
- [ ] Lint passing (npm run lint)
- [ ] Build successful (npm run build)

## Estimated Time

- **Phase 6.4-6.6** (Complex Components): 2-3 hours
- **Phase 7** (Pages): 3-4 hours
- **Phase 8** (Strict Mode): 2-3 hours
- **Phase 9** (Final Cleanup): 1-2 hours

**Total**: 8-12 hours for completion

## Next Steps

1. Start with simpler pages (HomePage, ProfilePage, SettingsPage)
2. Move to form-heavy pages (LoginPage, SignupPage)
3. Tackle complex pages (ThreadDetailPage, DiagnosisDetailPage)
4. Convert remaining components
5. Enable strict mode and fix errors
6. Final cleanup and verification

Good luck! The foundation is solid, and the remaining work is systematic.
