# Screen 0 — Onboarding Modal

> **Paper MCP Reference**: Artboard `8A-0` ("Screen 0 — Onboarding Modal")
> **UserInput Refs**: A1, A2, B1, B2

## Overview

A fullscreen modal that appears on first load. Users configure their simulation environment: country, LLM provider, model, API key, and use case. After clicking "Launch Simulation Environment", the modal dismisses and the user proceeds to Screen 1.

The modal can be re-opened via the Settings button on the sidebar. The selected country and model should be permanently displayed at the bottom of the sidebar.

## Component: `OnboardingModal.tsx`

### Props & State
```typescript
interface OnboardingConfig {
  country: string;          // "singapore" | "usa"
  provider: string;         // "gemini" | "openai" | "ollama"
  model: string;            // e.g. "gemini-2.0-flash"
  apiKey: string;           // masked after entry
  useCase: string;          // "policy-review" | "ad-testing" | "pmf-discovery" | "customer-review"
}
```

### UI Sections (top to bottom)

1. **Header**: McKAInsey logo + "Configure your simulation environment"
2. **Country / Region selector**: Grid of 4 cards (Singapore, USA, India, Japan). India/Japan are disabled (greyed out) with "Coming Soon" badge. Selected card has orange border + text.
   - Each card shows a flag emoji and country name
   - On select: calls `GET /api/v2/countries` to verify dataset exists
3. **LLM Provider + Model row** (side by side):
   - Provider: Dropdown — Gemini, OpenAI, Ollama
   - Model: Dropdown — populated dynamically based on provider
   - Source: `GET /api/v2/providers` returns `[{name, models[], requires_api_key}]`
4. **API Key**: Password input field, masked with dots showing first 4 and last 2 chars
   - Hidden when provider = "ollama" (no key needed)
5. **Use Case selector**: Row of 4 pill buttons. Selected has orange border + fill.
   - "Policy Review" | "Ad Testing" | "PMF Discovery" | "Reviews"
6. **Launch button**: Full-width orange CTA: "Launch Simulation Environment →"
   - On click: `POST /api/v2/session/create` with the config, stores `session_id` in React context
   - Validates: country selected, model selected, API key provided (if required)

### Behavior
- **First load**: Modal opens automatically with Singapore pre-selected
- **Settings button**: Re-opens modal with current config pre-filled
- **Sidebar display**: After dismissal, show small text at sidebar bottom: "🇸🇬 Singapore · Gemini"
- **Startup fix (B2)**: Backend must NOT exit if Ollama is not installed. The frontend lets users choose any provider.

### Backend Requirements
- `GET /api/v2/countries` → `[{name, code, flag_emoji, dataset_path, available}]`
- `GET /api/v2/providers` → `[{name, models, requires_api_key}]`
- `POST /api/v2/session/create` → `{session_id}` — creates session with config

### Tests
- [ ] Modal appears on first load
- [ ] Country selection highlights correctly, disabled countries show tooltip
- [ ] Provider change updates model dropdown
- [ ] API key field hides for Ollama
- [ ] "Launch" validates required fields before proceeding
- [ ] Session ID is stored in React context after creation
- [ ] Settings button re-opens modal with saved state
