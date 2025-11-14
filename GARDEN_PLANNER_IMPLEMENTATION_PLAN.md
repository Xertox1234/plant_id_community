# Garden Planner Feature - Implementation Plan (4-6 weeks)

## Overview
Replicate all Gardening-Planner features as `/garden-planner` section in React web app with hybrid Django + Firebase backend, fully integrated with existing plant ID, forum, and blog features.

**Source Repository**: https://github.com/Ashutosh049-lab/Gardening-Planner
**Integration Approach**: Replicate features (not iframe embed)
**Backend Strategy**: Hybrid Django + Firebase
**Platform Priority**: React Web First
**Timeline**: 4-6 weeks (full featured MVP)

---

## Phase 1: Backend Foundation (Week 1-2)

### Django Backend (`backend/apps/garden/`)
**New Django app with PostgreSQL models:**

#### Models
```python
# apps/garden/models.py

class Garden(models.Model):
    """User's garden with layout and metadata"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='gardens')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    dimensions = models.JSONField()  # {width: int, height: int, unit: 'ft'|'m'}
    layout_data = models.JSONField(default=dict)  # Plant positions for canvas
    location = models.JSONField(null=True)  # {lat: float, lng: float, city: str}
    climate_zone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    visibility = models.CharField(
        max_length=10,
        choices=[('private', 'Private'), ('public', 'Public')],
        default='private'
    )
    featured = models.BooleanField(default=False)  # Staff picks

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
            models.Index(fields=['visibility', 'featured']),
        ]

class GardenPlant(models.Model):
    """Plant instance in a garden"""
    garden = models.ForeignKey(Garden, on_delete=models.CASCADE, related_name='plants')
    plant_species = models.ForeignKey(
        'plant_identification.PlantSpecies',
        on_delete=models.SET_NULL,
        null=True,
        related_name='garden_instances'
    )
    common_name = models.CharField(max_length=200)
    scientific_name = models.CharField(max_length=200, blank=True)
    planted_date = models.DateField()
    position = models.JSONField()  # {x: int, y: int} on canvas
    image = models.ImageField(upload_to='garden_plants/', null=True, blank=True)
    notes = models.TextField(blank=True)
    health_status = models.CharField(
        max_length=20,
        choices=[
            ('healthy', 'Healthy'),
            ('needs_attention', 'Needs Attention'),
            ('diseased', 'Diseased'),
            ('dead', 'Dead')
        ],
        default='healthy'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['garden', '-planted_date']

class CareReminder(models.Model):
    """Care task reminder for a plant"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='care_reminders')
    garden_plant = models.ForeignKey(
        GardenPlant,
        on_delete=models.CASCADE,
        related_name='reminders'
    )
    reminder_type = models.CharField(
        max_length=20,
        choices=[
            ('watering', 'Watering'),
            ('fertilizing', 'Fertilizing'),
            ('pruning', 'Pruning'),
            ('repotting', 'Repotting'),
            ('pest_check', 'Pest Check'),
            ('custom', 'Custom')
        ]
    )
    custom_type_name = models.CharField(max_length=100, blank=True)
    scheduled_date = models.DateTimeField()
    recurring = models.BooleanField(default=False)
    interval_days = models.IntegerField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    skipped = models.BooleanField(default=False)
    skip_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    notification_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scheduled_date']
        indexes = [
            models.Index(fields=['user', 'scheduled_date', 'completed']),
            models.Index(fields=['notification_sent', 'scheduled_date']),
        ]

class Task(models.Model):
    """Seasonal gardening task"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='garden_tasks')
    garden = models.ForeignKey(
        Garden,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='tasks'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    category = models.CharField(
        max_length=20,
        choices=[
            ('planting', 'Planting'),
            ('maintenance', 'Maintenance'),
            ('harvesting', 'Harvesting'),
            ('preparation', 'Preparation'),
            ('other', 'Other')
        ]
    )
    season = models.CharField(
        max_length=10,
        choices=[
            ('spring', 'Spring'),
            ('summer', 'Summer'),
            ('fall', 'Fall'),
            ('winter', 'Winter'),
            ('year_round', 'Year Round')
        ],
        blank=True
    )
    priority = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High')
        ],
        default='medium'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-priority', 'due_date']

class PestIssue(models.Model):
    """Pest or disease tracking"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pest_issues')
    garden_plant = models.ForeignKey(
        GardenPlant,
        on_delete=models.CASCADE,
        related_name='pest_issues'
    )
    pest_type = models.CharField(max_length=200)
    description = models.TextField()
    identified_date = models.DateField(auto_now_add=True)
    severity = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical')
        ]
    )
    treatment = models.TextField(blank=True)
    treatment_date = models.DateField(null=True, blank=True)
    resolved = models.BooleanField(default=False)
    resolved_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-identified_date']

class PestImage(models.Model):
    """Images for pest/disease issues"""
    pest_issue = models.ForeignKey(
        PestIssue,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='pest_issues/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

class JournalEntry(models.Model):
    """Garden observation journal"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='journal_entries')
    garden = models.ForeignKey(
        Garden,
        on_delete=models.CASCADE,
        related_name='journal_entries'
    )
    garden_plant = models.ForeignKey(
        GardenPlant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journal_entries'
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    date = models.DateField()
    weather_data = models.JSONField(null=True, blank=True)  # Snapshot from OpenWeatherMap
    tags = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name_plural = 'journal entries'
        indexes = [
            models.Index(fields=['user', '-date']),
        ]

class JournalImage(models.Model):
    """Images for journal entries"""
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='journal_entries/')
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

class PlantCareLibrary(models.Model):
    """Shared plant care reference data"""
    scientific_name = models.CharField(max_length=200, unique=True)
    common_names = models.JSONField(default=list)
    family = models.CharField(max_length=100, blank=True)
    sunlight = models.CharField(
        max_length=20,
        choices=[
            ('full_sun', 'Full Sun'),
            ('partial_shade', 'Partial Shade'),
            ('full_shade', 'Full Shade')
        ]
    )
    water_needs = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High')
        ]
    )
    soil_type = models.CharField(max_length=200, blank=True)
    hardiness_zones = models.JSONField(default=list)  # e.g., ["5a", "9b"]
    care_instructions = models.TextField(blank=True)
    watering_frequency_days = models.IntegerField(null=True)
    fertilizing_frequency_days = models.IntegerField(null=True)
    pruning_frequency_days = models.IntegerField(null=True)
    companion_plants = models.JSONField(default=list)
    enemy_plants = models.JSONField(default=list)
    common_pests = models.JSONField(default=list)
    common_diseases = models.JSONField(default=list)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scientific_name']
        verbose_name_plural = 'plant care library entries'
```

