# Phase 6 Manual E2E Testing Guide

## Environment Setup

### ✅ Prerequisites Verified
- Backend: Running on http://localhost:8000 ✓
- Frontend: Running on http://localhost:5174 ✓
- Branch: `feature/phase-6-search-and-image-upload`

### Test User Account
You'll need a test account with forum posting permissions:
- If you don't have one, create via Django admin: http://localhost:8000/admin/
- Or use existing credentials

---

## Test Suite 1: Search Functionality

### 1.1 Basic Search
**URL**: http://localhost:5174/forum/search

**Steps**:
1. Navigate to search page
2. Verify initial state shows "Enter a search query to begin"
3. Type "plant" in search box
4. Wait 500ms (debounce delay)
5. Verify loading spinner appears
6. Verify search results load

**Expected Results**:
- ✓ Search input is visible and focused
- ✓ Debounce prevents immediate search
- ✓ Loading spinner displays during search
- ✓ Results show matching threads and posts
- ✓ Result count displays (e.g., "Found 5 threads and 12 posts for 'plant'")

**Pass/Fail**: _____________

---

### 1.2 Empty Search Results
**Steps**:
1. Search for "xyz123nonexistent"
2. Wait for results

**Expected Results**:
- ✓ "No results found" message displays
- ✓ Suggestion text: "Try different keywords or remove some filters"
- ✓ No error messages in console

**Pass/Fail**: _____________

---

### 1.3 Category Filter
**Steps**:
1. Search for "watering"
2. Select a category from dropdown (e.g., "Plant Care")
3. Verify results filter to selected category

**Expected Results**:
- ✓ Category dropdown populated with forum categories
- ✓ Results update when category selected
- ✓ "Clear filters" button appears
- ✓ URL updates with `?q=watering&category=plant-care`

**Pass/Fail**: _____________

---

### 1.4 Author Filter
**Steps**:
1. Search for "watering"
2. Type a username in "Author" field
3. Wait 500ms (debounce)
4. Verify results filter to posts by that author

**Expected Results**:
- ✓ Author filter debounces properly
- ✓ Results update after debounce
- ✓ "Clear filters" button appears
- ✓ URL updates with `?q=watering&author=username`

**Pass/Fail**: _____________

---

### 1.5 Clear Filters
**Steps**:
1. Apply both category and author filters
2. Click "Clear filters" button
3. Verify filters reset

**Expected Results**:
- ✓ Category dropdown resets to "All Categories"
- ✓ Author input clears
- ✓ Results show unfiltered search
- ✓ "Clear filters" button disappears
- ✓ URL resets to `?q=watering`

**Pass/Fail**: _____________

---

### 1.6 Pagination
**Steps**:
1. Search for a common term that returns many results
2. Verify pagination controls appear
3. Click "Next" button
4. Click "Previous" button

**Expected Results**:
- ✓ Pagination displays "Page 1", "Previous", "Next"
- ✓ "Previous" disabled on page 1
- ✓ "Next" disabled on last page
- ✓ Page number updates in UI
- ✓ URL updates with `?q=term&page=2`
- ✓ Results load for correct page

**Pass/Fail**: _____________

---

### 1.7 Search Input Debouncing
**Steps**:
1. Type "w" (wait)
2. Type "a" (wait)
3. Type "t" (wait)
4. Type "er" quickly
5. Observe network tab

**Expected Results**:
- ✓ Only ONE API call made after final keystroke
- ✓ 500ms delay before search executes
- ✓ Previous searches cancelled

**Pass/Fail**: _____________

---

### 1.8 Direct URL Navigation
**Steps**:
1. Navigate directly to: `http://localhost:5174/forum/search?q=watering&category=plant-care&page=2`
2. Verify state loads from URL params

**Expected Results**:
- ✓ Search input populated with "watering"
- ✓ Category dropdown shows "plant-care"
- ✓ Page 2 results displayed
- ✓ All filters applied correctly

**Pass/Fail**: _____________

---

### 1.9 Error Handling
**Steps**:
1. Stop the backend server temporarily
2. Attempt a search
3. Restart backend

**Expected Results**:
- ✓ Error message displays clearly
- ✓ No JavaScript errors in console
- ✓ UI remains functional
- ✓ Can retry search after backend restarts

**Pass/Fail**: _____________

---

### 1.10 Accessibility
**Steps**:
1. Navigate using keyboard only (Tab, Enter, arrows)
2. Use screen reader (if available)
3. Check ARIA labels

