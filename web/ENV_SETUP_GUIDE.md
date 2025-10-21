# Web Frontend - API Keys & Environment Setup

## Required Environment Variables

### 1. Backend API URL
**Variable**: `VITE_API_URL`  
**Default**: `http://localhost:8000`  
**Purpose**: Django backend API endpoint  
**Required**: Yes (for Plant ID, Blog, Forum features)

---

## Optional API Keys

### 2. Plant Identification APIs

The Django backend handles plant identification using these services. **You don't need to add these to the React frontend** - they should be configured in the Django backend `.env` file.

#### Trefle API (Plant Database)
- **Purpose**: Plant species database and taxonomy
- **Get Key**: https://trefle.io/
- **Backend Variable**: `TREFLE_API_KEY`
- **Free Tier**: 120 requests/day
- **Cost**: Free for development

#### PlantNet API (AI Identification)
- **Purpose**: AI-powered plant identification from photos
- **Get Key**: https://my.plantnet.org/
- **Backend Variable**: `PLANTNET_API_KEY`
- **Free Tier**: 500 identifications/day
- **Cost**: Free for development

#### Kindwise (Plant.id) API - PRIMARY
- **Purpose**: AI plant identification with disease detection
- **Get Key**: https://web.plant.id/
- **Backend Variable**: `PLANT_ID_API_KEY`
- **Current Key**: ✅ Configured
- **Usage**: Primary identification + health assessment

#### PlantNet API - SUPPLEMENTAL
- **Purpose**: Open source plant identification + care instructions
- **Get Key**: https://my.plantnet.org/
- **Backend Variable**: `PLANTNET_API_KEY`  
- **Current Key**: ✅ Configured
- **Usage**: Enrich results with detailed care instructions

---

## Setup Instructions

### Development Setup (Minimal)

1. **Copy the example file**:
   ```bash
   cp .env.example .env
   ```

2. **Set backend URL** (default works for local development):
   ```bash
   VITE_API_URL=http://localhost:8000
   ```

3. **Start the dev server**:
   ```bash
   npm run dev
   ```

That's it! The React frontend will work with mock data until you connect the Django backend.

---

### Production Setup

1. **Copy the example file**:
   ```bash
   cp .env.example .env
   ```

2. **Set your production backend URL**:
   ```bash
   VITE_API_URL=https://api.yourdomain.com
   ```

3. **Optional: Add analytics**:
   ```bash
   VITE_GA4_MEASUREMENT_ID=G-XXXXXXXXXX
   VITE_SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
   VITE_ENVIRONMENT=production
   ```

4. **Build for production**:
   ```bash
   npm run build
   ```

---

## Backend Setup (Django)

The Plant ID feature requires the **Django backend** to be running with proper API keys configured.

### Backend Environment File Location
`/existing_implementation/backend/.env`

### Required Backend API Keys

1. **Plant.id API** (Current implementation):
   ```bash
   PLANT_ID_API_KEY=your-plant-id-api-key
   ```
   - Get key: https://web.plant.id/
   - Free trial: 100 identifications
   - Production: $29/month

2. **Alternative: Trefle + PlantNet** (Optional):
   ```bash
   TREFLE_API_KEY=your-trefle-api-key
   PLANTNET_API_KEY=your-plantnet-api-key
   ```

### Backend Setup Steps

1. Navigate to backend directory:
   ```bash
   cd existing_implementation/backend
   ```

2. Copy environment template:
   ```bash
   cp .env.example .env
   ```

3. Add your Plant.id API key:
   ```bash
   # In .env file
   PLANT_ID_API_KEY=your-actual-key-here
   ```

4. Start Django server:
   ```bash
   python manage.py runserver
   ```

Now the React frontend can connect to Django at `http://localhost:8000` and use the Plant ID feature!

---

## API Key Priority

### For Plant Identification

The backend tries APIs in this order:
1. **Plant.id API** (primary) - Best accuracy, disease detection
2. **PlantNet API** (fallback) - Free, good for common plants
3. **Trefle API** (database) - Plant info after identification

You only need **one** of these to work:
- **Recommended**: Get Plant.id API key (100 free identifications to test)
- **Free alternative**: Use PlantNet API (500/day free)

---

## Current Status

✅ **React Frontend**: Fully built and ready  
✅ **Django Backend**: Exists in `/existing_implementation/backend/`  
⚠️ **API Keys**: Need to be configured in Django backend `.env`  
⚠️ **Backend Running**: Needs `python manage.py runserver` on port 8000  

---

## Testing Without Backend

The React frontend works standalone! Just:

1. Upload a plant photo
2. Click "Identify Plant"
3. You'll see a "Network Error" (expected without backend)

To see it working:
1. Configure backend API key (Plant.id or PlantNet)
2. Start Django server: `python manage.py runserver`
3. Upload photo again - now you'll get real AI results! 🌿

---

## Getting API Keys

### Quick Start (Free Testing)

**Option 1: Plant.id** (Best accuracy)
1. Go to https://web.plant.id/
2. Sign up for free account
3. Get API key (100 free identifications)
4. Add to backend `.env`: `PLANT_ID_API_KEY=your-key`

**Option 2: PlantNet** (More free calls)
1. Go to https://my.plantnet.org/
2. Create account
3. Generate API key (500/day free)
4. Add to backend `.env`: `PLANTNET_API_KEY=your-key`

### For Production

**Plant.id Pro**:
- $29/month = 1,000 identifications
- $49/month = 2,500 identifications
- Best accuracy + disease detection
- Link: https://web.plant.id/pricing

---

## Need Help?

**Frontend not connecting to backend?**
- Check backend is running: `curl http://localhost:8000/api/`
- Check CORS settings in Django `settings.py`
- Verify `VITE_API_URL` in `.env`

**Plant ID not working?**
- Check backend logs: `python manage.py runserver`
- Verify API key in backend `.env`
- Test API key directly: see backend docs

**Still stuck?**
- Check `/existing_implementation/docs/` for detailed guides
- Review Django backend logs for errors
- Ensure database is migrated: `python manage.py migrate`
