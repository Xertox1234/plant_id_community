# Week 2 Performance Optimization - Complete Fresh Implementation Plan

## Status: Phase 1 Complete ✅ | Phase 2-5 Pending

---

## Architecture
```
/backend/          # NEW Django backend (copied from existing_implementation/backend)
/web/              # React frontend (already exists)
/plant_community_mobile/  # Flutter app (connects to same backend)
```

---

## Phase 1: Create New Backend from Template ✅ COMPLETE

### 1.1 Copy Backend Structure ✅
- ✅ Copy entire `existing_implementation/backend/` to `/backend/`
- ✅ Create new Python 3.13 venv in `/backend/venv/`
- ✅ Install requirements.txt (135+ packages)
- ✅ Test backend runs: `python manage.py runserver`

### 1.2 Configure for New Location ✅
- ✅ Backend running at localhost:8000
- ✅ `/web/.env` already configured to use localhost:8000
- ✅ `/web/vite.config.js` proxy configured for /api routes
- ✅ `/backend/.env` contains API keys (Plant.id, PlantNet)

### 1.3 Clean State Verification ✅
- ✅ Removed Week 2 optimizations from copied code
- ✅ Reverted to sequential API processing
- ✅ Removed Redis config and caching code
- ✅ Deleted performance index migration
- ✅ Backend healthy at http://localhost:8000/api/plant-identification/identify/health/

**Phase 1 Checkpoint:** Clean backend is running successfully ✅

---

## Phase 2: Backend Performance Optimizations - From Scratch (3 hours)

### 2.1 Parallel API Processing (60% faster) ⏳ PENDING
**File**: `/backend/apps/plant_identification/services/combined_identification_service.py`

**Implementation Steps:**
1. Import ThreadPoolExecutor from concurrent.futures
2. Read image data once to avoid file pointer issues
3. Create two thread functions:
   - `call_plant_id()` - calls Plant.id API
   - `call_plantnet()` - calls PlantNet API
4. Submit both to ThreadPoolExecutor
5. Get results with timeout handling:
   - Plant.id: 35s timeout (30s API + 5s buffer)
   - PlantNet: 20s timeout (15s API + 5s buffer)
6. Add timing metrics and logging
7. Merge results from both APIs

**Expected Code Structure:**
```python
def _identify_parallel(self, image_data: bytes) -> tuple:
    import time
    start_time = time.time()

    def call_plant_id():
        try:
            logger.info("🚀 Plant.id API call started (parallel)")
            image_file = BytesIO(image_data)
            result = self.plant_id.identify_plant(image_file, include_diseases=True)
            logger.info(f"✅ Plant.id completed in {time.time() - start_time:.2f}s")
            return result
        except Exception as e:
            logger.error(f"❌ Plant.id failed: {e}")
            return None

    def call_plantnet():
        # Similar implementation
        pass

    # Execute in parallel
    future_plant_id = self.executor.submit(call_plant_id)
    future_plantnet = self.executor.submit(call_plantnet)

    plant_id_results = future_plant_id.result(timeout=35)
    plantnet_results = future_plantnet.result(timeout=20)

    return plant_id_results, plantnet_results
```

**Testing:**
- Test with real API calls
- Measure timing: Should be 2-5s (vs 4-9s sequential)
- Verify both APIs return results
- Test error handling (one API fails)

**Performance Target:** 4-9s → 2-5s (60% faster)

---

### 2.2 Redis Caching (40% fewer API calls) ⏳ PENDING

**Files:**
- `/backend/simple_server.py` or main settings
- `/backend/apps/plant_identification/services/plant_id_service.py`

**Implementation Steps:**

1. **Install Redis:**
   ```bash
   brew install redis
   brew services start redis
   redis-cli ping  # Should return PONG
   ```

2. **Install Package:**
   ```bash
   source venv/bin/activate
   pip install django-redis
   ```

3. **Configure Django (simple_server.py):**
   ```python
   CACHES = {
       'default': {
           'BACKEND': 'django_redis.cache.RedisCache',
           'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
           'OPTIONS': {
               'CLIENT_CLASS': 'django_redis.client.DefaultClient',
           },
           'KEY_PREFIX': 'plant_id',
           'TIMEOUT': 86400,  # 24 hours
       }
   }
   ```