#### REST API Endpoints
```
# URLs: backend/apps/garden/urls.py

/api/v1/garden/
├── gardens/                           # List/Create gardens
│   ├── GET      List user's gardens
│   ├── POST     Create new garden
│   └── {id}/
│       ├── GET      Garden detail
│       ├── PUT      Update garden
│       ├── PATCH    Partial update
│       ├── DELETE   Delete garden
│       ├── plants/                    # Garden plants
│       │   ├── GET      List plants in garden
│       │   └── POST     Add plant to garden
│       ├── layout/                    # Visual layout data
│       │   ├── GET      Get layout JSON
│       │   └── PUT      Update layout
│       ├── tasks/                     # Garden-specific tasks
│       │   └── GET      List tasks for garden
│       └── journal/                   # Garden journal entries
│           └── GET      List entries for garden
│
├── plants/                            # Garden plants
│   ├── {id}/
│   │   ├── GET      Plant detail
│   │   ├── PUT      Update plant
│   │   ├── PATCH    Partial update
│   │   ├── DELETE   Remove plant
│   │   ├── reminders/               # Plant reminders
│   │   │   ├── GET      List reminders
│   │   │   └── POST     Create reminder
│   │   ├── pests/                   # Pest issues
│   │   │   ├── GET      List issues
│   │   │   └── POST     Report pest
│   │   ├── journal/                 # Plant-specific journal
│   │   │   └── GET      List entries
│   │   └── care-plan/               # AI care plan
│   │       └── POST     Generate AI care plan
│
├── reminders/                         # Care reminders
│   ├── GET      List user's reminders (filter: upcoming, overdue, completed)
│   ├── POST     Create reminder
│   └── {id}/
│       ├── GET      Reminder detail
│       ├── PUT      Update reminder
│       ├── DELETE   Delete reminder
│       ├── complete/                # Mark complete
│       │   └── POST     Complete reminder
│       └── skip/                    # Skip reminder
│           └── POST     Skip with reason
│
├── tasks/                             # Gardening tasks
│   ├── GET      List tasks (filter: season, category, completed)
│   ├── POST     Create task
│   ├── seasonal/                    # Pre-populated seasonal tasks
│   │   └── GET      Get tasks by season + climate zone
│   └── {id}/
│       ├── GET      Task detail
│       ├── PUT      Update task
│       ├── DELETE   Delete task
│       └── complete/                # Mark complete
│           └── POST     Complete task
│
├── pests/                             # Pest issues
│   ├── GET      List pest issues (filter: resolved, severity)
│   ├── POST     Report new pest
│   └── {id}/
│       ├── GET      Issue detail
│       ├── PUT      Update issue
│       ├── DELETE   Delete issue
│       ├── treatments/              # Treatment suggestions
│       │   └── POST     Get AI treatment recommendations
│       └── resolve/                 # Mark resolved
│           └── POST     Mark as resolved
│
├── journal/                           # Garden journal
│   ├── GET      List entries (filter: garden, plant, date range)
│   ├── POST     Create entry
│   └── {id}/
│       ├── GET      Entry detail
│       ├── PUT      Update entry
│       ├── DELETE   Delete entry
│       └── images/                  # Journal images
│           └── POST     Upload image
│
├── plant-library/                     # Plant care reference
│   ├── GET      List plants (paginated)
│   ├── POST     Add plant (staff only)
│   ├── search/                      # Full-text search
│   │   └── GET      Search by name, family, requirements
│   └── {id}/
│       ├── GET      Plant care detail
│       ├── PUT      Update (staff only)
│       └── companions/              # Companion plants
│           └── GET      Get compatible plants
│
├── weather/                           # Weather data
│   ├── current/                     # Current weather
│   │   └── GET      Get current weather (lat, lng)
│   └── forecast/                    # 5-day forecast
│       └── GET      Get forecast (lat, lng)
│
└── community/                         # Community gardens
    ├── GET      List public gardens (featured, popular)
    └── {id}/
        ├── GET      Public garden detail
        └── like/                    # Like garden
            └── POST     Toggle like
```

#### Services Layer
```python
# apps/garden/services/

class WeatherService:
    """OpenWeatherMap API integration"""

    @staticmethod
    def get_current_weather(lat: float, lng: float) -> dict:
        """
        Fetch current weather with Redis cache (1hr TTL)
        Returns: {temp, conditions, humidity, wind_speed, icon}
        """
        pass

    @staticmethod
    def get_5day_forecast(lat: float, lng: float) -> list:
        """
        Fetch 5-day forecast with Redis cache (1hr TTL)
        Returns: List of daily forecasts
        """
        pass

    @staticmethod
    def check_frost_risk(forecast: list) -> dict:
        """Check if frost expected in next 5 days"""
        pass

class SmartReminderService:
    """Weather-aware reminder adjustments"""

    @staticmethod
    def should_skip_watering(reminder: CareReminder, forecast: dict) -> tuple:
        """
        Check if watering should be skipped based on weather
        Returns: (should_skip: bool, reason: str)
        """
        pass

    @staticmethod
    def adjust_reminder_schedule(reminder: CareReminder) -> datetime:
        """Adjust next reminder date based on weather"""
        pass

class CompanionPlantingService:
    """Compatible plant suggestions"""

    @staticmethod
    def get_compatible_plants(plant_species: str) -> list:
        """Get companion plants from library"""
        pass

    @staticmethod
    def check_garden_compatibility(garden: Garden) -> dict:
        """
        Analyze entire garden for companion/enemy warnings
        Returns: {warnings: [], suggestions: []}
        """
        pass

class CareAssistantService:
    """AI-powered care recommendations"""

    @staticmethod
    def generate_care_plan(
        plant_species: str,
        location: dict,
        season: str,
        soil_type: str = None
    ) -> str:
        """
        Generate personalized care plan using Wagtail AI
        Reuses existing AIGenerationService infrastructure
        Returns: Markdown formatted care plan
        """
        pass

    @staticmethod
    def suggest_pest_treatment(pest_issue: PestIssue) -> str:
        """Generate AI treatment recommendations"""
        pass
```

#### Constants
```python
# apps/garden/constants.py

# Cache timeouts (seconds)
CACHE_TIMEOUT_WEATHER = 3600  # 1 hour
CACHE_TIMEOUT_CARE_PLAN = 2592000  # 30 days
CACHE_TIMEOUT_PLANT_LIBRARY = 86400  # 24 hours

# Cache key formats
CACHE_KEY_WEATHER_CURRENT = "garden:weather:current:{lat}:{lng}"
CACHE_KEY_WEATHER_FORECAST = "garden:weather:forecast:{lat}:{lng}"
CACHE_KEY_CARE_PLAN = "garden:care_plan:{species}:{climate}"

# File upload limits
MAX_GARDEN_PLANT_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_JOURNAL_IMAGES_PER_ENTRY = 10
MAX_PEST_IMAGES_PER_ISSUE = 6

# Allowed image types
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp']
ALLOWED_IMAGE_MIME_TYPES = [
    'image/jpeg',
    'image/png',
    'image/webp'
]

# Weather thresholds
FROST_TEMP_F = 32
HEATWAVE_TEMP_F = 95
HEAVY_RAIN_INCHES = 0.5

# Reminder defaults
DEFAULT_WATERING_INTERVAL_DAYS = 3
DEFAULT_FERTILIZING_INTERVAL_DAYS = 14
DEFAULT_PRUNING_INTERVAL_DAYS = 30

# Rate limits (using django-ratelimit)
RATE_LIMIT_GARDEN_CREATE = "10/day"
RATE_LIMIT_AI_CARE_PLAN = "5/hour"
RATE_LIMIT_WEATHER_API = "100/hour"
```

