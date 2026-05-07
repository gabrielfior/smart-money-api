import os
import json
import hashlib
from typing import List, Optional, Dict, Any
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
JUPITER_KEY = os.getenv("JUPITER_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

app = FastAPI(
    title="Smart Money Market Intelligence API",
    description="Semantic market discovery + trader reputation for Jupiter Prediction",
    version="0.1.0"
)

# Models
class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    provider: Optional[str] = None  # "polymarket", "kalshi", or None for both

class BriefRequest(BaseModel):
    query: str
    include_traders: bool = True

# Supabase client
async def supabase_request(method: str, path: str, data: dict = None, params: dict = None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    async with httpx.AsyncClient() as client:
        if method == "GET":
            response = await client.get(url, headers=headers, params=params)
        elif method == "POST":
            response = await client.post(url, headers=headers, json=data)
        elif method == "DELETE":
            response = await client.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()

# OpenRouter embedding
async def get_embedding(text: str) -> List[float]:
    url = "https://openrouter.ai/api/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "nvidia/llama-nemotron-embed-vl-1b-v2:free",
        "input": text
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        result = response.json()
        return result["data"][0]["embedding"]

# Vector search in Supabase
async def vector_search(embedding: List[float], limit: int = 10, provider: Optional[str] = None):
    """Search events using pgvector similarity"""
    # Use RPC for vector search
    url = f"{SUPABASE_URL}/rest/v1/rpc/match_events"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "query_embedding": embedding,
        "match_threshold": 0.5,
        "match_count": limit
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        if response.status_code >= 400:
            # Fallback to simple search if RPC not set up
            return await fallback_search(embedding, limit, provider)
        return response.json()

async def fallback_search(embedding: List[float], limit: int = 10, provider: Optional[str] = None):
    """Fallback: return events with markets"""
    # Build query params
    params = {
        "limit": limit,
        "select": "event_id,title,category,subcategory,tags,rules,metadata,provider,created_at"
    }
    if provider:
        params["provider"] = f"eq.{provider}"
    
    # Get events (without embedding)
    events = await supabase_request("GET", "events", params=params)
    
    # Get markets for these events
    event_ids = [e["event_id"] for e in events]
    if event_ids:
        market_params = {
            "event_id": f"in.({','.join(event_ids)})",
            "select": "market_id,event_id,title,status,result,buy_yes_price,buy_no_price,volume,close_time,provider"
        }
        markets = await supabase_request("GET", "markets", params=market_params)
        
        # Attach markets to events
        for event in events:
            event["markets"] = [m for m in markets if m["event_id"] == event["event_id"]]
    
    return events

# Endpoints
@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})

@app.post("/search")
async def search(req: SearchRequest):
    """Semantic search for events with live market prices"""
    try:
        # Get embedding for query
        embedding = await get_embedding(req.query)
        
        # Search in Supabase
        results = await vector_search(embedding, req.limit, req.provider)
        
        # Strip embeddings and attach markets
        clean_results = []
        for r in results:
            clean = {k: v for k, v in r.items() if k != "embedding"}
            clean_results.append(clean)
        
        return {
            "source": "semantic",
            "query": req.query,
            "provider": req.provider or "all",
            "count": len(clean_results),
            "results": clean_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/brief")
async def brief(req: BriefRequest):
    """Full intelligence brief"""
    return {"message": "Brief endpoint - WIP", "query": req.query}

@app.get("/trader/{pubkey}")
async def get_trader(pubkey: str):
    """Get trader reputation"""
    return {"message": "Trader endpoint - WIP", "pubkey": pubkey}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)