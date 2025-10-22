#!/bin/bash

# Week 2 Performance Optimization - Quick Apply Script
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
SERVICES_DIR="$BACKEND_DIR/apps/plant_identification/services"

echo "═══════════════════════════════════════════════════════════════"
echo "  Plant ID Community - Week 2 Performance Optimization"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Step 1: Backup old service
echo "📦 Step 1: Backing up sequential service..."
if [ -f "$SERVICES_DIR/combined_identification_service.py" ]; then
    cp "$SERVICES_DIR/combined_identification_service.py" \
       "$SERVICES_DIR/combined_identification_service_sequential_backup_$(date +%Y%m%d_%H%M%S).py"
    echo "✅ Backup created"
else
    echo "⚠️  Original service not found (skipping backup)"
fi
echo ""

# Step 2: Deploy parallel version
echo "⚡ Step 2: Deploying parallel API processing..."
if [ -f "$SERVICES_DIR/combined_identification_service_parallel.py" ]; then
    mv "$SERVICES_DIR/combined_identification_service.py" \
       "$SERVICES_DIR/combined_identification_service_sequential.py" 2>/dev/null || true

    cp "$SERVICES_DIR/combined_identification_service_parallel.py" \
       "$SERVICES_DIR/combined_identification_service.py"

    echo "✅ Parallel processing deployed"
    echo "   Old version saved as: combined_identification_service_sequential.py"
else
    echo "❌ ERROR: Parallel version not found"
    echo "   Expected: $SERVICES_DIR/combined_identification_service_parallel.py"
    exit 1
fi
echo ""

# Step 3: Test import
echo "🧪 Step 3: Testing new service import..."
cd "$BACKEND_DIR"
source venv/bin/activate 2>/dev/null || true

python3 -c "
from apps.plant_identification.services.combined_identification_service import CombinedPlantIdentificationService
service = CombinedPlantIdentificationService()
print('✅ Service imports successfully')
print('   Plant.id:', 'configured' if service.plant_id else 'not configured')
print('   PlantNet:', 'configured' if service.plantnet else 'not configured')
" || {
    echo "❌ ERROR: Service import failed"
    echo "   Rolling back..."
    mv "$SERVICES_DIR/combined_identification_service_sequential.py" \
       "$SERVICES_DIR/combined_identification_service.py"
    exit 1
}
echo ""

# Step 4: Database indexes
echo "🗄️  Step 4: Preparing database index migration..."
echo "   Run this command to create the migration:"
echo ""
echo "   python manage.py makemigrations plant_identification --empty --name add_performance_indexes"
echo ""
echo "   Then edit the migration file and add indexes from WEEK2_PERFORMANCE.md"
echo "   Finally run: python manage.py migrate"
echo ""

# Step 5: Redis setup (optional)
echo "💾 Step 5: Redis caching (optional)"
echo "   To enable caching:"
echo "   1. Install Redis: brew install redis (Mac) or apt-get install redis-server (Linux)"
echo "   2. Start Redis: brew services start redis"
echo "   3. Install django-redis: pip install django-redis"
echo "   4. Add CACHES config to settings (see WEEK2_PERFORMANCE.md)"
echo ""

# Success
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Week 2 Performance Optimization Applied!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📊 Expected Performance Improvements:"
echo "   • Plant identification: 60% faster (4-9s → 2-5s)"
echo "   • Database queries: 100x faster (with indexes)"
echo "   • Upload time: 85% faster (with frontend compression)"
echo ""
echo "🧪 Test the improvement:"
echo "   time curl -X POST http://localhost:8000/api/plant-identification/identify/ \\"
echo "     -F \"image=@test_plant.jpg\""
echo ""
echo "📖 Next steps: See WEEK2_PERFORMANCE.md for:"
echo "   • Database index migration"
echo "   • Redis caching setup"
echo "   • Frontend image compression"
echo ""
