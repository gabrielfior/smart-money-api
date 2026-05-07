-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Events table with pre-computed embeddings (2048 dims for OpenRouter model)
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    subtitle TEXT,
    category TEXT,
    subcategory TEXT,
    tags TEXT[],
    rules TEXT,
    metadata JSONB,
    embedding VECTOR(2048),
    provider TEXT DEFAULT 'polymarket',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Markets table (live prices, frequent updates)
CREATE TABLE IF NOT EXISTS markets (
    market_id TEXT PRIMARY KEY,
    event_id TEXT REFERENCES events(event_id),
    title TEXT,
    status TEXT,
    result TEXT,
    buy_yes_price NUMERIC,
    buy_no_price NUMERIC,
    sell_yes_price NUMERIC,
    sell_no_price NUMERIC,
    volume NUMERIC DEFAULT 0,
    rules TEXT,
    open_time TIMESTAMP,
    close_time TIMESTAMP,
    provider TEXT DEFAULT 'polymarket',
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

-- Vector similarity search function
CREATE OR REPLACE FUNCTION match_events(
    query_embedding VECTOR(2048),
    match_threshold FLOAT,
    match_count INT
)
RETURNS TABLE(
    event_id TEXT,
    title TEXT,
    category TEXT,
    subcategory TEXT,
    tags TEXT[],
    rules TEXT,
    metadata JSONB,
    provider TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.event_id,
        e.title,
        e.category,
        e.subcategory,
        e.tags,
        e.rules,
        e.metadata,
        e.provider,
        1 - (e.embedding <=> query_embedding) AS similarity
    FROM events e
    WHERE 1 - (e.embedding <=> query_embedding) > match_threshold
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_events_embedding ON events USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_events_provider ON events(provider);
CREATE INDEX IF NOT EXISTS idx_markets_event_id ON markets(event_id);
CREATE INDEX IF NOT EXISTS idx_markets_provider ON markets(provider);