---

### Firebase Setup

#### Firestore Structure
```
collections/
├── users/
│   └── {userId}/
│       ├── reminders_pending/           # Real-time reminder sync
│       │   └── {reminderId}/
│       │       ├── plantName: string
│       │       ├── reminderType: string
│       │       ├── scheduledDate: timestamp
│       │       ├── gardenName: string
│       │       └── syncedToDjango: boolean
│       │
│       ├── notifications/               # Push notification queue
│       │   └── {notificationId}/
│       │       ├── type: string
│       │       ├── title: string
│       │       ├── body: string
│       │       ├── sent: boolean
│       │       └── createdAt: timestamp
│       │
│       └── preferences/                 # User notification settings
│           ├── enableReminders: boolean
│           ├── reminderTime: string  # "08:00"
│           ├── enableWeatherAlerts: boolean
│           └── timezone: string
│
├── weather_cache/                       # Cached weather data
│   └── {locationKey}/  # "{lat},{lng}" rounded to 2 decimals
│       ├── current: object
│       ├── forecast: array
│       └── updatedAt: timestamp
│
└── public_gardens/                      # Featured gardens (denormalized)
    └── {gardenId}/
        ├── userId: string
        ├── name: string
        ├── imageUrl: string
        ├── description: string
        ├── likes: number
        └── featuredAt: timestamp
```

#### Firestore Security Rules
```javascript
// firestore.rules

rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // Helper functions
    function isAuthenticated() {
      return request.auth != null;
    }

    function isOwner(userId) {
      return isAuthenticated() && request.auth.uid == userId;
    }

    // User reminders (private)
    match /users/{userId}/reminders_pending/{reminderId} {
      allow read, write: if isOwner(userId);
    }

    // User notifications (private)
    match /users/{userId}/notifications/{notificationId} {
      allow read: if isOwner(userId);
      allow write: if false;  // Only Cloud Functions can write
    }

    // User preferences (private)
    match /users/{userId}/preferences {
      allow read, write: if isOwner(userId);
    }

    // Weather cache (public read, function write)
    match /weather_cache/{locationKey} {
      allow read: if isAuthenticated();
      allow write: if false;  // Only Cloud Functions can write
    }

    // Public gardens (read-only for users)
    match /public_gardens/{gardenId} {
      allow read: if isAuthenticated();
      allow write: if false;  // Only Cloud Functions can write
    }
  }
}
```

#### Firebase Cloud Functions
```javascript
// functions/index.js

const functions = require('firebase-functions');
const admin = require('firebase-admin');
admin.initializeApp();

// Send daily reminder notifications (runs at 8 AM user local time)
exports.sendReminderNotifications = functions.pubsub
  .schedule('0 8 * * *')
  .timeZone('America/New_York')  // Configure per user timezone
  .onRun(async (context) => {
    const now = admin.firestore.Timestamp.now();

    // Query all users with pending reminders for today
    const usersSnapshot = await admin.firestore().collection('users').get();

    for (const userDoc of usersSnapshot.docs) {
      const userId = userDoc.id;
      const remindersRef = admin.firestore()
        .collection('users')
        .doc(userId)
        .collection('reminders_pending');

      const reminders = await remindersRef
        .where('scheduledDate', '<=', now)
        .get();

      if (reminders.empty) continue;

      // Create notification payload
      const reminderList = reminders.docs.map(doc => doc.data().plantName);
      const message = {
        notification: {
          title: `${reminders.size} Care Reminder${reminders.size > 1 ? 's' : ''}`,
          body: `Time to care for: ${reminderList.join(', ')}`
        },
        token: userDoc.data().fcmToken  // Firebase Cloud Messaging token
      };

      // Send notification
      try {
        await admin.messaging().send(message);

        // Log to notifications collection
        await admin.firestore()
          .collection('users')
          .doc(userId)
          .collection('notifications')
          .add({
            type: 'reminder',
            title: message.notification.title,
            body: message.notification.body,
            sent: true,
            createdAt: now
          });
      } catch (error) {
        console.error(`Failed to send notification to ${userId}:`, error);
      }
    }

    return null;
  });

// Sync completed reminders back to Django
exports.syncCompletedReminders = functions.firestore
  .document('users/{userId}/reminders_pending/{reminderId}')
  .onDelete(async (snap, context) => {
    const { userId, reminderId } = context.params;
    const reminderData = snap.data();

    // Call Django API to mark reminder complete
    const axios = require('axios');
    const djangoApiUrl = functions.config().django.api_url;

    try {
      await axios.post(
        `${djangoApiUrl}/api/v1/garden/reminders/${reminderId}/complete/`,
        {},
        {
          headers: {
            'Authorization': `Bearer ${functions.config().django.service_token}`
          }
        }
      );

      console.log(`Synced completion for reminder ${reminderId}`);
    } catch (error) {
      console.error(`Failed to sync reminder ${reminderId}:`, error);
    }

    return null;
  });

// Weather alerts (frost/heatwave)
exports.weatherAlerts = functions.pubsub
  .schedule('0 */6 * * *')  // Every 6 hours
  .onRun(async (context) => {
    // Query all gardens with location data
    const axios = require('axios');
    const db = admin.firestore();

    // In real implementation, fetch from Django API
    // For now, placeholder logic

    console.log('Weather alerts check completed');
    return null;
  });

// Update public gardens cache when garden visibility changes
exports.updatePublicGardens = functions.https.onCall(async (data, context) => {
  if (!context.auth) {
    throw new functions.https.HttpsError('unauthenticated', 'User must be authenticated');
  }

  const { gardenId, isPublic, gardenData } = data;

  if (isPublic) {
    // Add to public_gardens collection
    await admin.firestore()
      .collection('public_gardens')
      .doc(gardenId)
      .set({
        userId: context.auth.uid,
        ...gardenData,
        featuredAt: admin.firestore.FieldValue.serverTimestamp()
      });
  } else {
    // Remove from public_gardens collection
    await admin.firestore()
      .collection('public_gardens')
      .doc(gardenId)
      .delete();
  }

  return { success: true };
});
```

#### Django + Firebase Auth Integration
```python
# apps/users/services/firebase_service.py

import firebase_admin
from firebase_admin import auth, credentials
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed

class FirebaseAuthService:
    """Handle Firebase Authentication integration"""

    @staticmethod
    def initialize():
        """Initialize Firebase Admin SDK"""
        if not firebase_admin._apps:
            cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
            firebase_admin.initialize_app(cred)

    @staticmethod
    def create_custom_token(user_id: str) -> str:
        """
        Create Firebase custom token for Django user
        Called when user logs in via Django JWT
        """
        FirebaseAuthService.initialize()
        try:
            custom_token = auth.create_custom_token(str(user_id))
            return custom_token.decode('utf-8')
        except Exception as e:
            raise AuthenticationFailed(f"Failed to create Firebase token: {str(e)}")

    @staticmethod
    def verify_firebase_token(id_token: str) -> dict:
        """
        Verify Firebase ID token (for future Firebase-first auth)
        """
        FirebaseAuthService.initialize()
        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token
        except Exception as e:
            raise AuthenticationFailed(f"Invalid Firebase token: {str(e)}")


# New endpoint: apps/users/api/views.py

class FirebaseTokenView(APIView):
    """Generate Firebase custom token for authenticated user"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        POST /api/v1/auth/firebase-token/
        Returns: {firebase_token: str}
        """
        firebase_token = FirebaseAuthService.create_custom_token(request.user.id)
        return Response({
            'firebase_token': firebase_token
        })
```

