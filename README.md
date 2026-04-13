# Card Price Tracker Backend

## eBay provider configuration

The backend now uses a provider abstraction for sold listing sources.

### `LISTING_PROVIDER` options

- `mock` (default): Uses sample/mock sold listings.
- `ebay_browse`: Enables the official eBay Browse/OAuth scaffold, then falls back to mock sold listings because sold-comps are not yet wired to a supported Browse sold endpoint.

## Required environment variables

When `LISTING_PROVIDER=ebay_browse`, set:

- `EBAY_CLIENT_ID` (required)
- `EBAY_CLIENT_SECRET` (required)
- `EBAY_ENVIRONMENT` (`sandbox` default, or `production`)
- `EBAY_MARKETPLACE_ID` (optional, default `EBAY_US`)
- `EBAY_OAUTH_SCOPE` (optional, default `https://api.ebay.com/oauth/api_scope`)

## Run locally

```bash
cd /workspace/card-price-tracker
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

## Quick API checks

```bash
curl -X POST http://127.0.0.1:8000/search/match \
  -H 'content-type: application/json' \
  -d '{"query":"2024 Topps Chrome Elly De La Cruz #44 /299 auto"}'

curl -X POST http://127.0.0.1:8000/search/structured \
  -H 'content-type: application/json' \
  -d '{"set_name":"2024 Topps Chrome","player_name":"Elly De La Cruz","card_type":"Base","numbering":"/299"}'
```

Responses preserve grouped buckets and include a `message` when provider fallback/status is relevant.
