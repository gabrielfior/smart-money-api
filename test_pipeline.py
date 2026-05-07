import os
import httpx
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
JUPITER_KEY = os.getenv("JUPITER_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

async def fetch_jupiter_events(provider="polymarket", limit=10):
    """Fetch events from Jupiter Prediction API"""
    url = f"https://api.jup.ag/prediction/v1/events?limit={limit}&includeMarkets=true&provider={provider}"
    headers = {"x-api-key": JUPITER_KEY}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        return response.json()

async def get_embedding(text: str):
    """Get embedding from OpenRouter"""
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

async def store_event(event_id, title, category, subcategory, tags, rules, metadata, embedding, provider):
    """Store event in Supabase"""
    url = f"{SUPABASE_URL}/rest/v1/events"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    data = {
        "event_id": event_id,
        "title": title,
        "category": category,
        "subcategory": subcategory,
        "tags": tags,
        "rules": rules,
        "metadata": metadata,
        "embedding": embedding,
        "provider": provider
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        if response.status_code >= 400:
            print(f"Error storing event: {response.status_code} - {response.text}")
            return None
        return response.json()

async def store_market(market_id, event_id, title, status, result, pricing, rules, open_time, close_time, provider):
    """Store market in Supabase"""
    url = f"{SUPABASE_URL}/rest/v1/markets"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    # Convert micro USD to actual USD
    buy_yes = pricing.get("buyYesPriceUsd", 0) / 1_000_000 if pricing.get("buyYesPriceUsd") else None
    buy_no = pricing.get("buyNoPriceUsd", 0) / 1_000_000 if pricing.get("buyNoPriceUsd") else None
    sell_yes = pricing.get("sellYesPriceUsd", 0) / 1_000_000 if pricing.get("sellYesPriceUsd") else None
    sell_no = pricing.get("sellNoPriceUsd", 0) / 1_000_000 if pricing.get("sellNoPriceUsd") else None
    volume = pricing.get("volume", 0)
    
    # Convert timestamps
    ot = datetime.fromtimestamp(open_time) if open_time else None
    ct = datetime.fromtimestamp(close_time) if close_time else None
    
    data = {
        "market_id": market_id,
        "event_id": event_id,
        "title": title,
        "status": status,
        "result": result,
        "buy_yes_price": buy_yes,
        "buy_no_price": buy_no,
        "sell_yes_price": sell_yes,
        "sell_no_price": sell_no,
        "volume": volume,
        "rules": rules,
        "open_time": ot.isoformat() if ot else None,
        "close_time": ct.isoformat() if ct else None,
        "provider": provider
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        if response.status_code >= 400:
            print(f"Error storing market: {response.status_code} - {response.text}")
            return None
        return response.json()

async def process_provider(provider, limit=5):
    """Process events from a single provider"""
    print(f"\n{'='*50}")
    print(f"Processing {provider.upper()}...")
    print(f"{'='*50}")
    
    events_data = await fetch_jupiter_events(provider=provider, limit=limit)
    
    if "data" not in events_data:
        print(f"Error fetching {provider}:", events_data)
        return 0, 0
    
    events = events_data["data"]
    print(f"✅ Fetched {len(events)} {provider} events")
    
    event_count = 0
    market_count = 0
    
    for i, event in enumerate(events[:limit]):
        event_id = event["eventId"]
        title = event["metadata"]["title"]
        category = event["category"]
        subcategory = event["subcategory"]
        tags = event.get("tags", [])
        metadata = event.get("metadata", {})
        
        # Use first market's rules as event rules
        rules = ""
        markets = event.get("markets", [])
        if markets and len(markets) > 0:
            rules = markets[0].get("rulesPrimary", "")[:500]
        
        print(f"\n  [{i+1}/{limit}] {provider}: {title[:50]}...")
        
        try:
            # Embed event
            embedding = await get_embedding(f"{title} {rules}")
            
            # Store event
            result = await store_event(event_id, title, category, subcategory, tags, rules, metadata, embedding, provider)
            
            if result:
                event_count += 1
                print(f"       ✅ Event stored: {event_id}")
                
                # Store markets for this event
                for j, market in enumerate(markets[:3]):
                    market_id = market["marketId"]
                    market_title = market.get("metadata", {}).get("title", market_id)
                    status = market["status"]
                    result_val = market.get("result", "")
                    pricing = market.get("pricing", {})
                    market_rules = market.get("rulesPrimary", "")[:200]
                    open_time = market.get("openTime")
                    close_time = market.get("closeTime")
                    
                    m_result = await store_market(
                        market_id, event_id, market_title, status, result_val,
                        pricing, market_rules, open_time, close_time, provider
                    )
                    
                    if m_result:
                        market_count += 1
                        price = pricing.get('buyYesPriceUsd', 0) / 1_000_000
                        print(f"       ✅ Market {j+1}: {market_title[:40]}... (${price:.3f} YES)")
            else:
                print(f"       ❌ Failed to store event")
        except Exception as e:
            print(f"       ❌ Error: {e}")
    
    return event_count, market_count

async def test_pipeline():
    """Fetch from BOTH Polymarket and Kalshi"""
    print("🚀 Fetching prediction markets from Jupiter API")
    print("   (Polymarket + Kalshi)")
    
    total_events = 0
    total_markets = 0
    
    # Process Polymarket
    e, m = await process_provider("polymarket", limit=5)
    total_events += e
    total_markets += m
    
    # Process Kalshi
    e, m = await process_provider("kalshi", limit=5)
    total_events += e
    total_markets += m
    
    print(f"\n{'='*50}")
    print(f"✅ COMPLETE!")
    print(f"{'='*50}")
    print(f"Total events: {total_events}")
    print(f"Total markets: {total_markets}")
    
    # Verify
    print("\n📊 Database summary:")
    async with httpx.AsyncClient() as client:
        # Count by provider
        for provider in ["polymarket", "kalshi"]:
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/events?provider=eq.{provider}&select=*",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
            )
            events = len(response.json())
            
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/markets?provider=eq.{provider}&select=*",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
            )
            markets = len(response.json())
            
            print(f"   {provider}: {events} events, {markets} markets")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_pipeline())