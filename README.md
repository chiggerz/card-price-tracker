# Card Price Tracker Backend

## Listing provider architecture

The backend uses a provider-based listing integration:

- `backend.listing_providers.ListingProvider`: provider interface
- `backend.listing_providers.ProviderSearchResult`: provider response contract (`listings`, `provider_name`, `message`)
- `backend.listing_providers.MockListingProvider`: default sample/mock sold listings provider
- `backend.listing_providers.EbayBrowseProvider`: official eBay OAuth + Browse scaffold provider
- `backend.listing_providers.EbaySoldScrapeProvider`: real sold/completed comps provider via eBay search-page scraping
- `backend.listing_providers.FallbackListingProvider`: keeps app usable by falling back to mock listings when the primary provider cannot return sold comps
- `backend.ebay_scraper`: URL builder + HTML fetch + sold listing card parsing/normalization helpers used by `EbaySoldScrapeProvider`

Matcher/scoring/bucket grouping and structured `normalized_query` flow remain unchanged.

## Provider selection

Set `LISTING_PROVIDER`:

- `mock` (default): uses sample/mock sold listings
- `ebay_browse`: uses official eBay OAuth/Browse scaffold and then falls back to mock sold listings (because real sold/completed comps are not currently returned through this supported path)
- `ebay_sold_scrape`: scrapes eBay sold/completed search result pages and normalizes listing cards; falls back to mock listings if scrape fetch/parse fails or no listings are parsed

## Required eBay environment variables

When `LISTING_PROVIDER=ebay_browse`, these are required:

- `EBAY_CLIENT_ID`
- `EBAY_CLIENT_SECRET`

Optional eBay settings:

- `EBAY_ENVIRONMENT` (`sandbox` default, or `production`)
- `EBAY_MARKETPLACE_ID` (default `EBAY_US`)
- `EBAY_OAUTH_SCOPE` (default `https://api.ebay.com/oauth/api_scope`)

`LISTING_PROVIDER=ebay_sold_scrape` does not require OAuth credentials.

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

### eBay sold/completed scrape mode

```bash
export LISTING_PROVIDER=ebay_sold_scrape
uvicorn backend.main:app --reload
curl -X POST http://127.0.0.1:8000/search/match \
  -H 'content-type: application/json' \
  -d '{"query":"2024 Topps Chrome Elly De La Cruz /299 auto"}'
```

Expected behavior:

- app stays up
- provider attempts live scrape of eBay sold/completed results
- response buckets remain same shape as existing `/search/match` behavior
- each result preserves existing fields and may include `image_url` when available
- if scraping fails or no cards are parsed, response message explains the issue and provider falls back to mock sold listings

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

## ebay_sold_scrape limitations

- eBay page structure can change at any time and break parsers.
- eBay may throttle, block, or challenge automated fetches; this can cause empty or failed scrape runs.
- Sold dates are parsed from display text and may be locale-dependent.
- Price parsing captures the first recognized numeric amount and may not fully represent shipping/offer context.

## Current sold-comp status

- `ebay_browse`: OAuth/Browse scaffold only, no direct sold/completed support in this project path.
- `ebay_sold_scrape`: real sold/completed ingestion from eBay HTML search pages with best-effort parsing + fallback to mock data.