**Expected Results**:
- ✓ Search input has `aria-label="Search query"`
- ✓ Category dropdown has proper label
- ✓ Author input has proper label
- ✓ Pagination buttons keyboard accessible
- ✓ Focus visible on all interactive elements
- ✓ Semantic HTML structure (h1, nav, main)

**Pass/Fail**: _____________

---

## Test Suite 2: Image Upload Functionality

### 2.1 Upload Area Initial State
**Steps**:
1. Navigate to a forum thread
2. Find a post with edit/upload capability
3. Locate ImageUploadWidget

**Expected Results**:
- ✓ Upload area displays with dashed border
- ✓ "Click to upload or drag and drop" text visible
- ✓ "PNG, JPG, GIF, WEBP up to 10MB (0/6 images)" displays
- ✓ Upload icon (SVG) visible

**Pass/Fail**: _____________

---

### 2.2 Click to Upload (Valid File)
**Steps**:
1. Click upload area
2. Select a valid image (PNG, JPG, GIF, or WEBP under 10MB)
3. Wait for upload

**Expected Results**:
- ✓ File input dialog opens
- ✓ "Uploading..." spinner displays
- ✓ Image uploads successfully
- ✓ Thumbnail appears in grid
- ✓ Counter updates to "1/6 images"
- ✓ Console shows `[IMAGE_UPLOAD] Upload successful`

**Pass/Fail**: _____________

---

### 2.3 File Type Validation
**Steps**:
1. Attempt to upload a PDF file
2. Observe error message

**Expected Results**:
- ✓ Error message: "Invalid file type. Allowed: image/jpeg, image/jpg, image/png, image/gif, image/webp"
- ✓ File not uploaded
- ✓ API call NOT made (check network tab)
- ✓ Error displayed in red alert box

**Pass/Fail**: _____________

---

### 2.4 File Size Validation
**Steps**:
1. Attempt to upload image larger than 10MB
2. Observe error message

**Expected Results**:
- ✓ Error message: "File too large. Maximum size: 10MB"
- ✓ File not uploaded
- ✓ API call NOT made
- ✓ Error displayed in red alert box

**Pass/Fail**: _____________

---

### 2.5 Maximum Images Limit
**Steps**:
1. Upload 6 valid images
2. Verify counter shows "6/6 images"
3. Attempt to upload 7th image

**Expected Results**:
- ✓ File input disabled when 6 images reached
- ✓ Upload area shows "opacity-50 cursor-not-allowed"
- ✓ Error message: "Maximum 6 images allowed"
- ✓ 7th image not uploaded

**Pass/Fail**: _____________

---

### 2.6 Drag and Drop Upload
**Steps**:
1. Drag a valid image file over upload area
2. Observe hover state
3. Drop the file
4. Wait for upload

**Expected Results**:
- ✓ Border changes to green (`border-green-500`) on dragover
- ✓ Background changes to light green (`bg-green-50`)
- ✓ Hover state removes on dragleave
- ✓ File uploads on drop
- ✓ Upload completes successfully

**Pass/Fail**: _____________

---

### 2.7 Delete Image
**Steps**:
1. Upload an image
2. Hover over thumbnail
3. Click "Delete" button
4. Wait for deletion

**Expected Results**:
- ✓ Hover shows dark overlay with delete button
- ✓ Delete button visible: `opacity-0 group-hover:opacity-100`
- ✓ Clicking delete removes image
- ✓ Counter decrements (e.g., "2/6" → "1/6")
- ✓ Thumbnail removed from grid
- ✓ Console shows `[IMAGE_UPLOAD] Delete successful`

**Pass/Fail**: _____________

---

### 2.8 Delete Error Handling
**Steps**:
1. Stop backend server temporarily
2. Attempt to delete an image
3. Observe error

**Expected Results**:
- ✓ Error message displays: "Delete failed"
- ✓ Image remains in grid
- ✓ Counter unchanged
- ✓ Console shows `[IMAGE_UPLOAD] Delete failed`

**Pass/Fail**: _____________

---

### 2.9 Multiple Uploads
**Steps**:
1. Upload 3 images consecutively
2. Verify all thumbnails display
3. Delete middle image
4. Upload a new image

**Expected Results**:
- ✓ All 3 thumbnails render correctly
- ✓ Grid layout responsive (2 columns mobile, 3 desktop)
- ✓ Deleting middle image doesn't affect others
- ✓ Can upload after deletion
- ✓ Counter accurate throughout

