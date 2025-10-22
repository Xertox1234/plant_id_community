#!/bin/bash

# Plant ID Community - Security Setup Script
# This script helps you set up secure environment variables

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$BACKEND_DIR/.env"
ENV_TEMPLATE="$BACKEND_DIR/.env.template"

echo "═══════════════════════════════════════════════════════════════"
echo "  Plant ID Community - Secure Environment Setup"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check if .env already exists
if [ -f "$ENV_FILE" ]; then
    echo "⚠️  WARNING: .env file already exists!"
    echo "   Location: $ENV_FILE"
    echo ""
    read -p "   Do you want to overwrite it? (yes/no): " overwrite
    if [ "$overwrite" != "yes" ]; then
        echo "   Aborting. No changes made."
        exit 0
    fi
    mv "$ENV_FILE" "$ENV_FILE.backup.$(date +%Y%m%d_%H%M%S)"
    echo "   Backed up existing .env file"
    echo ""
fi

# Copy template
echo "📄 Creating .env from template..."
cp "$ENV_TEMPLATE" "$ENV_FILE"

# Generate SECRET_KEY
echo "🔐 Generating secure SECRET_KEY..."
SECRET_KEY=$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")

if [ -z "$SECRET_KEY" ]; then
    echo "❌ ERROR: Failed to generate SECRET_KEY"
    echo "   Make sure Django is installed: pip install django"
    exit 1
fi

# Update SECRET_KEY in .env
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" "$ENV_FILE"
else
    # Linux
    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" "$ENV_FILE"
fi

echo "✅ SECRET_KEY generated and saved"
echo ""

# Prompt for API keys
echo "═══════════════════════════════════════════════════════════════"
echo "  API Keys Configuration"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "⚠️  IMPORTANT: You need to obtain these API keys:"
echo ""
echo "1️⃣  Plant.id API Key"
echo "   • Get it at: https://plant.id/"
echo "   • Sign up for free account"
echo "   • Navigate to API Keys section"
echo "   • Copy your API key"
echo ""
echo "2️⃣  PlantNet API Key"
echo "   • Get it at: https://my.plantnet.org/"
echo "   • Sign up for free account"
echo "   • Navigate to API Keys section"
echo "   • Generate new API key"
echo ""

read -p "Do you have your API keys ready? (yes/no): " has_keys

if [ "$has_keys" == "yes" ]; then
    echo ""
    read -p "Enter your Plant.id API Key: " PLANT_ID_KEY
    read -p "Enter your PlantNet API Key: " PLANTNET_KEY

    # Validate keys are not empty
    if [ -z "$PLANT_ID_KEY" ] || [ -z "$PLANTNET_KEY" ]; then
        echo "❌ ERROR: API keys cannot be empty"
        exit 1
    fi

    # Update API keys in .env
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/PLANT_ID_API_KEY=.*/PLANT_ID_API_KEY=$PLANT_ID_KEY/" "$ENV_FILE"
        sed -i '' "s/PLANTNET_API_KEY=.*/PLANTNET_API_KEY=$PLANTNET_KEY/" "$ENV_FILE"
    else
        sed -i "s/PLANT_ID_API_KEY=.*/PLANT_ID_API_KEY=$PLANT_ID_KEY/" "$ENV_FILE"
        sed -i "s/PLANTNET_API_KEY=.*/PLANTNET_API_KEY=$PLANTNET_KEY/" "$ENV_FILE"
    fi

    echo "✅ API keys saved to .env"
else
    echo "⚠️  Skipping API key setup"
    echo "   You'll need to manually edit .env and add your keys"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Setup Complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "✅ Environment file created: $ENV_FILE"
echo "✅ SECRET_KEY generated"
echo ""

if [ "$has_keys" == "yes" ]; then
    echo "✅ API keys configured"
    echo ""
    echo "🚀 You can now start the server:"
    echo "   cd $BACKEND_DIR"
    echo "   python simple_server.py"
else
    echo "⚠️  Next steps:"
    echo "   1. Edit $ENV_FILE"
    echo "   2. Add your API keys"
    echo "   3. Start server: python simple_server.py"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Security Reminders"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "🔒 NEVER commit .env to git"
echo "🔒 NEVER share your API keys publicly"
echo "🔒 Rotate API keys regularly (every 90 days)"
echo "🔒 Use different keys for development and production"
echo ""
echo "📝 For production deployment, see:"
echo "   $BACKEND_DIR/SECURITY_FIXES_WEEK1.md"
echo ""
