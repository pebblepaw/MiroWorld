# Screen 2 — Population Sampling

> **Paper MCP Reference**: Artboard `H9-0` ("Screen 2 — Population Sampling (V2)")
> **UserInput Refs**: D1, A2, A3

## Overview

Two-panel layout. Left: dynamic sampling filters (auto-generated from country dataset) and sample size control. Right: token cost tracker, country map with agent distribution dots, and occupation distribution bar.

## Key Change from V1

**No hardcoded filters.** All filter fields are dynamically generated from the Parquet schema of the selected country's Nemotron dataset. The backend reads column names and unique values from the Parquet file and returns a filter schema.

## Left Panel

### 1. Header
- Title: "Population Sampling"
- Subtitle: "Configure agent population from {country} demographics"

### 2. Dynamic Filters (`DynamicFilters.tsx`)

The filter UI is entirely driven by the backend response from `GET /api/v2/console/session/{id}/filters`.

**API Response schema**:
```json
{
  "filters": [
    {
      "field": "age",
      "type": "range",
      "label": "Age Range",
      "min": 18,
      "max": 85,
      "default_min": 20,
      "default_max": 65
    },
    {
      "field": "planning_area",
      "type": "multi-select-chips",
      "label": "Planning Area",
      "options": ["All Areas", "Central", "East", "West", "North"],
      "default": ["All Areas"]
    },
    {
      "field": "occupation",
      "type": "dropdown",
      "label": "Occupation",
      "options": ["All Occupations", "Professional", "Service", "Clerical", ...],
      "default": "All Occupations"
    },
    {
      "field": "gender",
      "type": "single-select-chips",
      "label": "Gender",
      "options": ["All", "Male", "Female"],
      "default": "All"
    }
  ]
}
```

**Rendering rules**:
- `type: "range"` → Two number inputs with "to" label between them
- `type: "multi-select-chips"` → Row of pill buttons, multiple selectable
- `type: "single-select-chips"` → Row of pill buttons, one selectable
- `type: "dropdown"` → Standard dropdown select
- All selected options have orange styling (border + background tint)

The section header shows: `SAMPLING FILTERS (AUTO-DETECTED)` in orange.

### 3. Sample Size Slider

- Range: 50–500 (configurable from country config)
- Default: 250
- Progress bar style with orange fill
- Large number display: "250"
- Helper text: "50 to 500 · More agents = richer discourse but higher cost"

### 4. Action Buttons
- **"Sample Population"** (orange, primary): Triggers sampling
- **"Proceed →"** (green, secondary): Navigate to Screen 3

## Right Panel

### 1. Token Cost Tracker (`TokenCostTracker.tsx`)

Shows estimated cost for the upcoming simulation:

```
┌─ ESTIMATED COST ─────────────────────────────────────┐
│                    ~$0.42          ~$1.68     -75%    │
│              With context caching  Without    savings │
│                                   (striking)          │
└──────────────────────────────────────────────────────┘
```

- Cached cost: amber color, prominent
- Uncached cost: muted gray with strikethrough
- Savings badge: green pill with percentage
- For Ollama: Shows "Local (Free)" instead
- Endpoint: `GET /api/v2/token-usage/{session_id}/estimate?agents={n}&rounds={r}`

### 2. Country Map

- Placeholder area showing the country map with agent distribution dots
- For Singapore: Planning area boundaries
- For USA: State boundaries
- Colored dots representing sampled agents
- Uses GeoJSON data loaded from `config/countries/{country}/geo.json`

### 3. Occupation Distribution Bar

- Horizontal stacked bar showing occupation breakdown
- Color-coded segments (Professional=green, Service=purple, Clerical=cyan, etc.)
- Legend below with labels and percentages
- Total sample count: "n=250"

## Backend Requirements

- `GET /api/v2/console/session/{id}/filters` → Dynamic filter schema from Parquet
  - Reads column names, types, and unique values from the Parquet file
  - Returns structured JSON that the frontend renders dynamically
- `GET /api/v2/token-usage/{session_id}/estimate` → Cost estimate
  - Calculates based on: agent count × rounds × avg tokens per agent × model pricing
  - Returns cached and uncached estimates
- Existing sampling endpoints remain but now accept dynamic filter keys

### Tests

**Frontend**:
- [ ] Filter UI renders dynamically from API response
- [ ] Range inputs enforce min/max constraints
- [ ] Chip selectors toggle correctly (single vs multi)
- [ ] Sample size slider updates value and helper text
- [ ] Token cost tracker shows correct estimates
- [ ] Distribution bar updates after sampling
- [ ] Map renders for both Singapore and USA

**Backend**:
- [ ] `/filters` endpoint reads Parquet schema correctly
- [ ] `/filters` returns different schemas for different countries
- [ ] Token estimate calculation matches expected formula
- [ ] Caching savings correctly computed (0 for non-Gemini providers)
