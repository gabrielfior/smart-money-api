#!/bin/bash

# Deployment helper script

echo "🚀 Smart Money API Deployment"
echo "=============================="
echo ""

# Check available deployment tools
check_tool() {
    if command -v $1 &> /dev/null; then
        echo "✅ $1 found"
        return 0
    else
        echo "❌ $1 not found"
        return 1
    fi
}

echo "Checking deployment tools..."
RENDER=$(check_tool render)
RAILWAY=$(check_tool railway)
FLY=$(check_tool flyctl)
DOCKER=$(check_tool docker)

echo ""
echo "Options:"
echo ""

if $RENDER; then
    echo "1. Render (render.com)"
    echo "   - Sign up: https://render.com"
    echo "   - Run: render deploy"
    echo "   - Free tier available"
    echo ""
fi

if $RAILWAY; then
    echo "2. Railway (railway.app)"
    echo "   - Sign up: https://railway.app"
    echo "   - Run: railway up"
    echo "   - Free tier available"
    echo ""
fi

if $FLY; then
    echo "3. Fly.io"
    echo "   - Sign up: https://fly.io"
    echo "   - Run: fly launch"
    echo "   - Pay-as-you-go"
    echo ""
fi

if $DOCKER; then
    echo "4. Docker (self-hosted)"
    echo "   - Build: docker build -t smart-money-api ."
    echo "   - Run: docker run -p 8000:8000 --env-file .env smart-money-api"
    echo ""
fi

echo "Recommended: Railway or Render (easiest for Python/FastAPI)"
echo ""
echo "Required environment variables:"
echo "  - SUPABASE_URL"
echo "  - SUPABASE_KEY"
echo "  - JUPITER_KEY"
echo "  - OPENROUTER_KEY"
echo ""
echo "Set these in your deployment platform's dashboard."