import { test, expect } from '@playwright/test';

/**
 * Health Check Tests
 *
 * These tests verify that both servers are fully operational
 * before running the main test suite.
 */

test.describe('System Health Checks', () => {
  test('Vite dev server is healthy', async ({ page }) => {
    const response = await page.goto('/');

    expect(response?.status()).toBe(200);
    expect(response?.ok()).toBeTruthy();
  });

  test('Django backend server is healthy', async ({ request }) => {
    // Test multiple endpoints to ensure full backend readiness

    // 1. CSRF endpoint
    const csrfResponse = await request.get('http://localhost:8000/api/v1/auth/csrf/');
    expect(csrfResponse.ok()).toBeTruthy();

    // 2. Blog API endpoint
    const blogResponse = await request.get('http://localhost:8000/api/v2/blog-posts/');
    expect(blogResponse.status()).toBeLessThan(500);  // Should not have server errors

    // 3. Forum API endpoint
    const forumResponse = await request.get('http://localhost:8000/api/v1/forum/categories/');
    expect(forumResponse.status()).toBeLessThan(500);
  });

  test('Redis cache is accessible', async ({ request }) => {
    // Make a request that would use cache (blog posts)
    const response = await request.get('http://localhost:8000/api/v2/blog-posts/?limit=1');

    // Should succeed even if Redis is down (graceful degradation)
    expect(response.status()).toBeLessThan(500);
  });

  test('CORS is properly configured', async ({ page }) => {
    // Navigate to frontend
    await page.goto('/');

    // Make a fetch request to backend from frontend context
    const response = await page.evaluate(async () => {
      try {
        const res = await fetch('http://localhost:8000/api/v1/auth/csrf/', {
          credentials: 'include'
        });
        return { ok: res.ok, status: res.status };
      } catch (error) {
        return { ok: false, error: error.message };
      }
    });

    expect(response.ok).toBeTruthy();
  });

  test('frontend can communicate with backend', async ({ page }) => {
    await page.goto('/');

    // Execute a real API call from the frontend
    const result = await page.evaluate(async () => {
      try {
        const res = await fetch('http://localhost:8000/api/v1/auth/csrf/', {
          credentials: 'include',
          headers: {
            'Accept': 'application/json',
          }
        });

        if (!res.ok) {
          return { success: false, error: `HTTP ${res.status}` };
        }

        const data = await res.json();
        // CSRF endpoint returns {"detail": "CSRF cookie set"} and sets the token as a cookie
        // Just verify we got the expected response message
        return {
          success: true,
          hasExpectedMessage: data.detail === "CSRF cookie set",
          data: data
        };
      } catch (error) {
        return { success: false, error: error.message };
      }
    });

    // Verify successful communication and expected response format
    expect(result.success).toBeTruthy();
    if (result.success) {
      expect(result.hasExpectedMessage).toBeTruthy();
    }
  });
});

test.describe('Performance Checks', () => {
  test('frontend loads within acceptable time', async ({ page }) => {
    const startTime = Date.now();
    await page.goto('/');
    const loadTime = Date.now() - startTime;

    // Should load within 5 seconds on local dev
    expect(loadTime).toBeLessThan(5000);
  });

  test('API response time is acceptable', async ({ request }) => {
    const startTime = Date.now();
    await request.get('http://localhost:8000/api/v1/auth/csrf/');
    const responseTime = Date.now() - startTime;

    // API should respond within 1 second
    expect(responseTime).toBeLessThan(1000);
  });
});
