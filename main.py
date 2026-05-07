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
    limit: int = 5

class TraderRequest(BaseModel):
    pubkey: str

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

# OpenRouter LLM completion
async def llm_complete(prompt: str, model: str = "nvidia/nemotron-3-super-120b-a12b:free") -> str:
    """Generate text completion using OpenRouter"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a market intelligence analyst. Provide concise, data-driven briefs."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 800
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data, timeout=30.0)
        result = response.json()
        if "choices" not in result:
            error_msg = result.get("error", {}).get("message", "Unknown LLM error")
            raise HTTPException(status_code=500, detail=f"LLM error: {error_msg}")
        return result["choices"][0]["message"]["content"]

# Jupiter API helpers
async def jupiter_request(endpoint: str, params: dict = None):
    """Make authenticated request to Jupiter API"""
    url = f"https://api.jup.ag/prediction/v1/{endpoint}"
    headers = {"x-api-key": JUPITER_KEY}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=f"Jupiter API error: {response.text}")
        return response.json()

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
        results = response.json()
        # Filter by provider if specified
        if provider:
            results = [r for r in results if r.get("provider") == provider]
        return results

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

# Cache helpers
async def get_cached_result(query_hash: str) -> Optional[dict]:
    """Get cached search result"""
    try:
        results = await supabase_request("GET", "query_cache", params={
            "query_hash": f"eq.{query_hash}",
            "select": "results"
        })
        if results and len(results) > 0:
            return results[0]["results"]
    except:
        pass
    return None

async def cache_result(query_hash: str, query_text: str, results: dict):
    """Cache search result"""
    try:
        await supabase_request("POST", "query_cache", data={
            "query_hash": query_hash,
            "query_text": query_text,
            "results": results
        })
    except:
        pass

# Endpoints
@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "version": "0.1.0"})

@app.post("/search")
async def search(req: SearchRequest):
    """Semantic search for events with live market prices"""
    try:
        # Check cache
        query_hash = hashlib.md5(f"{req.query}:{req.provider}:{req.limit}".encode()).hexdigest()
        cached = await get_cached_result(query_hash)
        if cached:
            return {**cached, "cached": True}
        
        # Get embedding for query
        embedding = await get_embedding(req.query)
        
        # Search in Supabase
        results = await vector_search(embedding, req.limit, req.provider)
        
        # Strip embeddings and attach markets
        clean_results = []
        event_ids = []
        for r in results:
            clean = {k: v for k, v in r.items() if k != "embedding"}
            clean_results.append(clean)
            event_ids.append(r.get("event_id"))
        
        # Fetch markets for these events
        if event_ids:
            market_params = {
                "event_id": f"in.({','.join(event_ids)})",
                "select": "market_id,event_id,title,status,result,buy_yes_price,buy_no_price,volume,close_time,provider"
            }
            try:
                markets = await supabase_request("GET", "markets", params=market_params)
                # Attach markets to events
                markets_by_event = {}
                for m in markets:
                    eid = m["event_id"]
                    if eid not in markets_by_event:
                        markets_by_event[eid] = []
                    markets_by_event[eid].append(m)
                
                for event in clean_results:
                    event["markets"] = markets_by_event.get(event.get("event_id"), [])
            except:
                pass
        
        response = {
            "source": "semantic",
            "query": req.query,
            "provider": req.provider or "all",
            "count": len(clean_results),
            "results": clean_results
        }
        
        # Cache result
        await cache_result(query_hash, req.query, response)
        
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/brief")
async def brief(req: BriefRequest):
    """Generate intelligence brief combining market search + trader data"""
    try:
        # Step 1: Search for relevant events
        embedding = await get_embedding(req.query)
        events = await vector_search(embedding, req.limit, None)
        
        # Step 2: Get markets for events
        event_ids = [e.get("event_id") for e in events if e.get("event_id")]
        markets_data = []
        if event_ids:
            try:
                market_params = {
                    "event_id": f"in.({','.join(event_ids)})",
                    "select": "market_id,event_id,title,buy_yes_price,buy_no_price,volume,provider"
                }
                markets_data = await supabase_request("GET", "markets", params=market_params)
            except:
                pass
        
        # Step 3: Get top traders (from our DB or Jupiter)
        top_traders = []
        if req.include_traders:
            try:
                traders = await supabase_request("GET", "traders", params={
                    "order": "total_pnl.desc",
                    "limit": 5,
                    "select": "pubkey,total_pnl,win_rate,positions_count"
                })
                top_traders = traders
            except:
                pass
        
        # Step 4: Build prompt for LLM
        events_summary = []
        for e in events[:3]:
            event_markets = [m for m in markets_data if m.get("event_id") == e.get("event_id")]
            prices = []
            for m in event_markets[:2]:
                yes_price = m.get("buy_yes_price")
                if yes_price:
                    prices.append(f"${float(yes_price):.3f} YES")
            events_summary.append({
                "title": e.get("title", "Unknown"),
                "category": e.get("category", ""),
                "prices": prices,
                "volume": sum(float(m.get("volume", 0) or 0) for m in event_markets)
            })
        
        prompt = f"""Generate a market intelligence brief for: "{req.query}"

