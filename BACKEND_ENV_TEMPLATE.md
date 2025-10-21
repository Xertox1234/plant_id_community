# Backend API Keys Configuration

## Copy this to: /existing_implementation/backend/.env

# ===================================
# Plant Identification APIs
# ===================================

# Kindwise (Plant.id) - Primary AI identification with disease detection
PLANT_ID_API_KEY=W3YvEk2rx8g7Ko3fa8hKrlPJVqQeT2muIfikhKqvSBnaIUkXd4

# PlantNet - Open source plant identification + care instructions
PLANTNET_API_KEY=2b10XCJNMzrPYiojVsddjK0n

# ===================================
# Usage Strategy
# ===================================
# 1. Use Kindwise (Plant.id) for initial identification + disease detection
# 2. Use PlantNet to supplement with care instructions for common plants
# 3. Combine results to provide comprehensive plant information

# ===================================
# Backend Configuration
# ===================================
DEBUG=True
SECRET_KEY=your-secret-key-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=plant_community
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

# Frontend URL (for CORS)
FRONTEND_URL=http://localhost:5173
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# API Configuration
ENABLE_PLANT_ID=True
ENABLE_PLANTNET=True
ENABLE_CARE_INSTRUCTIONS=True
