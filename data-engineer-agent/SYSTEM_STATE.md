# Current System State

## 1) Purpose and Scope
The service is a FastAPI-based data-engineering agent that converts natural-language requests into **time-series data** from public sources. It returns a strict JSON response contract suitable for downstream forecasting (e.g., Sybilion).

Current scope:
- Time-series only (`output_type=timeseries`)
- English-first query parsing
- Public/free sources only
- Geospatial execution is out of scope in v1

## 2) API Endpoints
- `POST /query`
  - Full pipeline: text extraction -> source planning -> data fetch -> validation -> response
- `POST /dry-run`
  - Extraction + source planning only (no data fetch execution)
- `GET /sources`
  - Returns configured source registry
- `GET /datasets`
  - Returns configured dataset registry

Primary response model (`QueryResponse`):
- `status`: `success | partial | no_data | auth_required | error`
- `interpreted_request`
- `source_plan`
- `data[]` (`TimeSeriesPoint`)
- `metadata` (`granularity_match`, `limitations[]`, `sources[]`)
- `warnings[]`, `errors[]`

## 3) Sources in Use
Configured sources (`app/registry/sources.yaml`):
- `eurostat` (public JSON API)
- `yahoo_finance_commodities` (public market data API)
- `statistik_austria_open_data` (configured; not primary live path in current `/query`)
- `statcube_api` (subscription; excluded by free-only policy)

Free-only rule:
- Planner rejects any source with `auth_required=true` or `access!=public`.

## 4) Supported Datasets and Categories
### Eurostat datasets
- `eurostat_hicp_rent_index_austria`
  - metric: `average_rent`
- `eurostat_hicp_all_items`
  - metric: `inflation_index`
- `eurostat_unemployment_rate`
  - metric: `unemployment_rate`
- `eurostat_gdp_nominal_quarterly`
  - metric: `gdp_nominal`

### Yahoo commodities dataset
- `yahoo_finance_commodities_monthly`
  - metric: `commodity_price`
  - categories/series mapping (examples):
    - Energy: Brent (`BZ=F`), WTI (`CL=F`), NatGas (`NG=F`), Gasoline (`RB=F`), Heating oil (`HO=F`)
    - Metals: Gold (`GC=F`), Silver (`SI=F`), Copper (`HG=F`), Platinum (`PL=F`), Palladium (`PA=F`)
    - Agriculture/Fruits/Softs: Wheat (`ZW=F`), Corn (`ZC=F`), Soybeans (`ZS=F`), Coffee (`KC=F`), Sugar (`SB=F`), Cocoa (`CC=F`), Cotton (`CT=F`), Orange juice (`OJ=F`)
    - Livestock: Lean hogs (`HE=F`), Live cattle (`LE=F`)
    - Supply/material proxies: Freight (`BDRY`), Rare-earth/minerals proxy (`REMX`)

Note: Yahoo commodities are mostly market/futures/proxy series, not official local spot micro-prices.

## 5) Text Extraction Logic
Implemented in `app/agents/intent_extractor.py`.

Pipeline:
1. Lowercase normalization
2. Output type detection (`timeseries` vs geospatial keywords)
3. Metric/domain detection by keyword rules
4. Country detection (mapped country names -> ISO-style codes, default `AT`)
5. District range extraction (`districts X to Y`)
6. Horizon extraction:
   - supports `last N years`, `past N years`, `last A-B years` (uses upper bound)
   - default horizon = 10 years
7. Frequency hint extraction (`monthly`, `quarterly`, `annual`)

Current behavior is deterministic (rule-based), no LLM calls.

## 6) Runtime Architecture
Main orchestration in `app/main.py`.

Components:
- `IntentExtractor` -> structured request
- `SourcePlanner` -> candidate selection and status planning
- Source-specific adapters:
  - `EurostatAdapter` (`app/adapters/eurostat.py`)
  - `CommodityConnector` (`app/adapters/commodities.py`)
- `ResultValidator` -> contract checks + status normalization

Flow (`POST /query`):
1. Extract intent
2. Plan source candidates
3. If no viable source -> return `no_data` / `auth_required`
4. Fetch live series from selected adapter
5. Validate and normalize output
6. Add limitations (e.g., insufficient history)

## 7) Status Semantics
- `success`: valid data and no major coverage/granularity issue
- `partial`: data returned but with known limitation (e.g., district request resolved with higher-level proxy, or short history)
- `no_data`: no suitable public dataset or no observations
- `auth_required`: reserved in schema; currently avoided by free-only planner behavior
- `error`: source fetch/technical failure

## 8) Time Horizon Policy
- Default target horizon: 10 years
- For `last 5-10 years`, target = 10
- If returned coverage is less than 5 years, response is forced to `partial` with `insufficient_history` limitation.

## 9) How to Add New Sources or Datasets
### Add a new source
1. Add source entry to `app/registry/sources.yaml`.
2. Ensure `access=public` for inclusion in current planner policy.

### Add a new dataset
1. Add dataset entry to `app/registry/datasets.yaml` with:
   - `domain`, `metrics[]`, `time_series`, `geo_granularity`, limitations
2. Map query keywords to metric/domain in `IntentExtractor.detect_metric()`.
3. Implement adapter fetch logic for the dataset/source.
4. Route in `POST /query` by `source_id`.
5. Add tests (intent + planner + adapter behavior).

## 10) Testing and Quality
- Test suite: `pytest`
- Current test coverage includes:
  - intent extraction rules
  - source planning
  - response validation behavior
  - commodity series selection
  - API-level behavior for core scenarios

Run:
```bash
pytest -q
```

## 11) Known Limitations
- No LLM-based semantic parsing; rule coverage depends on keyword patterns.
- Commodity series from Yahoo can be subject to market-data API rate limits.
- Geospatial data extraction is intentionally out of scope in current v1.
- Some configured sources/datasets are present as registry entries but not yet wired into live `/query` fetch paths.

## 12) Quick Verification cURL
```bash
curl -s -X POST "http://127.0.0.1:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"Get CPI inflation in Austria for the last 5-10 years"}'
```

```bash
curl -s -X POST "http://127.0.0.1:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"Get Brent commodity prices for the last 10 years"}'
```