---

## Phase 2: React Web UI (Week 2-4)

### Directory Structure
```
web/src/
├── pages/garden/
│   ├── GardenPlannerPage.tsx          # Main dashboard with overview
│   ├── GardenListPage.tsx             # All user gardens (grid view)
│   ├── GardenDetailPage.tsx           # Single garden detail
│   ├── GardenLayoutDesigner.tsx       # Drag-and-drop canvas designer
│   ├── ReminderCalendarPage.tsx       # Calendar view of reminders
│   ├── TaskManagementPage.tsx         # Seasonal task planner
│   ├── PestTrackerPage.tsx            # Pest/disease log
│   ├── JournalPage.tsx                # Garden journal entries
│   └── PlantLibraryPage.tsx           # Browse plant care library
│
├── components/garden/
│   ├── GardenCanvas.tsx               # HTML5 Canvas for layout
│   ├── PlantMarker.tsx                # Draggable plant marker
│   ├── ReminderCard.tsx               # Individual reminder UI
│   ├── ReminderList.tsx               # List of reminders
│   ├── WeatherWidget.tsx              # Weather display (current + forecast)
│   ├── TaskCard.tsx                   # Task checklist item
│   ├── TaskList.tsx                   # Filterable task list
│   ├── PestForm.tsx                   # Add/edit pest issue
│   ├── PestIssueCard.tsx              # Pest issue display
│   ├── JournalEntryCard.tsx           # Journal entry preview
│   ├── JournalEntryForm.tsx           # Rich text journal editor
│   ├── CompanionSuggestions.tsx       # Compatible plants display
│   ├── CareScheduleWizard.tsx         # Setup care reminders flow
│   ├── GardenCard.tsx                 # Garden grid item
│   ├── PlantCard.tsx                  # Plant detail card
│   ├── SeasonalTaskTemplates.tsx      # Pre-populated task library
│   └── PublicGardenGallery.tsx        # Community gardens showcase
│
├── services/
│   ├── gardenApi.ts                   # Django REST API calls
│   ├── firebaseService.ts             # Firebase Firestore operations
│   ├── weatherService.ts              # OpenWeatherMap API wrapper
│   └── notificationService.ts         # Push notification handling
│
├── types/garden.ts                     # TypeScript interfaces
├── hooks/
│   ├── useGardens.ts                  # Garden CRUD hooks
│   ├── useReminders.ts                # Reminder management hooks
│   ├── useWeather.ts                  # Weather data hooks
│   └── useFirebaseSync.ts             # Real-time sync hooks
│
└── utils/
    ├── gardenCalculations.ts          # Layout, spacing calculations
    └── companionPlanting.ts           # Compatibility logic
```

### TypeScript Interfaces
```typescript
// web/src/types/garden.ts

export interface Garden {
  id: number;
  user: number;
  name: string;
  description?: string;
  dimensions: {
    width: number;
    height: number;
    unit: 'ft' | 'm';
  };
  layout_data: {
    plants: PlantPosition[];
    gridSize?: number;
  };
  location?: {
    lat: number;
    lng: number;
    city: string;
  };
  climate_zone?: string;
  created_at: string;
  updated_at: string;
  visibility: 'private' | 'public';
  featured: boolean;
}

export interface GardenPlant {
  id: number;
  garden: number;
  plant_species?: number;
  common_name: string;
  scientific_name?: string;
  planted_date: string;
  position: {
    x: number;
    y: number;
  };
  image?: string;
  notes?: string;
  health_status: 'healthy' | 'needs_attention' | 'diseased' | 'dead';
  created_at: string;
  updated_at: string;
}

export interface PlantPosition {
  plantId: number;
  x: number;
  y: number;
  icon?: string;
}

export interface CareReminder {
  id: number;
  user: number;
  garden_plant: number;
  reminder_type: 'watering' | 'fertilizing' | 'pruning' | 'repotting' | 'pest_check' | 'custom';
  custom_type_name?: string;
  scheduled_date: string;
  recurring: boolean;
  interval_days?: number;
  completed: boolean;
  completed_at?: string;
  skipped: boolean;
  skip_reason?: string;
  notes?: string;
  notification_sent: boolean;
  created_at: string;
}

export interface Task {
  id: number;
  user: number;
  garden?: number;
  title: string;
  description?: string;
  due_date?: string;
  completed: boolean;
  completed_at?: string;
  category: 'planting' | 'maintenance' | 'harvesting' | 'preparation' | 'other';
  season?: 'spring' | 'summer' | 'fall' | 'winter' | 'year_round';
  priority: 'low' | 'medium' | 'high';
  created_at: string;
}

export interface PestIssue {
  id: number;
  user: number;
  garden_plant: number;
  pest_type: string;
  description: string;
  identified_date: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  treatment?: string;
  treatment_date?: string;
  resolved: boolean;
  resolved_date?: string;
  notes?: string;
  images: PestImage[];
  created_at: string;
  updated_at: string;
}

export interface PestImage {
  id: number;
  pest_issue: number;
  image: string;
  uploaded_at: string;
}

export interface JournalEntry {
  id: number;
  user: number;
  garden: number;
  garden_plant?: number;
  title: string;
  content: string;
  date: string;
  weather_data?: WeatherData;
  tags: string[];
  images: JournalImage[];
  created_at: string;
  updated_at: string;
}

export interface JournalImage {
  id: number;
  journal_entry: number;
  image: string;
  caption?: string;
  uploaded_at: string;
}

export interface PlantCareLibraryEntry {
  id: number;
  scientific_name: string;
  common_names: string[];
  family?: string;
  sunlight: 'full_sun' | 'partial_shade' | 'full_shade';
  water_needs: 'low' | 'medium' | 'high';
  soil_type?: string;
  hardiness_zones: string[];
  care_instructions?: string;
  watering_frequency_days?: number;
  fertilizing_frequency_days?: number;
  pruning_frequency_days?: number;
  companion_plants: string[];
  enemy_plants: string[];
  common_pests: string[];
  common_diseases: string[];
  notes?: string;
}

export interface WeatherData {
  temp: number;
  temp_min: number;
  temp_max: number;
  conditions: string;
  humidity: number;
  wind_speed: number;
  precipitation?: number;
  icon: string;
  date: string;
}

export interface WeatherForecast {
  current: WeatherData;
  forecast: WeatherData[];
  location: {
    city: string;
    lat: number;
    lng: number;
  };
}
```

### Key Components

