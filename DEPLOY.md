# Deployment Guide

## Quick Start

### Option 1: Render (Recommended - Free Tier)

1. Sign up at [render.com](https://render.com)
2. Connect your GitHub repo
3. Create a new Web Service
4. Select Python runtime
5. Set environment variables in dashboard:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `JUPITER_KEY`
   - `OPENROUTER_KEY`
6. Deploy!

### Option 2: Railway

1. Sign up at [railway.app](https://railway.app)
2. Install CLI: `npm i -g @railway/cli`
3. Login: `railway login`
4. Deploy: `railway up`

### Option 3: Docker (Self-hosted)

```bash
# Build
docker build -t smart-money-api .

# Run with env vars
docker run -p 8000:8000 \
  -e SUPABASE_URL=your_url \
  -e SUPABASE_KEY=your_key \
  -e JUPITER_KEY=your_key \
  -e OPENROUTER_KEY=your_key \
  smart-money-api
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | ✅ | Your Supabase project URL |
| `SUPABASE_KEY` | ✅ | Supabase service role key |
| `JUPITER_KEY` | ✅ | Jupiter Prediction API key |
| `OPENROUTER_KEY` | ✅ | OpenRouter API key |
| `PORT` | ❌ | Server port (default: 8000) |

## After Deployment

Test your API:
```bash
curl https://your-app.render.com/health

curl -X POST https://your-app.render.com/search \
  -H "Content-Type: application/json" \
  -d '{"query": "bitcoin", "limit": 2}'
```

## pay.sh Gateway

For production with payments, run the pay.sh gateway:
```bash
pay server start pay-provider.yml
```

Or deploy it separately pointing to your API URL.