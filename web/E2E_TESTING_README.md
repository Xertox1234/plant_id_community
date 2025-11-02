# Playwright E2E Testing Setup

## Overview

This project uses Playwright for end-to-end testing with **automatic server management**. Playwright will:

- ✅ Check if servers are already running
- ✅ Start servers automatically if needed
- ✅ Wait for servers to be ready before running tests
- ✅ Clean up servers after tests complete
- ✅ Prevent terminal crashes with proper configuration

## Installation

```bash
cd web

# Install Playwright
npm install -D @playwright/test

# Install browser binaries (Chromium, Firefox, WebKit)
npx playwright install
```

## How It Works

### Server Auto-Management

The `playwright.config.js` includes a `webServer` configuration that manages both:

1. **Frontend (Vite)** - Port 5174
   - Command: `npm run dev`
   - Health check: `http://localhost:5174`

2. **Backend (Django)** - Port 8000
   - Command: `cd ../backend && source venv/bin/activate && python manage.py runserver 8000`
   - Health check: `http://localhost:8000/api/v1/auth/csrf/`

### Server Readiness Flow

```
Run: npm run test:e2e
    ↓
[1] Playwright checks if servers are running
    ↓
[2a] If servers running → Reuse them (dev mode)
[2b] If not running → Start both servers
    ↓
[3] Poll health check URLs (every 500ms)
    ↓
[4] Wait for 2xx/3xx/4xx status codes
    ↓
[5] Servers ready → Execute tests
    ↓
[6] Tests complete → Stop servers (if Playwright started them)
```

## Running Tests

### Basic Commands

```bash
# Run all E2E tests (auto-starts servers)
npm run test:e2e

# Run with visible browser windows
npm run test:e2e:headed

# Run with Playwright UI (recommended for debugging)
npm run test:e2e:ui

# Run with step-by-step debugger
npm run test:e2e:debug

# Run only on Chromium
npm run test:e2e:chromium

# Run only health checks
npm run test:e2e:health
```

### Advanced Usage

```bash
# Run specific test file
npx playwright test e2e/example.spec.js

# Run tests matching pattern
npx playwright test -g "authentication"

# Run in specific browser
npx playwright test --project=firefox

# Run with multiple workers (parallel)
npx playwright test --workers=4

# Generate test report
npx playwright show-report
```

## Test Structure

```
web/
├── e2e/                          # E2E test directory
│   ├── health-check.spec.js     # Server health checks
│   └── example.spec.js          # Sample tests
├── playwright.config.js         # Playwright configuration
└── playwright-report/           # Test reports (auto-generated)
```

## Key Features

### 1. Anti-Crash Configuration

**Problem**: Playwright can crash the terminal when HTML reporter tries to open a browser in headless/CI environments.

**Solution**: Reporter configured with `open: 'never'`

```javascript
reporter: [
  ['html', { open: 'never' }],  // ✅ Never auto-open
  ['list'],                      // Console output
]
```

### 2. Server Reuse (Development)

**Problem**: Starting/stopping servers on every test run is slow.

**Solution**: Reuse existing servers in development

```javascript
webServer: {
  reuseExistingServer: !process.env.CI,  // Reuse in dev, fresh in CI
}
```

### 3. Proper Timeouts

**Problem**: Servers can take time to start, especially Django with migrations.

**Solution**: Generous timeouts with proper health checks

```javascript
webServer: {
  timeout: 120 * 1000,  // 2 minutes
  url: 'http://localhost:8000/api/v1/auth/csrf/',  // Actual endpoint
}
```

### 4. Multi-Server Support

**Problem**: Testing requires both frontend and backend.

**Solution**: Array of webServer configs

```javascript
webServer: [
  { /* Frontend config */ },
  { /* Backend config */ }
]
```

## Health Checks

### Frontend Health Check
- **URL**: `http://localhost:5174`
- **Method**: HEAD/GET request
- **Success**: Any 2xx/3xx status code
- **What it verifies**: Vite dev server is running and serving content

### Backend Health Check
- **URL**: `http://localhost:8000/api/v1/auth/csrf/`
- **Method**: GET request
- **Success**: 200 status with JSON response
- **What it verifies**:
  - Django server is running
  - Database is connected
  - URL routing works
  - Authentication endpoints are available

## Writing Tests

### Basic Test Structure

```javascript
import { test, expect } from '@playwright/test';

test('descriptive test name', async ({ page }) => {
  // Navigate to page
  await page.goto('/');

  // Interact with elements
  await page.click('button');

  // Make assertions
  await expect(page).toHaveTitle(/Expected Title/);
});
```

### Testing API Endpoints

