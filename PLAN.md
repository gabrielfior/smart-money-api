# Hackathon Plan: Smart Money Market Intelligence API

## Goal

Build an AI agent API that provides **semantic market discovery + trader reputation intelligence** over Jupiter Prediction markets. Agents ask natural language questions like *"What do top traders think about AI regulation?"* and get back marketContext + topTraderSignals + consensus.

## Prize Tracks Targeted

| Prize | Amount | Deadline | Skills Needed | Notes |
|-------|--------|----------|---------------|-------|
| **Tether** | $10k (1st $5k) | May 13, 2026 | Frontend/Backend/Blockchain/Mobile | General track |
| **Dune** | $6k (1st) | May 27, 2026 | Backend | "Frontier Data Sidetrack" — 4 submissions, low competition |

## Data Source

### Jupiter Prediction API

- **API Base**: `https://api.jup.ag/prediction/v1`
- **Requires**: API key from developers.jup.ag/portal
- **Key Endpoints**:
  - `/events/search?query=` — keyword search (LIMITATION: no semantic)
  - `/markets/{marketId}` — pricing, volume, resolution criteria
  - `/positions?ownerPubkey=` — individual P&L, win rate, contracts
  - `/history?ownerPubkey=` — realized P&L, fees, fill prices
  - `/leaderboards` — rankings (if available)

## The Core Problem

1. **Semantic Gap**: Jupiter's keyword search fails on *"AI reg"* → *"Will AI be regulated?"* — no semantic/RAG
2. **Trader Reputation Gap**: No aggregate trader intelligence — can't answer *"who's actually good?"*

## The Product

### API Design (pay.sh compatible)

| Method | Path | Input | Output |
|--------|------|-------|--------|
| `POST` | `/brief` | `{ query: "What do top traders think about AI regulation?" }` | `{ markets: [...], topTraders: [...], consensus: "65% YES" }` |
| `POST` | `/search` | `{ query: "markets about government oversight of AI" }` | semantically matched events |
| `GET` | `/trader/{pubkey}` | — | `{ pnl, winRate, volume, categories, recentPositions }` |
| `GET` | `/health` | — | `{ status: "ok" }` |

### Pricing
- Pay-per-call via pay.sh (HTTP 402)
- Brief: $0.01–0.05 per query
- Search: $0.005 per query
- Sandbox mode for testing

### How It Works

```
User Query → Semantic Embedding → Match Markets → Aggregate Top Traders → Return Brief
     │              │                    │                │
     └──────────────┴────────────────────┴────────────────┘
                          RAG Layer + Trader Ranking
```

1. **Semantic Search** — Embed event titles/metadata/rules → find markets beyond keywords
2. **Trader Aggregation** — Rank traders by P&L/winRate in matched markets
3. **Brief Generation** — LLM compiles marketContext + topTraderSignals + consensus

## Architecture

```
Agent → pay.sh gateway → Brief API
                       ├── Semantic Search (embeddings)
                       ├── Jupiter API (markets, positions)
                       ├── Trader Ranker (aggregate P&L)
                       └── Brief Generator (LLM)
```

## Tech Stack

- **Runtime**: Python (FastAPI) — pay.sh compatible
- **Database**: Supabase (PostgreSQL) — for trader stats, position caching
- **Vector DB**: Chroma DB (local/Docker) — for semantic embeddings
- **Embeddings**: OpenRouter `nvidia/llama-nemotron-embed-vl-1b-v2:free`
- **LLM**: OpenRouter (free tier) — for brief generation
- **Payment**: pay.sh — HTTP 402, sandbox mode for testing
- **Data**: Jupiter Prediction API

## Key Differentiators

1. **Semantic > Keyword** — RAG over market metadata beats Jupiter's `/events/search`
2. **Trader Reputation** — Aggregate track records from position history
3. **Network Effect** — More queries → better rankings

## Open Questions (Answered)

1. **Vector DB**: Chroma DB local via Docker
2. **Trader Ranking**: Pure P&L (no risk adjustment)
3. **Frontend**: API-only via pay.sh
4. **Pricing**: Free (sandbox mode)

## Next Steps

1. Create Supabase project + get API keys
2. Set up Python/FastAPI project scaffold
3. Start Chroma DB (Docker)
4. Get Jupiter API key
5. Implement semantic search over event metadata
6. Build trader ranking from position data
7. Wire up pay.sh (sandbox)
8. Deploy + test