#### 1. Garden Layout Designer
```typescript
// web/src/components/garden/GardenCanvas.tsx

import React, { useRef, useEffect, useState } from 'react';
import type { Garden, GardenPlant, PlantPosition } from '../../types/garden';

interface GardenCanvasProps {
  garden: Garden;
  plants: GardenPlant[];
  onLayoutUpdate: (layout: PlantPosition[]) => void;
  editable?: boolean;
}

export const GardenCanvas: React.FC<GardenCanvasProps> = ({
  garden,
  plants,
  onLayoutUpdate,
  editable = true
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [draggedPlant, setDraggedPlant] = useState<number | null>(null);
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  // Canvas rendering logic
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw grid
    drawGrid(ctx, garden.dimensions, scale, pan);

    // Draw plants
    plants.forEach(plant => {
      drawPlant(ctx, plant, scale, pan);
    });
  }, [garden, plants, scale, pan]);

  const drawGrid = (ctx: CanvasRenderingContext2D, dimensions: any, scale: number, pan: any) => {
    // Grid drawing implementation
    ctx.strokeStyle = '#e5e7eb';
    ctx.lineWidth = 1;

    const gridSize = 12; // 1 foot per grid square
    for (let x = 0; x <= dimensions.width; x += gridSize) {
      ctx.beginPath();
      ctx.moveTo((x * scale) + pan.x, pan.y);
      ctx.lineTo((x * scale) + pan.x, (dimensions.height * scale) + pan.y);
      ctx.stroke();
    }
    for (let y = 0; y <= dimensions.height; y += gridSize) {
      ctx.beginPath();
      ctx.moveTo(pan.x, (y * scale) + pan.y);
      ctx.lineTo((dimensions.width * scale) + pan.x, (y * scale) + pan.y);
      ctx.stroke();
    }
  };

  const drawPlant = (ctx: CanvasRenderingContext2D, plant: GardenPlant, scale: number, pan: any) => {
    const x = (plant.position.x * scale) + pan.x;
    const y = (plant.position.y * scale) + pan.y;

    // Draw plant marker (circle with icon)
    ctx.fillStyle = plant.health_status === 'healthy' ? '#10b981' : '#ef4444';
    ctx.beginPath();
    ctx.arc(x, y, 20, 0, 2 * Math.PI);
    ctx.fill();

    // Draw plant name
    ctx.fillStyle = '#000';
    ctx.font = '12px sans-serif';
    ctx.fillText(plant.common_name, x + 25, y + 5);
  };

  // Mouse event handlers for drag-and-drop
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!editable) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left - pan.x) / scale;
    const y = (e.clientY - rect.top - pan.y) / scale;

    // Find clicked plant
    const clickedPlant = plants.find(plant => {
      const dx = plant.position.x - x;
      const dy = plant.position.y - y;
      return Math.sqrt(dx*dx + dy*dy) < 20;
    });

    if (clickedPlant) {
      setDraggedPlant(clickedPlant.id);
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!draggedPlant) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left - pan.x) / scale;
    const y = (e.clientY - rect.top - pan.y) / scale;

    // Update plant position
    const updatedPlants = plants.map(plant =>
      plant.id === draggedPlant
        ? { ...plant, position: { x, y } }
        : plant
    );

    // Trigger layout update
    const layout = updatedPlants.map(p => ({
      plantId: p.id,
      x: p.position.x,
      y: p.position.y
    }));
    onLayoutUpdate(layout);
  };

  const handleMouseUp = () => {
    setDraggedPlant(null);
  };

  return (
    <div className="relative">
      <canvas
        ref={canvasRef}
        width={800}
        height={600}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        className="border border-gray-300 rounded-lg cursor-move"
      />

      {/* Zoom controls */}
      <div className="absolute top-4 right-4 flex gap-2">
        <button
          onClick={() => setScale(s => Math.min(s + 0.1, 2))}
          className="px-3 py-1 bg-white border rounded"
        >
          +
        </button>
        <button
          onClick={() => setScale(s => Math.max(s - 0.1, 0.5))}
          className="px-3 py-1 bg-white border rounded"
        >
          -
        </button>
      </div>
    </div>
  );
};
```

#### 2. Reminder Calendar
```typescript
// web/src/components/garden/ReminderCalendar.tsx

import React, { useState } from 'react';
import { Calendar, dateFnsLocalizer } from 'react-big-calendar';
import { format, parse, startOfWeek, getDay } from 'date-fns';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import type { CareReminder } from '../../types/garden';

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek,
  getDay,
  locales: { 'en-US': require('date-fns/locale/en-US') }
});

interface ReminderCalendarProps {
  reminders: CareReminder[];
  onReminderClick: (reminder: CareReminder) => void;
  onDateSelect: (date: Date) => void;
}

export const ReminderCalendar: React.FC<ReminderCalendarProps> = ({
  reminders,
  onReminderClick,
  onDateSelect
}) => {
  // Transform reminders to calendar events
  const events = reminders.map(reminder => ({
    id: reminder.id,
    title: `${reminder.reminder_type} - ${reminder.garden_plant}`,
    start: new Date(reminder.scheduled_date),
    end: new Date(reminder.scheduled_date),
    resource: reminder
  }));

  return (
    <div className="h-screen p-4">
      <Calendar
        localizer={localizer}
        events={events}
        startAccessor="start"
        endAccessor="end"
        onSelectEvent={(event) => onReminderClick(event.resource)}
        onSelectSlot={({ start }) => onDateSelect(start)}
        selectable
        views={['month', 'week', 'day']}
        eventPropGetter={(event) => ({
          style: {
            backgroundColor: event.resource.completed ? '#10b981' : '#3b82f6',
            borderRadius: '4px',
            opacity: event.resource.skipped ? 0.5 : 1
          }
        })}
      />
    </div>
  );
};
```

#### 3. Weather Widget
```typescript
// web/src/components/garden/WeatherWidget.tsx

import React, { useEffect, useState } from 'react';
import { weatherService } from '../../services/weatherService';
import type { WeatherForecast } from '../../types/garden';

interface WeatherWidgetProps {
  latitude: number;
  longitude: number;
}

export const WeatherWidget: React.FC<WeatherWidgetProps> = ({
  latitude,
  longitude
}) => {
  const [forecast, setForecast] = useState<WeatherForecast | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchWeather = async () => {
      try {
        const data = await weatherService.getForecast(latitude, longitude);
        setForecast(data);
      } catch (error) {
        console.error('Failed to fetch weather:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchWeather();
  }, [latitude, longitude]);

  if (loading) {
    return <div className="animate-pulse">Loading weather...</div>;
  }

  if (!forecast) {
    return <div>Weather data unavailable</div>;
  }

  return (
    <div className="bg-white rounded-lg shadow p-4">
      {/* Current weather */}
      <div className="mb-4">
        <h3 className="text-lg font-semibold">Current Weather</h3>
        <div className="flex items-center gap-4 mt-2">
          <img
            src={`https://openweathermap.org/img/wn/${forecast.current.icon}@2x.png`}
            alt={forecast.current.conditions}
            className="w-16 h-16"
          />
          <div>
            <div className="text-3xl font-bold">{Math.round(forecast.current.temp)}°F</div>
            <div className="text-gray-600">{forecast.current.conditions}</div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 mt-2 text-sm">
          <div>Humidity: {forecast.current.humidity}%</div>
          <div>Wind: {Math.round(forecast.current.wind_speed)} mph</div>
        </div>
      </div>

      {/* 5-day forecast */}
      <div>
        <h4 className="font-semibold mb-2">5-Day Forecast</h4>
        <div className="grid grid-cols-5 gap-2">
          {forecast.forecast.map((day, index) => (
            <div key={index} className="text-center">
              <div className="text-xs text-gray-600">
                {new Date(day.date).toLocaleDateString('en-US', { weekday: 'short' })}
              </div>
              <img
                src={`https://openweathermap.org/img/wn/${day.icon}.png`}
                alt={day.conditions}
                className="w-10 h-10 mx-auto"
              />
              <div className="text-sm font-semibold">
                {Math.round(day.temp_max)}°
              </div>
              <div className="text-xs text-gray-500">
                {Math.round(day.temp_min)}°
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Frost alert */}
      {forecast.forecast.some(day => day.temp_min <= 32) && (
        <div className="mt-4 p-2 bg-blue-100 border-l-4 border-blue-500 text-blue-700">
          ❄️ Frost warning: Protect sensitive plants!
        </div>
      )}
    </div>
  );
};
```

### API Services
```typescript
// web/src/services/gardenApi.ts

