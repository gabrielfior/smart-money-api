#!/usr/bin/env python3
"""
Refresh market prices from Jupiter Prediction API.
Run this as a cron job every 5-15 minutes to keep prices fresh.
Fetches ~100 open markets total (50 per provider max).
"""
import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
JUPITER_KEY = os.getenv("JUPITER_KEY")

PROVIDERS = ["polymarket", "kalshi"]
MAX_MARKETS_PER_PROVIDER = 50

def fetch_jupiter_events(provider="polymarket", limit=20):
    """Fetch events with markets from Jupiter"""
    url = "https://api.jup.ag/prediction/v1/events"
    headers = {"x-api-key": JUPITER_KEY}
    params = {
        "limit": limit,
        "includeMarkets": "true",
        "provider": provider
    }
    
    response = httpx.get(url, headers=headers, params=params, timeout=30.0)
    return response.json()

def update_market_prices(market_id, pricing, status, result):
    """Update market prices in Supabase"""
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
    
    data = {
        "buy_yes_price": buy_yes,
        "buy_no_price": buy_no,
        "sell_yes_price": sell_yes,
        "sell_no_price": sell_no,
        "volume": volume,
        "status": status,
        "result": result,
        "updated_at": "now()"
    }
    
    # Use PATCH to update specific market
    patch_url = f"{url}?market_id=eq.{market_id}"
    
    try:
        response = httpx.patch(patch_url, headers=headers, json=data, timeout=10.0)
        return response.status_code in (200, 204)
    except Exception:
        return False

def refresh_provider(provider, max_markets=50):
    """Refresh prices for a single provider, only open markets"""
    print(f"\n{'='*60}")
    print(f"Refreshing {provider.upper()} prices...")
    print(f"{'='*60}")
    
    data = fetch_jupiter_events(provider=provider, limit=20)
    
    if "data" not in data:
        print(f"❌ Error fetching {provider}: {data}")
        return 0, 0
    
    events = data["data"]
    print(f"    Fetched {len(events)} events")
    
    updated = 0
    skipped = 0
    markets_processed = 0
    
    for event in events:
        if markets_processed >= max_markets:
            print(f"    Reached max markets limit ({max_markets})")
            break
            
        markets = event.get("markets", [])
        
        for market in markets:
            if markets_processed >= max_markets:
                break
                
            market_id = market.get("marketId")
            pricing = market.get("pricing", {})
            status = market.get("status")
            result = market.get("result", "")
            
            # Skip closed markets
            if status != "open":
                skipped += 1
                continue
            
            if not market_id or not pricing:
                skipped += 1
                continue
            
            success = update_market_prices(market_id, pricing, status, result)
            if success:
                updated += 1
                if updated <= 5:
                    buy_yes = pricing.get("buyYesPriceUsd", 0) / 1_000_000
                    print(f"  ✅ {market_id}: ${buy_yes:.3f} YES (vol: {pricing.get('volume', 0):,})")
            else:
                skipped += 1
            
            markets_processed += 1
    
    print(f"    Processed: {markets_processed}, Updated: {updated}, Skipped: {skipped}")
    return updated, skipped

def main():
    """Main refresh routine"""
    from datetime import datetime
    
    print("🔄 Starting market price refresh...")
    print(f"   Time: {datetime.now().isoformat()}")
    
    total_updated = 0
    total_skipped = 0
    
    for provider in PROVIDERS:
        updated, skipped = refresh_provider(provider, max_markets=MAX_MARKETS_PER_PROVIDER)
        total_updated += updated
        total_skipped += skipped
    
    print(f"\n{'='*60}")
    print(f"✅ REFRESH COMPLETE")
    print(f"{'='*60}")
    print(f"Markets updated: {total_updated}")
    print(f"Markets skipped: {total_skipped}")
    
    return 0 if total_updated > 0 else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