4. **Implement Caching (plant_id_service.py):**
   ```python
   import hashlib
   from django.core.cache import cache

   def identify_plant(self, image_file, include_diseases=True):
       # Read image data
       image_data = image_file.read()

       # Generate cache key from image hash
       image_hash = hashlib.sha256(image_data).hexdigest()
       cache_key = f"plant_id:{image_hash}:{include_diseases}"

       # Check cache first
       cached_result = cache.get(cache_key)
       if cached_result:
           logger.info(f"✅ Cache HIT for image {image_hash[:8]}")
           return cached_result

       # Cache miss - call API
       logger.info(f"❌ Cache MISS for image {image_hash[:8]}")
       image_file.seek(0)  # Reset file pointer
       result = self._call_api(image_file, include_diseases)

       # Store in cache
       if result:
           cache.set(cache_key, result, timeout=86400)
           logger.info(f"💾 Cached result for image {image_hash[:8]}")

       return result
   ```

**Testing:**
- Upload same image twice
- First upload: Cache MISS (2-5s)
- Second upload: Cache HIT (<0.1s instant response)
- Check Redis: `redis-cli KEYS "plant_id:*"`
- Monitor hit rate: `redis-cli INFO stats | grep hits`

**Performance Target:** 30-40% cache hit rate, instant responses

---

### 2.3 Database Indexes (100x faster queries) ⏳ PENDING

**Files:** Create new migration in `/backend/apps/plant_identification/migrations/`

**Implementation Steps:**

1. **Create Empty Migration:**
   ```bash
   cd /backend
   source venv/bin/activate
   python manage.py makemigrations plant_identification --empty --name add_performance_indexes
   ```

2. **Edit Migration File:**
   Add 8 composite indexes:

   ```python
   from django.db import migrations, models

   class Migration(migrations.Migration):
       dependencies = [
           ('plant_identification', '0011_batchidentificationrequest_batchidentificationimage_and_more'),
       ]

       operations = [
           # PlantIdentificationRequest indexes
           migrations.AddIndex(
               model_name='plantidentificationrequest',
               index=models.Index(fields=['user', '-created_at'], name='idx_request_user_created'),
           ),
           migrations.AddIndex(
               model_name='plantidentificationrequest',
               index=models.Index(fields=['status', '-created_at'], name='idx_request_status_created'),
           ),

           # PlantIdentificationResult indexes
           migrations.AddIndex(
               model_name='plantidentificationresult',
               index=models.Index(fields=['confidence_score', '-created_at'], name='idx_result_confidence'),
           ),
           migrations.AddIndex(
               model_name='plantidentificationresult',
               index=models.Index(fields=['request', 'confidence_score'], name='idx_result_request_conf'),
           ),

           # PlantSpecies indexes
           migrations.AddIndex(
               model_name='plantspecies',
               index=models.Index(fields=['scientific_name'], name='idx_species_scientific'),
           ),
           migrations.AddIndex(
               model_name='plantspecies',
               index=models.Index(fields=['identification_count', '-created_at'], name='idx_species_popularity'),
           ),

           # UserPlant indexes
           migrations.AddIndex(
               model_name='userplant',
               index=models.Index(fields=['user', '-acquisition_date'], name='idx_userplant_user_date'),
           ),
           migrations.AddIndex(
               model_name='userplant',
               index=models.Index(fields=['species', 'user'], name='idx_userplant_species_user'),
           ),
       ]
   ```

3. **Apply Migration:**
   ```bash
   python manage.py migrate
   ```

4. **Verify Indexes:**
   ```bash
   python manage.py dbshell

   # SQLite
   .indexes plant_identification_plantidentificationrequest

   # PostgreSQL
   \d plant_identification_plantidentificationrequest
   ```

5. **Test Query Performance:**
   ```bash
   python manage.py shell

   from apps.plant_identification.models import PlantIdentificationRequest
   import time

   start = time.time()
   requests = PlantIdentificationRequest.objects.filter(
       user_id=1
   ).order_by('-created_at')[:20]
   list(requests)
   print(f"Query time: {(time.time() - start)*1000:.2f}ms")
   ```

**Performance Target:** 300-800ms → 3-8ms (100x faster)

---

## Phase 3: Frontend Image Compression (85% faster uploads) (1.5 hours)

### 3.1 Create Compression Utility ⏳ PENDING
**File**: `/web/src/utils/imageCompression.js`

