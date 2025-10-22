# Component Library

Complete guide to all components in the Plant ID Community web frontend.

## Component Organization

Components are organized by feature in feature-specific folders:

```
src/components/
└── PlantIdentification/
    ├── FileUpload.jsx
    └── IdentificationResults.jsx
```

**Future Structure** (as app grows):
```
src/components/
├── PlantIdentification/    # Plant ID feature
├── Common/                 # Shared components
├── Auth/                   # Authentication
└── Collection/             # Plant collection
```

## Component Index

| Component | Location | Purpose |
|-----------|----------|---------|
| [FileUpload](#fileupload) | `PlantIdentification/FileUpload.jsx` | Image upload with drag-drop and compression |
| [IdentificationResults](#identificationresults) | `PlantIdentification/IdentificationResults.jsx` | Display AI identification results |

## Pages

Pages are route-level components in `src/pages/`:

| Page | Path | Purpose |
|------|------|---------|
| [HomePage](#homepage) | `/` | Landing page with hero and features |
| [IdentifyPage](#identifypage) | `/identify` | Plant identification workflow |
| [BlogPage](#blogpage) | `/blog` | Blog posts (placeholder) |
| [ForumPage](#forumpage) | `/forum` | Community forum (placeholder) |

---

## PlantIdentification Components

### FileUpload

Image upload component with drag-and-drop, preview, and automatic compression.

**Location:** `src/components/PlantIdentification/FileUpload.jsx`

#### Props

```typescript
interface FileUploadProps {
  onFileSelect: (file: File | null) => void  // Callback when file selected
  selectedFile: File | null                   // Currently selected file
}
```

#### Usage

```javascript
import FileUpload from '../components/PlantIdentification/FileUpload'

function MyComponent() {
  const [file, setFile] = useState(null)

  return (
    <FileUpload
      onFileSelect={setFile}
      selectedFile={file}
    />
  )
}
```

#### Features

- **Drag & Drop**: Drag image files onto upload area
- **Click to Upload**: Click to open file picker
- **File Validation**: Accepts only images (jpg, png, gif, webp)
- **Size Validation**: Warns for files > 10MB
- **Auto-Compression**: Compresses files > 2MB automatically
- **Image Preview**: Shows thumbnail after selection
- **Compression Stats**: Displays before/after file sizes
- **Accessibility**: Full keyboard navigation and ARIA labels

#### State Management

**Internal State:**
```javascript
const [isDragOver, setIsDragOver] = useState(false)
const [previewUrl, setPreviewUrl] = useState(null)
const [compressionStats, setCompressionStats] = useState(null)
const [error, setError] = useState(null)
```

**Compression Flow:**
```
File Selected (10MB)
      │
      ▼
Size > 2MB? ──No──> Use Original
      │
     Yes
      ▼
Compress Image
      │
      ▼
Show Stats (10MB → 800KB)
      │
      ▼
Call onFileSelect(compressedFile)
```

#### Example: Compression Stats

```javascript
{
  original: { size: 10485760, formatted: "10.00 MB" },
  compressed: { size: 838860, formatted: "819.20 KB" },
  reduction: 92.0  // Percentage
}
```

#### Styling

**Classes Used:**
- `border-dashed border-2` - Drag-drop border
- `bg-green-50` - Light green background on drag-over
- `rounded-xl` - Rounded corners (12px)
- `transition-all duration-200` - Smooth state transitions

#### Cleanup

**Memory Management:**
```javascript
useEffect(() => {
  return () => {
    // Revoke ObjectURL on unmount
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
    }
  }
}, [previewUrl])
```

#### Error Handling

**Validation Errors:**
- Invalid file type → "Please select an image file"
- File too large → "File size should be less than 10MB"
- Compression failed → Falls back to original file

---

### IdentificationResults

Displays plant identification results from the AI API.

**Location:** `src/components/PlantIdentification/IdentificationResults.jsx`

#### Props

```typescript
interface IdentificationResultsProps {
  results: {
    plant_name: string
    scientific_name: string
    confidence: number
    suggestions: Array<{
      plant_name: string
      scientific_name: string
      probability: number
      common_names: string[]
      description?: string
      similar_images?: string[]
    }>
    disease_detection?: {
      is_healthy: boolean
      disease_name?: string
      description?: string
    }
  } | null
  loading: boolean
  error: string | null
}
```

#### Usage

```javascript
import IdentificationResults from '../components/PlantIdentification/IdentificationResults'

function MyComponent() {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  return (
    <IdentificationResults
      results={results}
      loading={loading}
      error={error}
    />
  )
}
```

#### Features

- **Loading State**: Animated spinner with message
- **Error Display**: Red alert box with error message
- **Primary Result**: Large display of top match
- **Confidence Badge**: Color-coded confidence percentage
- **Disease Detection**: Warning if plant is unhealthy
- **Alternative Suggestions**: List of other possible matches
- **Similar Images**: Grid of visually similar plants
- **Responsive Layout**: Adapts to mobile/tablet/desktop

#### Display States

1. **Loading**
   ```
   [Spinner] Identifying plant...
   ```

2. **Error**
   ```
   ⚠️ Error message here
   ```

3. **Results**
   ```
   ┌─────────────────────────┐
   │ Monstera Deliciosa      │
   │ Monstera deliciosa      │
   │ [95% confidence]        │
   └─────────────────────────┘

   Description: ...

   Alternative Matches:
   - Pothos (85%)
   - Philodendron (78%)

   Similar Images:
   [img] [img] [img] [img]
   ```

#### Confidence Badge Colors

```javascript
const getConfidenceColor = (confidence) => {
  if (confidence >= 0.8) return 'bg-green-500'    // High confidence
  if (confidence >= 0.6) return 'bg-yellow-500'   // Medium confidence
  return 'bg-red-500'                             // Low confidence
}
```

#### Disease Detection Display

```javascript
{results.disease_detection && !results.disease_detection.is_healthy && (
  <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4">
    <div className="flex items-center">
      <AlertCircle className="text-yellow-600 mr-2" />
      <div>
        <h4 className="font-semibold">Health Issue Detected</h4>
        <p>{results.disease_detection.disease_name}</p>
      </div>
    </div>
  </div>
)}
```

#### Styling

**Classes Used:**
- `bg-white rounded-xl shadow-lg` - Card container
- `grid md:grid-cols-2 gap-4` - Responsive similar images grid
- `border-l-4 border-yellow-400` - Disease warning accent
- `text-sm text-gray-600` - Secondary text style

---

## Page Components

### HomePage

Landing page with hero section and feature showcase.

**Location:** `src/pages/HomePage.jsx`
**Route:** `/`

#### Features

- Hero section with gradient background
- Feature cards (Identify, Learn, Community)
- Call-to-action buttons
- Navigation to /identify page

#### Structure

```
┌─────────────────────────────┐
│        Hero Section         │
│  "Discover the Plant World" │
│    [Get Started Button]     │
└─────────────────────────────┘
┌─────────────────────────────┐
│       Feature Cards         │
│  [Identify] [Learn] [Share] │
└─────────────────────────────┘
```

#### Styling

- Gradient background: `bg-gradient-to-br from-green-50 to-emerald-50`
- Large hero text: `text-5xl font-bold`
- Green CTAs: `bg-green-600 hover:bg-green-700`

---

### IdentifyPage

Main plant identification workflow page.

**Location:** `src/pages/IdentifyPage.jsx`
**Route:** `/identify`

#### Features

- Integrates FileUpload and IdentificationResults
- Manages upload → API call → results flow
- Error handling and loading states
- State management for entire workflow

#### State

```javascript
const [selectedFile, setSelectedFile] = useState(null)
const [results, setResults] = useState(null)
const [loading, setLoading] = useState(false)
const [error, setError] = useState(null)
```

#### Workflow

```
1. User selects file
   └─> setSelectedFile(file)

2. User clicks "Identify Plant"
   └─> setLoading(true)
   └─> API call
       ├─> Success: setResults(data)
       └─> Error: setError(message)
   └─> setLoading(false)

3. Display results
   └─> <IdentificationResults results={results} />
```

#### Example API Integration

```javascript
const handleIdentify = async () => {
  if (!selectedFile) return

  try {
    setLoading(true)
    setError(null)

    const result = await plantIdService.identifyPlant(selectedFile)
    setResults(result)
  } catch (err) {
    setError(err.message || 'Failed to identify plant')
  } finally {
    setLoading(false)
  }
}
```

---

### BlogPage

Placeholder for future blog integration.

**Location:** `src/pages/BlogPage.jsx`
**Route:** `/blog`

#### Current State

- Placeholder component
- "Coming soon" message
- Future: Wagtail CMS integration

---

### ForumPage

Placeholder for future forum integration.

**Location:** `src/pages/ForumPage.jsx`
**Route:** `/forum`

#### Current State

- Placeholder component
- "Coming soon" message
- Future: Django Machina integration (read-only)

---

## Component Best Practices

### 1. Component Structure

```javascript
import { useState, useEffect } from 'react'
import { Icon } from 'lucide-react'

/**
 * Component description
 * @param {Object} props - Component props
 * @param {string} props.prop1 - Prop description
 */
export default function MyComponent({ prop1, prop2 }) {
  // State
  const [state, setState] = useState(null)

  // Effects
  useEffect(() => {
    // Effect logic
    return () => {
      // Cleanup
    }
  }, [dependencies])

  // Handlers
  const handleClick = () => {
    // Handler logic
  }

  // Render
  return (
    <div className="...">
      {/* Component content */}
    </div>
  )
}
```

### 2. Props Destructuring

```javascript
// ✅ Good: Destructure props in function signature
function MyComponent({ name, age, onClick }) {
  return <div onClick={onClick}>{name}</div>
}

// ❌ Avoid: Using props object
function MyComponent(props) {
  return <div onClick={props.onClick}>{props.name}</div>
}
```

### 3. Conditional Rendering

```javascript
// ✅ Good: Use && for simple conditions
{loading && <Spinner />}

// ✅ Good: Use ternary for if/else
{error ? <ErrorMessage /> : <SuccessMessage />}

// ✅ Good: Extract complex conditions
const showResults = results && !loading && !error
{showResults && <Results data={results} />}
```

### 4. State Updates

```javascript
// ✅ Good: Functional updates for dependent state
setCount(prevCount => prevCount + 1)

// ✅ Good: Separate setState calls
setLoading(true)
setError(null)

// ❌ Avoid: Batching unrelated state
setState({ loading: true, error: null, data: null })
```

### 5. Event Handlers

```javascript
// ✅ Good: Arrow functions for handlers
const handleClick = () => {
  // Handler logic
}

// ✅ Good: Pass parameters via closures
const handleDelete = (id) => () => {
  deleteItem(id)
}

// ❌ Avoid: Inline arrow functions in JSX (creates new function each render)
<button onClick={() => handleClick(id)}>Click</button>

// ✅ Better: Use closure
<button onClick={handleClick(id)}>Click</button>
```

### 6. Cleanup

```javascript
// ✅ Good: Always cleanup side effects
useEffect(() => {
  const url = URL.createObjectURL(file)
  setPreviewUrl(url)

  return () => {
    URL.revokeObjectURL(url)  // Cleanup
  }
}, [file])
```

## Styling Guidelines

### Tailwind Class Order

```javascript
// Recommended order:
className="
  layout-classes        // grid, flex, block
  sizing-classes        // w-full, h-screen
  spacing-classes       // p-4, m-2, gap-4
  typography-classes    // text-lg, font-bold
  color-classes         // bg-white, text-gray-600
  border-classes        // border, rounded-xl
  effects-classes       // shadow-lg, hover:bg-green-700
  transition-classes    // transition-colors, duration-200
"
```

### Responsive Design

```javascript
// Mobile-first approach
className="
  grid                 // Mobile: single column
  md:grid-cols-2       // Tablet: 2 columns
  lg:grid-cols-3       // Desktop: 3 columns
"
```

### Common Patterns

```javascript
// Card
className="bg-white rounded-xl shadow-lg p-6"

// Button Primary
className="bg-green-600 text-white px-6 py-3 rounded-lg hover:bg-green-700 transition-colors"

// Button Secondary
className="border-2 border-green-600 text-green-600 px-6 py-3 rounded-lg hover:bg-green-50 transition-colors"

// Input
className="w-full px-4 py-2 border-2 border-gray-300 rounded-lg focus:border-green-600 focus:outline-none"

// Error Message
className="bg-red-50 border-l-4 border-red-400 p-4 text-red-700"
```

## Future Components

### Planned Components

1. **Authentication**
   - `LoginForm`
   - `SignupForm`
   - `UserProfile`

2. **Plant Collection**
   - `PlantCard`
   - `PlantGrid`
   - `PlantDetails`

3. **Common**
   - `Navigation`
   - `Footer`
   - `ErrorBoundary`
   - `LoadingSkeleton`

4. **History**
   - `HistoryList`
   - `HistoryItem`

## Summary

The component library is intentionally minimal for the current scope. As the application grows, follow these principles:

1. **Feature-based organization** - Group related components
2. **Single responsibility** - Each component does one thing well
3. **Composition** - Build complex UIs from simple components
4. **Accessibility** - ARIA labels, keyboard navigation
5. **Performance** - Cleanup, memoization when needed