**Pass/Fail**: _____________

---

### 2.10 Upload Progress Indication
**Steps**:
1. Upload a larger file (5-10MB)
2. Observe UI during upload

**Expected Results**:
- ✓ Upload area shows "Uploading..." text
- ✓ Animated spinner displays
- ✓ Upload area disabled during upload
- ✓ File input disabled
- ✓ Progress completes, thumbnail appears

**Pass/Fail**: _____________

---

### 2.11 Image Preview Quality
**Steps**:
1. Upload several different image types (PNG, JPG, GIF, WEBP)
2. Verify thumbnails render correctly

**Expected Results**:
- ✓ Thumbnails display at correct size (h-32)
- ✓ `object-cover` maintains aspect ratio
- ✓ Images not distorted
- ✓ Thumbnails load quickly
- ✓ Uses `image_thumbnail` URL if available

**Pass/Fail**: _____________

---

### 2.12 Accessibility - Image Upload
**Steps**:
1. Navigate with keyboard only
2. Tab to upload area
3. Press Enter or Space to open file dialog
4. Tab to delete button
5. Press Enter to delete

**Expected Results**:
- ✓ Upload area focusable (`tabIndex={0}`)
- ✓ `aria-label="Upload image"` present
- ✓ File input has `aria-label="File input"`
- ✓ Delete button has `aria-label="Delete image"`
- ✓ Keyboard navigation works smoothly
- ✓ Focus visible on all elements

**Pass/Fail**: _____________

---

## Test Suite 3: Integration Tests

### 3.1 Search → Navigate to Thread → Upload Image
**Steps**:
1. Search for a thread
2. Click on a thread from results
3. Navigate to thread detail page
4. Find a post with upload capability
5. Upload an image

**Expected Results**:
- ✓ Search results clickable
- ✓ Thread detail loads correctly
- ✓ ImageUploadWidget renders
- ✓ Upload completes successfully
- ✓ Image persists on page refresh

**Pass/Fail**: _____________

---

### 3.2 Network Error Recovery
**Steps**:
1. Open DevTools Network tab
2. Set network throttling to "Slow 3G"
3. Perform search
4. Upload image
5. Restore normal network

**Expected Results**:
- ✓ Search handles slow network gracefully
- ✓ Loading states visible
- ✓ Upload shows progress indicator
- ✓ Operations complete successfully
- ✓ No timeout errors

**Pass/Fail**: _____________

---

### 3.3 Console Cleanliness
**Steps**:
1. Open DevTools Console
2. Perform all operations above
3. Monitor for errors/warnings

**Expected Results**:
- ✓ No JavaScript errors
- ✓ No React warnings
- ✓ Only expected logs: `[IMAGE_UPLOAD]`, `[CACHE]`, etc.
- ✓ No memory leaks (check Profiler)

**Pass/Fail**: _____________

---

### 3.4 Responsive Design
**Steps**:
1. Test on desktop (1920x1080)
2. Test on tablet (768x1024)
3. Test on mobile (375x667)

**Expected Results**:
- ✓ Search layout adapts to screen size
- ✓ Image grid responsive (2 cols mobile, 3 desktop)
- ✓ Touch targets adequate on mobile (44x44px min)
- ✓ No horizontal scroll
- ✓ Text readable at all sizes

**Pass/Fail**: _____________

---

## Summary

### Overall Test Results
- Search Functionality: ___ / 10 passed
- Image Upload: ___ / 12 passed
- Integration Tests: ___ / 4 passed

**Total**: ___ / 26 passed (__%)

### Critical Issues Found
1. _____________________________________________
2. _____________________________________________
3. _____________________________________________

### Minor Issues Found
1. _____________________________________________
2. _____________________________________________
3. _____________________________________________

### Notes
_____________________________________________
_____________________________________________
_____________________________________________

### Sign-Off
- Tester: _____________
- Date: _____________
- Branch: feature/phase-6-search-and-image-upload
- Commit: 82954a2

---

## Automated Test Coverage Verification

Run these commands to verify automated tests still pass:

```bash
cd web

# SearchPage tests
npm test -- src/pages/forum/SearchPage.test.jsx --run

# ImageUploadWidget tests
npm test -- src/components/forum/ImageUploadWidget.test.jsx --run

# All forum tests
npm test -- src/pages/forum/ src/components/forum/ --run
```

**Expected**: All tests passing (47/47)
