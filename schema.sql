-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Events table with pre-computed embeddings
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    subtitle TEXT,
    category TEXT,
    subcategory TEXT,
    rules TEXT,
    metadata JSONB,
    embedding VECTOR(384), -- 384 dims for small models
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Traders table (aggregated rankings)
CREATE TABLE IF NOT EXISTS traders (
    pubkey TEXT PRIMARY KEY,
    total_pnl NUMERIC DEFAULT 0,
    total_volume NUMERIC DEFAULT 0,
    win_rate NUMERIC DEFAULT 0,
    positions_count INTEGER DEFAULT 0,
    categories JSONB DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Cached query results for speed
CREATE TABLE IF NOT EXISTS query_cache (
    query_hash TEXT PRIMARY KEY,
    query_text TEXT NOT NULL,
    results JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);