# Getting Started - Web Frontend

Complete setup guide for new developers joining the Plant ID Community web frontend team.

## Prerequisites

### Required Software

- **Node.js** 18.0.0 or higher
  ```bash
  node --version  # Should be v18.x.x or higher
  ```

- **npm** 9.0.0 or higher
  ```bash
  npm --version   # Should be 9.x.x or higher
  ```

- **Git** (for cloning repository)
  ```bash
  git --version
  ```

### Recommended Tools

- **VS Code** with extensions:
  - ESLint
  - Tailwind CSS IntelliSense
  - ES7+ React/Redux/React-Native snippets
  - Auto Rename Tag
  - Prettier (optional)

- **Browser DevTools**:
  - React Developer Tools (Chrome/Firefox)
  - Redux DevTools (for future state management)

## Initial Setup

### 1. Clone Repository

```bash
# Clone the repository
git clone <repository-url>
cd plant_id_community

# Navigate to web frontend
cd web
```

### 2. Install Dependencies

```bash
# Install all npm packages
npm install

# Verify installation
npm list --depth=0
```

**Expected output:**
```
plant-id-web@0.0.0
├── @vitejs/plugin-react@latest
├── axios@1.12.2
├── lucide-react@0.546.0
├── react@19.1.1
├── react-dom@19.1.1
├── react-router-dom@7.9.4
├── tailwindcss@4.1.15
└── vite@7.1.7
```

### 3. Environment Configuration

Create `.env` file in the `web/` directory:

```bash
# Copy example environment file
cp .env.example .env

# Or create manually
touch .env
```

**Edit `.env` with your configuration:**

```bash
# Required: Backend API URL
VITE_API_URL=http://localhost:8000

# Optional: Analytics (future)
# VITE_GA_MEASUREMENT_ID=G-XXXXXXXXXX

# Optional: Error tracking (future)
# VITE_SENTRY_DSN=https://...

# Optional: Debug mode
# VITE_DEBUG=true
```

**Environment Variables Explained:**

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_URL` | Yes | `http://localhost:8000` | Django backend URL |
| `VITE_GA_MEASUREMENT_ID` | No | - | Google Analytics ID (future) |
| `VITE_SENTRY_DSN` | No | - | Sentry error tracking URL (future) |
| `VITE_DEBUG` | No | `false` | Enable debug logging |

**Important Notes:**
- All environment variables MUST be prefixed with `VITE_`
- Restart dev server after changing `.env`
- Never commit `.env` to git (already in `.gitignore`)
- Use `.env.example` for documentation

### 4. Start Backend Server

The web frontend requires the Django backend to be running:

```bash
# In a separate terminal, navigate to backend
cd ../backend

# Activate virtual environment
source venv/bin/activate

# Start Django server (port 8000)
python manage.py runserver

# Verify backend is running
curl http://localhost:8000/api/plant-identification/identify/health/
```

**Expected Response:**
```json
{
  "status": "healthy",
  "plant_id_available": true,
  "plantnet_available": true
}
```

### 5. Start Development Server

```bash
# In web/ directory
npm run dev
```

**Expected Output:**
```
  VITE v7.1.7  ready in 423 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
  ➜  press h + enter to show help
```

### 6. Verify Setup

Open browser to `http://localhost:5173`

**Checklist:**
- [ ] Landing page loads without errors
- [ ] Navigation works (Home, Identify, Blog, Forum)
- [ ] No console errors
- [ ] Tailwind styles applied (green primary color)
- [ ] React DevTools shows component tree

## Development Workflow

### Daily Development

```bash
# 1. Pull latest changes
git pull origin main

# 2. Install any new dependencies
npm install

# 3. Start backend (separate terminal)
cd backend && source venv/bin/activate
python manage.py runserver

# 4. Start frontend dev server
cd web
npm run dev

# 5. Open browser to http://localhost:5173
```

### Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Edit components in `src/`
   - Add new pages in `src/pages/`
   - Update services in `src/services/`

3. **Test locally**
   - Verify in browser at `localhost:5173`
   - Check console for errors
   - Test responsive design (mobile/tablet/desktop)

4. **Lint your code**
   ```bash
   npm run lint
   ```

5. **Commit changes**
   ```bash
   git add .
   git commit -m "feat: your feature description"
   ```

6. **Push to remote**
   ```bash
   git push origin feature/your-feature-name
   ```

## Available Scripts

### Development

```bash
# Start development server with HMR
npm run dev

# Development server will run on http://localhost:5173
# Changes auto-reload in browser
```

### Production Build

```bash
# Create optimized production build
npm run build

# Output: dist/ directory
```

**Build Output:**
```
dist/
├── index.html              # Entry HTML file
├── assets/
│   ├── index-[hash].js     # Main JavaScript bundle
│   ├── vendor-[hash].js    # Dependencies (React, etc.)
│   └── index-[hash].css    # Tailwind CSS
└── vite.svg                # Favicon
```

### Preview Production Build

```bash
# Build first
npm run build

# Preview production build locally
npm run preview

# Opens at http://localhost:4173
```

### Code Quality

```bash
# Run ESLint
npm run lint

# Fix auto-fixable issues
npm run lint -- --fix
```

## Project Structure