import axios from 'axios';
import type { Garden, GardenPlant, CareReminder, Task } from '../types/garden';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Add CSRF token to all requests (reuse existing pattern)
axios.interceptors.request.use((config) => {
  const csrfToken = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];

  if (csrfToken && config.headers) {
    config.headers['X-CSRFToken'] = csrfToken;
  }

  return config;
});

export const gardenApi = {
  // Gardens
  async listGardens(): Promise<Garden[]> {
    const { data } = await axios.get(`${API_BASE}/api/v1/garden/gardens/`);
    return data.results || data;
  },

  async getGarden(id: number): Promise<Garden> {
    const { data } = await axios.get(`${API_BASE}/api/v1/garden/gardens/${id}/`);
    return data;
  },

  async createGarden(garden: Partial<Garden>): Promise<Garden> {
    const { data } = await axios.post(`${API_BASE}/api/v1/garden/gardens/`, garden);
    return data;
  },

  async updateGarden(id: number, garden: Partial<Garden>): Promise<Garden> {
    const { data } = await axios.patch(`${API_BASE}/api/v1/garden/gardens/${id}/`, garden);
    return data;
  },

  async deleteGarden(id: number): Promise<void> {
    await axios.delete(`${API_BASE}/api/v1/garden/gardens/${id}/`);
  },

  // Plants
  async listGardenPlants(gardenId: number): Promise<GardenPlant[]> {
    const { data } = await axios.get(`${API_BASE}/api/v1/garden/gardens/${gardenId}/plants/`);
    return data.results || data;
  },

  async createGardenPlant(gardenId: number, plant: Partial<GardenPlant>): Promise<GardenPlant> {
    const { data } = await axios.post(`${API_BASE}/api/v1/garden/gardens/${gardenId}/plants/`, plant);
    return data;
  },

  async updatePlantPosition(plantId: number, position: { x: number; y: number }): Promise<GardenPlant> {
    const { data } = await axios.patch(`${API_BASE}/api/v1/garden/plants/${plantId}/`, { position });
    return data;
  },

  // Reminders
  async listReminders(filters?: { upcoming?: boolean; overdue?: boolean }): Promise<CareReminder[]> {
    const { data } = await axios.get(`${API_BASE}/api/v1/garden/reminders/`, { params: filters });
    return data.results || data;
  },

  async createReminder(reminder: Partial<CareReminder>): Promise<CareReminder> {
    const { data } = await axios.post(`${API_BASE}/api/v1/garden/reminders/`, reminder);
    return data;
  },

  async completeReminder(id: number): Promise<CareReminder> {
    const { data } = await axios.post(`${API_BASE}/api/v1/garden/reminders/${id}/complete/`);
    return data;
  },

  async skipReminder(id: number, reason: string): Promise<CareReminder> {
    const { data } = await axios.post(`${API_BASE}/api/v1/garden/reminders/${id}/skip/`, { reason });
    return data;
  },

  // AI Care Plan
  async generateCarePlan(plantId: number, options: {
    location: { lat: number; lng: number };
    season: string;
    soil_type?: string;
  }): Promise<{ care_plan: string }> {
    const { data } = await axios.post(`${API_BASE}/api/v1/garden/plants/${plantId}/care-plan/`, options);
    return data;
  }
};
```

```typescript
// web/src/services/firebaseService.ts

import { initializeApp } from 'firebase/app';
import {
  getFirestore,
  collection,
  query,
  where,
  onSnapshot,
  doc,
  setDoc,
  deleteDoc
} from 'firebase/firestore';
import { getAuth, signInWithCustomToken } from 'firebase/auth';
import type { CareReminder } from '../types/garden';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID
};

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);
const auth = getAuth(app);

export const firebaseService = {
  // Authenticate with custom token from Django
  async signIn(customToken: string) {
    await signInWithCustomToken(auth, customToken);
  },

  // Real-time reminder sync
  subscribeToReminders(userId: string, callback: (reminders: CareReminder[]) => void) {
    const q = query(
      collection(db, 'users', userId, 'reminders_pending')
    );

    return onSnapshot(q, (snapshot) => {
      const reminders = snapshot.docs.map(doc => ({
        id: parseInt(doc.id),
        ...doc.data()
      })) as CareReminder[];

      callback(reminders);
    });
  },

  // Sync reminder to Firebase
  async syncReminder(userId: string, reminder: CareReminder) {
    const reminderRef = doc(db, 'users', userId, 'reminders_pending', reminder.id.toString());
    await setDoc(reminderRef, {
      plantName: reminder.garden_plant, // Should fetch plant name
      reminderType: reminder.reminder_type,
      scheduledDate: new Date(reminder.scheduled_date),
      syncedToDjango: true
    });
  },

  // Remove completed reminder from Firebase
  async removeReminder(userId: string, reminderId: number) {
    const reminderRef = doc(db, 'users', userId, 'reminders_pending', reminderId.toString());
    await deleteDoc(reminderRef);
  }
};
```

```typescript
// web/src/services/weatherService.ts

import axios from 'axios';
import type { WeatherForecast, WeatherData } from '../types/garden';

const OPENWEATHER_API_KEY = import.meta.env.VITE_OPENWEATHER_API_KEY;
const API_BASE = 'https://api.openweathermap.org/data/2.5';

