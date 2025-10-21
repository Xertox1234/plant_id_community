# 🚀 Quick Start Guide - Plant ID Backend

## ⚡ 3-Minute Setup

### 1. Install & Start Backend
```bash
cd existing_implementation/backend
python3 -m venv venv
source venv/bin/activate
pip install Django djangorestframework django-cors-headers requests Pillow
python manage.py migrate
python manage.py runserver
```

### 2. Test It Works
```bash
curl http://localhost:8000/api/plant-identification/identify/health/
```

### 3. Start React Frontend
```bash
cd ../../web
npm run dev
```

## 🎯 That's It!

- Backend: http://localhost:8000
- Frontend: http://localhost:5173
- Upload a plant photo and watch the magic! ✨

## 🔑 API Keys (Already Configured)

✅ Plant.id: Configured in `.env`
✅ PlantNet: Configured in `.env`
✅ CORS: Enabled for React frontend

## 📡 API Endpoint

**POST** `/api/plant-identification/identify/`
- Upload: `image` (multipart/form-data)
- Returns: Plant name, care instructions, disease detection

## 🧪 Test with Postman

1. Method: **POST**
2. URL: `http://localhost:8000/api/plant-identification/identify/`
3. Body → form-data
4. Key: `image` (type: File)
5. Value: Select plant image
6. Send! 🚀

## 💡 How It Works

```
React Upload
    ↓
Django API
    ↓
┌──────────────┬──────────────┐
│  Plant.id    │  PlantNet    │
│  (ID + AI)   │  (Care Info) │
└──────────────┴──────────────┘
    ↓
Merge Results
    ↓
Return Comprehensive Data
```

## 📊 What You Get Back

```json
{
  "success": true,
  "plant_name": "Monstera Deliciosa",
  "scientific_name": "Monstera deliciosa",
  "confidence": 0.95,
  "suggestions": [...],
  "care_instructions": {...},
  "disease_detection": {...}
}
```

## 🐛 Troubleshooting

**"Module not found"**
```bash
pip install -r requirements.txt
```

**"Table doesn't exist"**
```bash
python manage.py migrate
```

**CORS errors**
Check `.env` has:
```
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

---

**Need detailed setup?** Read `SETUP_COMPLETE_READ_ME.md`

**Ready to test!** 🌿