```
web/
├── docs/                       # Documentation
│   ├── README.md
│   ├── Architecture.md
│   └── ...
├── public/                     # Static assets
│   └── vite.svg
├── src/
│   ├── pages/                  # Route components
│   │   ├── HomePage.jsx
│   │   ├── IdentifyPage.jsx
│   │   ├── BlogPage.jsx
│   │   └── ForumPage.jsx
│   ├── components/             # Reusable components
│   │   └── PlantIdentification/
│   │       ├── FileUpload.jsx
│   │       └── IdentificationResults.jsx
│   ├── services/               # API clients
│   │   └── plantIdService.js
│   ├── utils/                  # Utility functions
│   │   └── imageCompression.js
│   ├── assets/                 # Images, fonts, etc.
│   ├── App.jsx                 # Router setup
│   ├── main.jsx                # React entry point
│   └── index.css               # Tailwind imports
├── .env                        # Environment variables (git-ignored)
├── .env.example                # Example environment config
├── .gitignore                  # Git ignore rules
├── eslint.config.js            # ESLint configuration
├── index.html                  # HTML template
├── package.json                # Dependencies and scripts
├── tailwind.config.js          # Tailwind theme
├── vite.config.js              # Vite configuration
└── README.md                   # Project README
```

## Common Tasks

### Adding a New Page

1. **Create page component**
   ```bash
   touch src/pages/MyPage.jsx
   ```

2. **Implement component**
   ```javascript
   // src/pages/MyPage.jsx
   export default function MyPage() {
     return (
       <div className="container mx-auto px-4 py-8">
         <h1 className="text-3xl font-bold">My Page</h1>
       </div>
     )
   }
   ```

3. **Add route**
   ```javascript
   // src/App.jsx
   import MyPage from './pages/MyPage'

   <Routes>
     {/* ... existing routes */}
     <Route path="/my-page" element={<MyPage />} />
   </Routes>
   ```

4. **Add navigation link**
   ```javascript
   // src/components/Navigation.jsx (or HomePage.jsx)
   import { Link } from 'react-router-dom'

   <Link to="/my-page">My Page</Link>
   ```

### Adding a New Component

1. **Create component file**
   ```bash
   mkdir -p src/components/MyFeature
   touch src/components/MyFeature/MyComponent.jsx
   ```

2. **Implement component**
   ```javascript
   // src/components/MyFeature/MyComponent.jsx
   export default function MyComponent({ prop1, prop2 }) {
     return (
       <div className="bg-white p-4 rounded-lg shadow">
         {/* Component content */}
       </div>
     )
   }
   ```

3. **Import and use**
   ```javascript
   // src/pages/SomePage.jsx
   import MyComponent from '../components/MyFeature/MyComponent'

   <MyComponent prop1="value" prop2={42} />
   ```

### Adding a New API Endpoint

1. **Add method to service**
   ```javascript
   // src/services/plantIdService.js
   export const plantIdService = {
     // ... existing methods

     myNewEndpoint: async (data) => {
       try {
         const response = await axios.post(
           `${API_BASE_URL}/api/my-endpoint/`,
           data
         )
         return response.data
       } catch (error) {
         throw new Error(
           error.response?.data?.error || 'Request failed'
         )
       }
     }
   }
   ```

2. **Use in component**
   ```javascript
   import { plantIdService } from '../services/plantIdService'

   const handleSubmit = async () => {
     try {
       setLoading(true)
       const result = await plantIdService.myNewEndpoint(data)
       // Handle success
     } catch (error) {
       setError(error.message)
     } finally {
       setLoading(false)
     }
   }
   ```

### Adding a Utility Function

1. **Create utility file**
   ```bash
   touch src/utils/myUtility.js
   ```

2. **Implement utility**
   ```javascript
   // src/utils/myUtility.js

   /**
    * Description of what this function does
    * @param {string} input - Input parameter
    * @returns {string} Output value
    */
   export function myUtility(input) {
     // Implementation
     return output
   }
   ```

3. **Use in components**
   ```javascript
   import { myUtility } from '../utils/myUtility'

   const result = myUtility(input)
   ```

## Troubleshooting

### Common Issues

#### 1. Port 5173 already in use

```bash
# Kill process on port 5173
npx kill-port 5173

# Or use different port
npm run dev -- --port 3000
```

#### 2. Backend connection refused

**Symptoms:**
- API calls fail with "Network Error"
- Console shows CORS errors

**Solutions:**
```bash
# Verify backend is running
curl http://localhost:8000/api/plant-identification/identify/health/

# Check .env has correct URL
cat .env | grep VITE_API_URL

# Restart dev server after changing .env
# Ctrl+C to stop, then npm run dev
```

#### 3. Styles not loading

**Symptoms:**
- Page has no styling
- Tailwind classes not applied

**Solutions:**
```bash
# Rebuild Tailwind
rm -rf node_modules/.vite
npm run dev

# Verify tailwind.config.js exists
ls -la tailwind.config.js

# Check content paths in tailwind.config.js
```

#### 4. Module not found errors

**Symptoms:**
- `Error: Cannot find module 'some-package'`

**Solutions:**
```bash
# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Or install specific package
npm install some-package
```

#### 5. ESLint errors

**Symptoms:**
- Red squiggly lines in VS Code
- Lint command fails

**Solutions:**
```bash
# Auto-fix issues
npm run lint -- --fix

# Update ESLint config if needed
# Edit eslint.config.js
```

### Getting Help

1. **Check documentation**
   - [Architecture.md](./Architecture.md)
   - [Components.md](./Components.md)
   - [API-Integration.md](./API-Integration.md)

2. **Check console**
   - Browser DevTools → Console tab
   - Look for error messages

3. **Check network requests**
   - Browser DevTools → Network tab
   - Verify API calls to backend

4. **Ask the team**
   - Create GitHub issue
   - Ask in team chat

## Next Steps

Now that you're set up, check out:

- **[Architecture.md](./Architecture.md)** - Understand the system design
- **[Components.md](./Components.md)** - Learn about available components
- **[API-Integration.md](./API-Integration.md)** - Backend integration patterns
- **[Performance.md](./Performance.md)** - Image compression and optimization
- **[Styling.md](./Styling.md)** - Tailwind CSS conventions

Happy coding! 🌿