export const weatherService = {
  async getCurrent(lat: number, lng: number): Promise<WeatherData> {
    const { data } = await axios.get(`${API_BASE}/weather`, {
      params: {
        lat,
        lon: lng,
        appid: OPENWEATHER_API_KEY,
        units: 'imperial'
      }
    });

    return {
      temp: data.main.temp,
      temp_min: data.main.temp_min,
      temp_max: data.main.temp_max,
      conditions: data.weather[0].description,
      humidity: data.main.humidity,
      wind_speed: data.wind.speed,
      precipitation: data.rain?.['1h'] || 0,
      icon: data.weather[0].icon,
      date: new Date().toISOString()
    };
  },

  async getForecast(lat: number, lng: number): Promise<WeatherForecast> {
    const [current, forecast] = await Promise.all([
      this.getCurrent(lat, lng),
      axios.get(`${API_BASE}/forecast`, {
        params: {
          lat,
          lon: lng,
          appid: OPENWEATHER_API_KEY,
          units: 'imperial'
        }
      })
    ]);

    // Group forecast by day (5 days)
    const dailyForecasts: WeatherData[] = [];
    const seenDays = new Set<string>();

    forecast.data.list.forEach((item: any) => {
      const date = new Date(item.dt * 1000);
      const dateStr = date.toISOString().split('T')[0];

      if (!seenDays.has(dateStr) && dailyForecasts.length < 5) {
        seenDays.add(dateStr);
        dailyForecasts.push({
          temp: item.main.temp,
          temp_min: item.main.temp_min,
          temp_max: item.main.temp_max,
          conditions: item.weather[0].description,
          humidity: item.main.humidity,
          wind_speed: item.wind.speed,
          precipitation: item.rain?.['3h'] || 0,
          icon: item.weather[0].icon,
          date: date.toISOString()
        });
      }
    });

    return {
      current,
      forecast: dailyForecasts,
      location: {
        city: forecast.data.city.name,
        lat,
        lng
      }
    };
  }
};
```

---

## Phase 3: Integration Points (Week 4-5)

### Plant ID → Garden Integration
```typescript
// web/src/pages/plant-identification/ResultsPage.tsx (extend existing)

import { useState } from 'react';
import { gardenApi } from '../../services/gardenApi';
import type { Garden } from '../../types/garden';

// Add to existing component
const [showGardenModal, setShowGardenModal] = useState(false);
const [gardens, setGardens] = useState<Garden[]>([]);

const handleAddToGarden = async (plantData: PlantIdentificationResult) => {
  // Fetch user's gardens
  const userGardens = await gardenApi.listGardens();
  setGardens(userGardens);
  setShowGardenModal(true);
};

const saveToGarden = async (gardenId: number) => {
  // Create garden plant
  await gardenApi.createGardenPlant(gardenId, {
    common_name: selectedPlant.name,
    scientific_name: selectedPlant.scientificName,
    planted_date: new Date().toISOString().split('T')[0],
    position: { x: 0, y: 0 }, // User will position in designer
    image: selectedPlant.image
  });

  // Navigate to garden designer
  navigate(`/garden-planner/gardens/${gardenId}/layout`);
};
```

### AI Care Plan Generation
```python
# backend/apps/garden/services/care_assistant.py

from apps.blog.services.ai_generation_service import AIGenerationService
from django.core.cache import cache
from ..constants import CACHE_KEY_CARE_PLAN, CACHE_TIMEOUT_CARE_PLAN

class CareAssistantService:
    """AI-powered care recommendations using Wagtail AI"""

    @staticmethod
    def generate_care_plan(
        plant_species: str,
        location: dict,
        season: str,
        soil_type: str = None
    ) -> str:
        """Generate personalized care plan"""

        # Check cache first
        cache_key = CACHE_KEY_CARE_PLAN.format(
            species=plant_species,
            climate=f"{location.get('climate_zone', 'unknown')}"
        )
        cached_plan = cache.get(cache_key)
        if cached_plan:
            return cached_plan

        # Build prompt
        prompt = f"""
        Generate a detailed weekly care plan for {plant_species}.

        Location: {location.get('city', 'Unknown')} (Climate Zone: {location.get('climate_zone', 'Unknown')})
        Current Season: {season}
        Soil Type: {soil_type or 'Standard potting mix'}

        Include:
        - Watering schedule (frequency, amount, best time of day)
        - Fertilizing recommendations (type, frequency)
        - Sunlight requirements and positioning
        - Pruning/deadheading schedule
        - Common issues to watch for in this season
        - Month-by-month seasonal adjustments

        Format as markdown with clear sections.
        """

        # Generate using existing Wagtail AI service
        care_plan = AIGenerationService.generate_content(
            prompt=prompt,
            max_tokens=1000,
            temperature=0.7
        )

        # Cache for 30 days
        cache.set(cache_key, care_plan, CACHE_TIMEOUT_CARE_PLAN)

        return care_plan

    @staticmethod
    def suggest_pest_treatment(pest_issue) -> str:
        """Generate AI treatment recommendations"""

        prompt = f"""
        Provide treatment recommendations for this plant pest/disease:

        Pest Type: {pest_issue.pest_type}
        Plant: {pest_issue.garden_plant.common_name}
        Severity: {pest_issue.severity}
        Description: {pest_issue.description}

        Include:
        - Immediate action steps
        - Organic treatment options (preferred)
        - Chemical treatment options (if necessary)
        - Prevention strategies for the future
        - Timeline for expected results

        Format as markdown with clear sections.
        """

        treatment_plan = AIGenerationService.generate_content(
            prompt=prompt,
            max_tokens=800,
            temperature=0.7
        )

        return treatment_plan
```

### Forum Garden Showcase
```python
# backend/apps/forum/models.py (extend existing)

class ForumCategory(models.Model):
    # Add new category: "Garden Showcase"
    # In migration or admin: create category with slug "garden-showcase"
    pass

# New serializer for garden posts
class GardenShowcaseSerializer(serializers.ModelSerializer):
    garden_data = serializers.SerializerMethodField()

    def get_garden_data(self, obj):
        # Fetch linked garden from post metadata
        garden_id = obj.metadata.get('garden_id')
        if garden_id:
            from apps.garden.models import Garden
            garden = Garden.objects.get(id=garden_id, visibility='public')
            return {
                'id': garden.id,
                'name': garden.name,
                'plant_count': garden.plants.count(),
                'layout_image': garden.layout_data.get('screenshot')
            }
        return None

    class Meta:
        model = Post
        fields = ['id', 'title', 'content', 'garden_data', 'created_at', 'likes']
```

---

## Phase 4: Firebase + Django Sync (Week 5)

### Real-Time Reminder Workflow
```typescript
// web/src/hooks/useFirebaseSync.ts

import { useEffect, useState } from 'react';
import { firebaseService } from '../services/firebaseService';
import { gardenApi } from '../services/gardenApi';
import type { CareReminder } from '../types/garden';

export const useFirebaseSync = (userId: string) => {
  const [reminders, setReminders] = useState<CareReminder[]>([]);

  useEffect(() => {
    // Subscribe to real-time updates from Firebase
    const unsubscribe = firebaseService.subscribeToReminders(userId, (firebaseReminders) => {
      setReminders(firebaseReminders);
    });

    return () => unsubscribe();
  }, [userId]);

  const completeReminder = async (reminderId: number) => {
    // 1. Update Django (source of truth)
    await gardenApi.completeReminder(reminderId);

    // 2. Remove from Firebase (triggers sync back)
    await firebaseService.removeReminder(userId, reminderId);
  };

  const createReminder = async (reminder: Partial<CareReminder>) => {
    // 1. Create in Django
    const newReminder = await gardenApi.createReminder(reminder);

    // 2. Sync to Firebase for real-time updates
    await firebaseService.syncReminder(userId, newReminder);
  };

  return { reminders, completeReminder, createReminder };
};
```

---

## Phase 5: Testing & Security (Week 6)

### Django Tests
```python
# backend/apps/garden/tests/test_garden_api.py