```javascript
test('backend API works', async ({ request }) => {
  const response = await request.get('http://localhost:8000/api/v1/auth/csrf/');

  expect(response.ok()).toBeTruthy();
  expect(response.status()).toBe(200);

  const data = await response.json();
  expect(data).toHaveProperty('csrfToken');
});
```

### Testing Frontend-Backend Integration

```javascript
test('frontend can fetch from backend', async ({ page }) => {
  await page.goto('/');

  const apiWorks = await page.evaluate(async () => {
    const res = await fetch('http://localhost:8000/api/v1/auth/csrf/');
    const data = await res.json();
    return data.csrfToken?.length > 0;
  });

  expect(apiWorks).toBeTruthy();
});
```

## CI/CD Configuration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install frontend dependencies
        run: cd web && npm ci

      - name: Install backend dependencies
        run: cd backend && pip install -r requirements.txt

      - name: Install Playwright browsers
        run: cd web && npx playwright install --with-deps

      - name: Run E2E tests
        run: cd web && npm run test:e2e

      - name: Upload test report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: web/playwright-report/
```

## Troubleshooting

### Terminal Crashes

**Symptom**: Terminal freezes or crashes when running Playwright tests

**Solutions**:
1. Ensure `reporter: [['html', { open: 'never' }]]` is set
2. Run in headless mode (default)
3. Limit workers in CI: `workers: process.env.CI ? 1 : undefined`

### Server Not Starting

**Symptom**: "Timed out waiting for webServer"

**Solutions**:
1. Check server health check URL is correct
2. Increase timeout: `timeout: 180 * 1000`
3. Manually start servers first: `reuseExistingServer: true`
4. Check server logs: `stdout: 'pipe'` in webServer config

### Backend Health Check Fails

**Symptom**: Frontend works but backend health check times out

**Solutions**:
1. Verify Django migrations are applied: `python manage.py migrate`
2. Check virtual environment is activated
3. Ensure Redis is running (if required): `redis-cli ping`
4. Test health check URL manually: `curl http://localhost:8000/api/v1/auth/csrf/`

### Port Already in Use

**Symptom**: "EADDRINUSE: address already in use"

**Solutions**:
1. Kill existing processes:
   ```bash
   pkill -f "vite"
   pkill -f "runserver"
   ```
2. Use `reuseExistingServer: true` to reuse running servers
3. Change ports in config if needed

### Tests Pass Locally but Fail in CI

**Symptom**: Tests work on your machine but fail in GitHub Actions/CI

**Solutions**:
1. Set `CI=true` environment variable
2. Install system dependencies: `npx playwright install --with-deps`
3. Check timezone/locale differences
4. Increase timeouts for slower CI environments

## Best Practices

### 1. Always Use Server Auto-Start

✅ **Good** - Let Playwright manage servers:
```bash
npm run test:e2e
```

❌ **Bad** - Manually starting servers in separate terminals:
```bash
# Terminal 1
npm run dev

# Terminal 2
cd ../backend && python manage.py runserver

# Terminal 3
npm run test:e2e
```

### 2. Use Health Checks, Not Delays

✅ **Good** - Wait for server health check:
```javascript
webServer: {
  url: 'http://localhost:8000/api/v1/auth/csrf/',
}
```

❌ **Bad** - Arbitrary delays:
```javascript
webServer: {
  command: 'python manage.py runserver && sleep 10',  // Don't do this!
}
```

### 3. Reuse Servers in Development

✅ **Good** - Fast feedback loop:
```javascript
reuseExistingServer: !process.env.CI,
```

❌ **Bad** - Always restart:
```javascript
reuseExistingServer: false,  // Slow in development!
```

### 4. Test Real Integration, Not Mocks

✅ **Good** - Test actual API calls:
```javascript
test('blog posts load', async ({ page }) => {
  await page.goto('/blog');
  await expect(page.locator('article')).toHaveCount(3);
});
```

❌ **Bad** - Mock everything (use Vitest for unit tests):
```javascript
// This belongs in Vitest, not Playwright
vi.mock('../services/blogService');
```

## Resources

- [Playwright Documentation](https://playwright.dev)
- [Web Server Configuration](https://playwright.dev/docs/test-webserver)
- [Writing Tests](https://playwright.dev/docs/writing-tests)
- [Best Practices](https://playwright.dev/docs/best-practices)

## Summary

This Playwright setup gives you:

✅ **Zero manual server management** - Playwright handles it all
✅ **Crash prevention** - Proper reporter and timeout configuration
✅ **Fast development** - Server reuse in local development
✅ **CI/CD ready** - Works out of the box in GitHub Actions
✅ **True E2E testing** - Real browser + real servers
✅ **Health check verification** - Ensures full system readiness

Happy testing! 🎭