TOP EVENTS:
"""
        for i, e in enumerate(events_summary, 1):
            prompt += f"{i}. {e['title']} ({e['category']})\n"
            if e['prices']:
                prompt += f"   Prices: {', '.join(e['prices'])}\n"
            if e['volume']:
                prompt += f"   Volume: ${e['volume']:,.0f}\n"
        
        if top_traders:
            prompt += "\nTOP TRADERS:\n"
            for i, t in enumerate(top_traders[:3], 1):
                pnl = float(t.get("total_pnl", 0) or 0)
                win_rate = float(t.get("win_rate", 0) or 0) * 100
                prompt += f"{i}. {t['pubkey'][:16]}... P&L: ${pnl:,.2f}, Win Rate: {win_rate:.1f}%\n"
        
        prompt += """
Provide:
1. KEY INSIGHTS (2-3 bullet points)
2. MARKET SENTIMENT (bullish/bearish/neutral with reasoning)
3. RISK FACTORS (1-2 sentences)
4. SMART MONEY SIGNAL (what top traders are doing, if data available)

Keep it concise and actionable."""
        
        # Step 5: Generate brief
        brief_text = await llm_complete(prompt)
        
        return {
            "query": req.query,
            "events_found": len(events),
            "traders_analyzed": len(top_traders),
            "brief": brief_text,
            "events": [{"title": e.get("title"), "category": e.get("category")} for e in events[:3]]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/trader/{pubkey}")
async def get_trader(pubkey: str):
    """Get trader reputation and positions from Jupiter"""
    try:
        # Fetch positions from Jupiter (use ownerPubkey)
        positions_data = await jupiter_request("positions", {"ownerPubkey": pubkey})
        
        # Fetch trade history (use ownerPubkey)
        history_data = await jupiter_request("history", {"ownerPubkey": pubkey})
        
        # Calculate metrics
        positions = positions_data.get("data", [])
        history = history_data.get("data", [])
        
        total_pnl = sum(float(p.get("pnl", 0) or 0) for p in positions)
        total_volume = sum(float(p.get("volume", 0) or 0) for p in positions)
        
        # Calculate win rate from history
        wins = 0
        total_trades = 0
        for h in history:
            pnl = h.get("pnl")
            if pnl is not None:
                total_trades += 1
                if float(pnl) > 0:
                    wins += 1
        
        win_rate = wins / total_trades if total_trades > 0 else 0
        
        # Store/update trader in our DB
        try:
            await supabase_request("POST", "traders", data={
                "pubkey": pubkey,
                "total_pnl": total_pnl,
                "total_volume": total_volume,
                "win_rate": win_rate,
                "positions_count": len(positions),
                "updated_at": "now()"
            })
        except:
            # Trader might already exist, try update
            pass
        
        return {
            "pubkey": pubkey,
            "total_pnl": total_pnl,
            "total_volume": total_volume,
            "win_rate": win_rate,
            "positions_count": len(positions),
            "trades_count": total_trades,
            "positions": positions[:5],  # Return top 5 positions
            "recent_history": history[:5]  # Return recent 5 trades
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/traders/sync")
async def sync_traders():
    """Fetch top whales from Jupiter leaderboards and store in DB"""
    try:
        # Fetch leaderboards from Jupiter
        leaderboard = await jupiter_request("leaderboards")
        traders_data = leaderboard.get("data", [])
        
        stored = 0
        errors = 0
        
        for trader in traders_data:
            try:
                pubkey = trader.get("ownerPubkey")
                if not pubkey:
                    continue
                
                # Convert string values to float
                pnl = float(trader.get("realizedPnlUsd", 0) or 0) / 1_000_000  # Convert from micro USD
                volume = float(trader.get("totalVolumeUsd", 0) or 0) / 1_000_000
                win_rate = float(trader.get("winRatePct", 0) or 0) / 100
                positions_count = int(trader.get("predictionsCount", 0) or 0)
                
                # Store in DB (upsert)
                try:
                    await supabase_request("POST", "traders", data={
                        "pubkey": pubkey,
                        "total_pnl": pnl,
                        "total_volume": volume,
                        "win_rate": win_rate,
                        "positions_count": positions_count,
                        "updated_at": "now()"
                    })
                    stored += 1
                except:
                    # Already exists or error
                    errors += 1
            except Exception as e:
                errors += 1
                continue
        
        return {
            "message": f"Synced {stored} traders from Jupiter leaderboards",
            "stored": stored,
            "errors": errors,
            "total_from_api": len(traders_data)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/traders/top")
async def get_top_traders(limit: int = 10):
    """Get top traders by P&L from our database"""
    try:
        traders = await supabase_request("GET", "traders", params={
            "order": "total_pnl.desc",
            "limit": limit,
            "select": "pubkey,total_pnl,total_volume,win_rate,positions_count,updated_at"
        })
        return {
            "count": len(traders),
            "traders": traders
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
