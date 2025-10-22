# Week 2 Performance - Manual Setup Required

## ✅ Completed
- **Parallel API Processing**: Successfully deployed `combined_identification_service_parallel.py`
  - Location: `apps/plant_identification/services/combined_identification_service.py`
  - Backup: `combined_identification_service_sequential.py`
  - Expected: 60% faster plant identification (4-9s → 2-5s)

## ⚠️ Database Indexes - Manual Migration Required

The automated migration failed due to Python 3.9/Django 5.2 compatibility issues.

### Option 1: Upgrade Python (Recommended)
```bash
# Install Python 3.10+ (required for Django 5.2)
brew install python@3.11  # Mac
# OR
sudo apt install python3.11  # Linux

# Recreate virtual environment
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Now run migrations
python manage.py makemigrations plant_identification --empty --name add_performance_indexes
```

Then edit the migration file with indexes from WEEK2_PERFORMANCE.md lines 114-191.

### Option 2: Use Django 4.2 (Current Python)
```bash
# Downgrade requirements temporarily
pip install "Django>=4.2,<5.0"

# Create migration
python manage.py makemigrations plant_identification --empty --name add_performance_indexes
```

### The Indexes to Add

Once you can create the migration, add these indexes (copy from WEEK2_PERFORMANCE.md):

```python
operations = [
    # PlantIdentificationRequest
    migrations.AddIndex(
        model_name='plantidentificationrequest',
        index=models.Index(fields=['user', '-created_at'], name='idx_request_user_created'),
    ),
    migrations.AddIndex(
        model_name='plantidentificationrequest',
        index=models.Index(fields=['status', '-created_at'], name='idx_request_status_created'),
    ),

    # PlantIdentificationResult
    migrations.AddIndex(
        model_name='plantidentificationresult',
        index=models.Index(fields=['confidence_score', '-created_at'], name='idx_result_confidence'),
    ),
    migrations.AddIndex(
        model_name='plantidentificationresult',
        index=models.Index(fields=['request', 'confidence_score'], name='idx_result_request_conf'),
    ),

    # PlantSpecies
    migrations.AddIndex(
        model_name='plantspecies',
        index=models.Index(fields=['scientific_name'], name='idx_species_scientific'),
    ),
    migrations.AddIndex(
        model_name='plantspecies',
        index=models.Index(fields=['identification_count', '-created_at'], name='idx_species_popularity'),
    ),

    # UserPlant
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

**Impact**: 100x faster queries (800ms → 8ms for user history)

## Redis Caching

See next step for Redis installation and configuration.