```javascript
/**
 * Compress image before upload
 * @param {File} file - Original image file
 * @param {number} maxWidth - Maximum width (default 1200px)
 * @param {number} quality - JPEG quality 0-1 (default 0.85)
 * @returns {Promise<File>} Compressed image file
 */
export async function compressImage(file, maxWidth = 1200, quality = 0.85) {
  return new Promise((resolve) => {
    const reader = new FileReader();

    reader.onload = (e) => {
      const img = new Image();

      img.onload = () => {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');

        // Calculate new dimensions
        let width = img.width;
        let height = img.height;

        if (width > maxWidth) {
          height = (height * maxWidth) / width;
          width = maxWidth;
        }

        canvas.width = width;
        canvas.height = height;

        // Draw and compress
        ctx.drawImage(img, 0, 0, width, height);

        canvas.toBlob(
          (blob) => {
            resolve(new File([blob], file.name, {
              type: 'image/jpeg',
              lastModified: Date.now(),
            }));
          },
          'image/jpeg',
          quality
        );
      };

      img.src = e.target.result;
    };

    reader.readAsDataURL(file);
  });
}
```

---

### 3.2 Find and Update Upload Component ⏳ PENDING

**Steps:**
1. Find file upload component in `/web/src/`
2. Likely locations:
   - `/web/src/components/PlantIdentification/FileUpload.jsx`
   - `/web/src/pages/IdentifyPage.jsx`
   - Search for: `<input type="file"` or `FormData`

3. **Integrate Compression:**
   ```javascript
   import { compressImage } from '@/utils/imageCompression';

   const handleFileSelect = async (file) => {
     // Compress if > 2MB
     if (file.size > 2 * 1024 * 1024) {
       console.log(`Original size: ${(file.size / 1024 / 1024).toFixed(2)}MB`);

       const compressedFile = await compressImage(file);

       console.log(`Compressed size: ${(compressedFile.size / 1024 / 1024).toFixed(2)}MB`);

       file = compressedFile;
     }

     onFileSelect(file);
   };
   ```

4. **Add Loading Indicator:**
   ```javascript
   const [isCompressing, setIsCompressing] = useState(false);

   const handleFileSelect = async (file) => {
     if (file.size > 2 * 1024 * 1024) {
       setIsCompressing(true);
       file = await compressImage(file);
       setIsCompressing(false);
     }
     onFileSelect(file);
   };
   ```

---

### 3.3 Test Upload Performance ⏳ PENDING

**Test Cases:**
| Original Size | Expected Compressed | Reduction | Upload Time (3G) |
|--------------|---------------------|-----------|------------------|
| 10MB | ~800KB | 92% | 3-5s (was 40-80s) |
| 5MB | ~600KB | 88% | 2-4s (was 20-40s) |
| 2MB | ~500KB | 75% | 2-3s (was 8-16s) |
| <2MB | No compression | 0% | Original speed |

**Performance Target:** 85% size reduction, 85% faster uploads

---

## Phase 4: Integration Testing (1.5 hours)

### 4.1 Backend Performance Tests ⏳ PENDING

**Test Script:** `/backend/test_performance.py`
```python
import time
import requests
from pathlib import Path

API_URL = "http://localhost:8000"

# Test 1: Parallel API timing
def test_parallel_api():
    with open('test_plant.jpg', 'rb') as f:
        start = time.time()
        response = requests.post(
            f"{API_URL}/api/plant-identification/identify/",
            files={'image': f}
        )
        duration = time.time() - start

    print(f"✓ Identification time: {duration:.2f}s")
    assert duration < 6.0, "Should be under 6s (target: 2-5s)"
    return response.json()

# Test 2: Cache hit rate
def test_cache():
    with open('test_plant.jpg', 'rb') as f:
        # First call (cache miss)
        start1 = time.time()
        response1 = requests.post(
            f"{API_URL}/api/plant-identification/identify/",
            files={'image': f}
        )
        time1 = time.time() - start1

    with open('test_plant.jpg', 'rb') as f:
        # Second call (cache hit)
        start2 = time.time()
        response2 = requests.post(
            f"{API_URL}/api/plant-identification/identify/",
            files={'image': f}
        )
        time2 = time.time() - start2

    print(f"✓ Cache miss: {time1:.2f}s")
    print(f"✓ Cache hit: {time2:.2f}s")
    assert time2 < 1.0, "Cache hit should be < 1s"

if __name__ == '__main__':
    test_parallel_api()
    test_cache()
```

---

### 4.2 Frontend Integration with Playwright ⏳ PENDING

**File**: `/web/tests/plant-identification-performance.spec.js`