from django.test import TestCase
from rest_framework.test import APIClient
from apps.users.models import User
from ..models import Garden, GardenPlant

class GardenAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

    def test_create_garden(self):
        """Test garden creation"""
        data = {
            'name': 'My Vegetable Garden',
            'dimensions': {'width': 20, 'height': 10, 'unit': 'ft'},
            'visibility': 'private'
        }
        response = self.client.post('/api/v1/garden/gardens/', data, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Garden.objects.count(), 1)
        self.assertEqual(Garden.objects.first().name, 'My Vegetable Garden')

    def test_add_plant_to_garden(self):
        """Test adding plant to garden"""
        garden = Garden.objects.create(
            user=self.user,
            name='Test Garden',
            dimensions={'width': 10, 'height': 10, 'unit': 'ft'}
        )

        data = {
            'common_name': 'Tomato',
            'planted_date': '2024-05-01',
            'position': {'x': 5, 'y': 5}
        }
        response = self.client.post(
            f'/api/v1/garden/gardens/{garden.id}/plants/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(garden.plants.count(), 1)

    def test_rate_limiting_ai_care_plan(self):
        """Test rate limiting on AI endpoint"""
        garden = Garden.objects.create(user=self.user, name='Test')
        plant = GardenPlant.objects.create(
            garden=garden,
            common_name='Tomato',
            planted_date='2024-05-01',
            position={'x': 0, 'y': 0}
        )

        # Make 6 requests (limit is 5/hour)
        for i in range(6):
            response = self.client.post(
                f'/api/v1/garden/plants/{plant.id}/care-plan/',
                {'location': {'lat': 40.7, 'lng': -74}, 'season': 'spring'}
            )

            if i < 5:
                self.assertEqual(response.status_code, 200)
            else:
                self.assertEqual(response.status_code, 429)  # Too many requests
```

### React Component Tests
```typescript
// web/src/components/garden/__tests__/GardenCanvas.test.tsx

import { render, screen, fireEvent } from '@testing-library/react';
import { GardenCanvas } from '../GardenCanvas';
import type { Garden, GardenPlant } from '../../../types/garden';

describe('GardenCanvas', () => {
  const mockGarden: Garden = {
    id: 1,
    user: 1,
    name: 'Test Garden',
    dimensions: { width: 20, height: 10, unit: 'ft' },
    layout_data: { plants: [] },
    created_at: '2024-01-01',
    updated_at: '2024-01-01',
    visibility: 'private',
    featured: false
  };

  const mockPlants: GardenPlant[] = [
    {
      id: 1,
      garden: 1,
      common_name: 'Tomato',
      planted_date: '2024-05-01',
      position: { x: 5, y: 5 },
      health_status: 'healthy',
      created_at: '2024-01-01',
      updated_at: '2024-01-01'
    }
  ];

  test('renders canvas with grid', () => {
    render(
      <GardenCanvas
        garden={mockGarden}
        plants={mockPlants}
        onLayoutUpdate={jest.fn()}
      />
    );

    const canvas = screen.getByRole('img');  // Canvas has implicit img role
    expect(canvas).toBeInTheDocument();
  });

  test('allows dragging plant marker', () => {
    const mockUpdate = jest.fn();

    render(
      <GardenCanvas
        garden={mockGarden}
        plants={mockPlants}
        onLayoutUpdate={mockUpdate}
      />
    );

    const canvas = screen.getByRole('img');

    // Simulate drag
    fireEvent.mouseDown(canvas, { clientX: 100, clientY: 100 });
    fireEvent.mouseMove(canvas, { clientX: 150, clientY: 150 });
    fireEvent.mouseUp(canvas);

    expect(mockUpdate).toHaveBeenCalled();
  });
});
```

---

## Phase 6: Future Flutter Mobile (Post-6 weeks)

### Flutter Garden Feature Structure
```dart
// plant_community_mobile/lib/features/garden/

models/
├── garden.dart
├── garden_plant.dart
└── care_reminder.dart

providers/
├── garden_provider.dart
├── reminder_provider.dart
└── weather_provider.dart

screens/
├── garden_list_screen.dart
├── garden_detail_screen.dart
├── garden_planner_screen.dart
└── reminder_calendar_screen.dart

widgets/
├── garden_card.dart
├── plant_marker.dart
└── reminder_item.dart

services/
├── garden_api_service.dart
└── reminder_notification_service.dart
```

---

## Deployment Checklist

### Environment Variables

**Django (.env)**:
```bash
# Existing
SECRET_KEY=...
DEBUG=False
DATABASE_URL=...
REDIS_URL=...

# New for garden planner
OPENWEATHER_API_KEY=your_openweathermap_api_key
FIREBASE_SERVICE_ACCOUNT_PATH=/path/to/serviceAccountKey.json
```

**React (.env)**:
```bash
# Existing
VITE_API_URL=https://your-api.com

# New for Firebase
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=...
VITE_FIREBASE_PROJECT_ID=...
VITE_FIREBASE_STORAGE_BUCKET=...
VITE_FIREBASE_MESSAGING_SENDER_ID=...
VITE_FIREBASE_APP_ID=...

# Weather
VITE_OPENWEATHER_API_KEY=...
```

### Database Migrations
```bash
cd backend
python manage.py makemigrations garden
python manage.py migrate garden
```

### Firebase Deployment
```bash
cd backend/firebase_functions
npm install
firebase deploy --only functions
firebase deploy --only firestore:rules
```

### Static Files
```bash
# Django
python manage.py collectstatic

# React
cd web
npm run build
```

---

## Success Metrics

### Technical Performance
- ✅ Garden designer drag latency <100ms
- ✅ Weather API response <2s (fresh), <50ms (cached)
- ✅ Reminder calendar render time <200ms
- ✅ Firebase sync success rate >99%

### User Engagement
- ✅ 80%+ plant ID users save to garden
- ✅ 50%+ daily reminder completion rate
- ✅ 30%+ gardens shared publicly
- ✅ 5+ journal entries per active user/month

### Code Quality
- ✅ 100+ comprehensive tests (Django + React)
- ✅ Zero TypeScript compilation errors
- ✅ All security patterns implemented (CSRF, file upload, rate limiting)
- ✅ Pattern documentation complete

---

## Timeline Summary

**Week 1**: Django models, migrations, basic API endpoints
**Week 2**: Services layer (weather, AI, companion planting), Firebase setup
**Week 3**: React pages (8 pages), TypeScript interfaces
**Week 4**: React components (canvas, calendar, widgets), Firebase integration
**Week 5**: Plant ID integration, AI care plans, forum showcase
**Week 6**: Testing, security audit, documentation, deployment

**Total**: 6 weeks to production-ready MVP

---

## Next Steps

1. ✅ Review and approve this plan
2. ✅ Set up OpenWeatherMap API account (free tier: 1000 calls/day)
3. ✅ Set up Firebase project (free tier sufficient for MVP)
4. ✅ Begin Phase 1: Django backend implementation
5. ✅ Weekly progress reviews and adjustments

Ready to start implementing! 🚀
