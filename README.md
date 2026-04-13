# Card Price Tracker Backend

## Listing provider architecture

The backend uses a provider-based listing integration:

- `backend.listing_providers.ListingProvider`: provider interface
- `backend.listing_providers.ProviderSearchResult`: provider response contract (`listings`, `provider_name`, `message`)
- `backend.listing_providers.MockListingProvider`: default sample/mock sold listings provider
- `backend.listing_providers.EbayBrowseProvider`: official eBay OAuth + Browse scaffold provider
- `backend.listing_providers.FallbackListingProvider`: keeps app usable by falling back to mock listings when the primary provider cannot return sold comps

Matcher/scoring/bucket grouping and structured `normalized_query` flow are unchanged.

## Provider selection

Set `LISTING_PROVIDER`:

- `mock` (default): uses sample/mock sold listings
- `ebay_browse`: uses official eBay OAuth/Browse scaffold and then falls back to mock sold listings (because real sold/completed comps are not currently returned through this supported path)

## Required eBay environment variables

When `LISTING_PROVIDER=ebay_browse`, these are required:

- `EBAY_CLIENT_ID`
- `EBAY_CLIENT_SECRET`

Optional eBay settings:

- `EBAY_ENVIRONMENT` (`sandbox` default, or `production`)
- `EBAY_MARKETPLACE_ID` (default `EBAY_US`)
- `EBAY_OAUTH_SCOPE` (default `https://api.ebay.com/oauth/api_scope`)

## Local run

```bash
cd /workspace/card-price-tracker
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

## Run the frontend locally

```bash
cd /workspace/card-price-tracker/frontend
python -m http.server 5173
```

Open `http://127.0.0.1:5173`.

## Local provider-mode checks

### Mock mode (default)

```bash
LISTING_PROVIDER=mock uvicorn backend.main:app --reload
curl -X POST http://127.0.0.1:8000/search/match \
  -H 'content-type: application/json' \
  -d '{"query":"2024 Topps Chrome Elly De La Cruz #44 /299 auto"}'
```

Expected behavior: grouped buckets are populated from mock sold listings.

### eBay Browse scaffold mode

```bash
export LISTING_PROVIDER=ebay_browse
export EBAY_CLIENT_ID='your-client-id'
export EBAY_CLIENT_SECRET='your-client-secret'
uvicorn backend.main:app --reload
curl -X POST http://127.0.0.1:8000/search/structured \
  -H 'content-type: application/json' \
  -d '{"set_name":"2024 Topps Chrome","player_name":"Elly De La Cruz","card_type":"Base","numbering":"/299"}'
```

Expected behavior:

- app stays up
- response includes provider status/message explaining sold comps are not returned from this official path
- app falls back to mock listings so matcher/grouped buckets still work

## Current sold-comp status

**Real sold/completed comps are _not_ currently implemented through an official supported eBay API path in this project.**

`EbayBrowseProvider` is an OAuth/Browse scaffold and intentionally does not pretend live sold comps are available.