```javascript
import { test, expect } from '@playwright/test';

test('Week 2 Performance - Full Workflow', async ({ page }) => {
  // Navigate to identify page
  await page.goto('http://localhost:5173/identify');

  // Check page load time
  const startLoad = Date.now();
  await page.waitForLoadState('networkidle');
  const loadTime = Date.now() - startLoad;
  console.log(`✓ Page load: ${loadTime}ms`);
  expect(loadTime).toBeLessThan(3000);

  // Find file input
  const fileInput = page.locator('input[type="file"]').first();
  await expect(fileInput).toBeVisible();

  // Upload image
  await fileInput.setInputFiles('test_plant.jpg');

  // Wait for compression (if > 2MB)
  await page.waitForTimeout(2000);

  // Wait for identification results
  await page.waitForSelector('[data-testid="plant-result"]', { timeout: 10000 });

  // Verify results displayed
  const result = page.locator('[data-testid="plant-result"]');
  await expect(result).toBeVisible();

  console.log('✓ Full workflow complete');
});

test('Backend Health Check', async ({ page }) => {
  const response = await page.request.get('http://localhost:8000/api/plant-identification/identify/health/');
  expect(response.status()).toBe(200);

  const data = await response.json();
  expect(data.status).toBe('healthy');
  expect(data.apis.plant_id).toBe('configured');
  expect(data.apis.plantnet).toBe('configured');
});
```

---

### 4.3 Create Documentation ⏳ PENDING

**File**: `/WEEK2_PERFORMANCE.md` (project root)

Will document:
- All optimizations implemented
- Before/after performance metrics
- Configuration instructions
- Testing procedures
- Troubleshooting guide

---

## Phase 5: Cleanup and Finalization (30 min)

### 5.1 Final Verification ⏳ PENDING
- [ ] Backend health check passes
- [ ] Frontend loads and connects
- [ ] Plant identification workflow works
- [ ] All performance targets met
- [ ] All tests passing

### 5.2 Delete existing_implementation ⏳ PENDING
```bash
# Optional backup
tar -czf existing_implementation_backup.tar.gz existing_implementation/

# Delete folder
rm -rf existing_implementation/

# Update .gitignore if needed
# Remove references from /CLAUDE.md
```

### 5.3 Update Documentation ⏳ PENDING
- [ ] Update main `/README.md` with new structure
- [ ] Update `/CLAUDE.md` with /backend location
- [ ] Add Week 2 performance documentation
- [ ] Document API endpoints and usage

### 5.4 Git Commits ⏳ PENDING
```bash
git add backend/
git commit -m "feat: add new backend with Week 2 performance optimizations

- Parallel API processing (Plant.id + PlantNet): 60% faster
- Redis caching with SHA-256 image hashing: 30-40% cache hit rate
- Database composite indexes: 100x faster queries
- See WEEK2_PERFORMANCE.md for details"

git add web/src/utils/imageCompression.js
git add web/src/components/[upload-component]
git commit -m "feat: add frontend image compression

- Canvas-based compression: max 1200px, 85% quality
- 85% size reduction (10MB → 800KB)
- Auto-compress files > 2MB
- See WEEK2_PERFORMANCE.md for details"

git add WEEK2_PERFORMANCE.md
git commit -m "docs: add Week 2 performance optimization documentation"

git rm -r existing_implementation/
git commit -m "chore: remove existing_implementation reference folder"

git add CLAUDE.md README.md
git commit -m "docs: update architecture docs for new backend location"
```

---

## Success Criteria

- [x] New `/backend/` folder working independently
- [x] `/web/` frontend connects to new `/backend/`
- [ ] Parallel API processing: 60% faster (4-9s → 2-5s)
- [ ] Redis caching: 30-40% cache hit rate
- [ ] Database indexes: 100x faster queries (800ms → 8ms)
- [ ] Image compression: 85% size reduction (10MB → 800KB)
- [ ] All tests passing
- [ ] `existing_implementation/` deleted
- [ ] Documentation complete

---

## Performance Targets

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Plant ID time | 4-9s | 2-5s | 60% faster |
| Cache hits | 0% | 30-40% | Instant (<0.1s) |
| DB queries | 800ms | 8ms | 100x faster |
| Image upload (10MB) | 40-80s | 3-5s | 85% faster |

---

## Estimated Time: 7-9 hours total

**Progress:** Phase 1 Complete (1 hour) | Remaining: 6-8 hours

---

## Current Status

✅ **Phase 1 Complete** - Backend copied, cleaned, and running
⏳ **Phase 2 Next** - Implement backend optimizations (parallel, cache, indexes)

**Next Steps:**
1. Implement parallel API processing in combined_identification_service.py
2. Install Redis and add caching to plant_id_service.py
3. Create and apply database index migration
4. Then move to Phase 3 (frontend compression)
