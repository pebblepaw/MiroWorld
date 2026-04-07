# Backend: Config System

> **Implements**: Phase Q (Q2–Q4), all UserInput refs to externalized prompts & country config

## Overview

All hardcoded country-specific data and use-case-specific prompts are externalized into YAML config files. A new `ConfigService` loads and caches these at startup.

## Directory Structure

```
config/
├── countries/
│   ├── singapore.yaml
│   └── usa.yaml
└── prompts/
    ├── policy-review.yaml
    ├── ad-testing.yaml
    ├── product-market-fit.yaml
    └── customer-review.yaml
```

## Country Config Schema

```yaml
# config/countries/singapore.yaml
name: "Singapore"
code: "sg"
flag_emoji: "🇸🇬"
dataset_path: "backend/data/nemotron/singapore_nemotron_cc.parquet"
available: true

# Fields that exist in this country's Parquet file
# Used to dynamically generate filters on Screen 2
filter_fields:
  - field: "age"
    type: "range"
    label: "Age Range"
    default_min: 20
    default_max: 65

  - field: "planning_area"
    type: "multi-select-chips"
    label: "Planning Area"
    # options auto-detected from Parquet unique values

  - field: "occupation"
    type: "dropdown"
    label: "Occupation"

  - field: "gender"
    type: "single-select-chips"
    label: "Gender"

# Map configuration
geo_json_path: "config/countries/singapore_geo.json"
map_center: [1.3521, 103.8198]
map_zoom: 11

# Agent sampling
max_agents: 500
default_agents: 250

# Name extraction regex (country-specific patterns)
name_regex: "^([A-Z][a-z]+(?:\\s[A-Z][a-z]+){1,3})"
```

```yaml
# config/countries/usa.yaml
name: "United States"
code: "us"
flag_emoji: "🇺🇸"
dataset_path: "backend/data/nemotron/usa_nemotron_cc.parquet"
available: true

filter_fields:
  - field: "age"
    type: "range"
    label: "Age Range"
    default_min: 18
    default_max: 70

  - field: "state"
    type: "multi-select-chips"
    label: "State"

  - field: "occupation"
    type: "dropdown"
    label: "Occupation"

  - field: "gender"
    type: "single-select-chips"
    label: "Gender"

  - field: "ethnicity"
    type: "multi-select-chips"
    label: "Ethnicity"

geo_json_path: "config/countries/usa_geo.json"
map_center: [39.8283, -98.5795]
map_zoom: 4

max_agents: 500
default_agents: 250
name_regex: "^([A-Z][a-z]+(?:\\s[A-Z][a-z]+){1,3})"
```

## Use Case Prompt Config Schema

```yaml
# config/prompts/policy-review.yaml
name: "Policy Review"
code: "policy-review"
description: "Evaluate public sentiment toward a government policy"

guiding_prompt: |
  You are evaluating the public's reaction to the following policy document.
  Focus on understanding approval, disapproval, and the specific reasons behind each stance.
  Pay attention to demographic patterns in opinion shifts.

agent_personality_modifiers:
  - "Express genuine concern about how this policy affects your daily life and family"
  - "When responding to other comments, engage directly with their specific arguments"
  - "If you strongly disagree, explain why with concrete personal examples"

checkpoint_questions:
  - question: "Do you approve of this policy? Rate 1-10."
    type: "scale"
    metric_name: "approval_rate"
    threshold: 7
    threshold_direction: "gte"
    display_label: "Approval Rate"
    tooltip: "Percentage of agents who rated the policy ≥ 7 out of 10 during the checkpoint interview."

  - question: "What is your overall sentiment about this policy? Rate 1-10."
    type: "scale"
    metric_name: "net_sentiment"
    display_label: "Net Sentiment"
    tooltip: "Mean opinion score across all agents (1=strongly negative, 10=strongly positive)."

report_sections:
  - title: "Overall Approval"
    prompt: "Summarize the overall approval rate and how it changed over the simulation."
  - title: "Key Supporting Arguments"
    prompt: "List the top 3 arguments in favor, with evidence from agent posts."
  - title: "Key Opposing Arguments"
    prompt: "List the top 3 arguments against, with evidence from agent posts."
  - title: "Demographic Patterns"
    prompt: "Identify which demographic groups shifted most significantly."
  - title: "Recommendations"
    prompt: "Provide actionable recommendations for the policy maker based on the simulation results."
```

```yaml
# config/prompts/ad-testing.yaml
name: "Ad Testing"
code: "ad-testing"
description: "Test advertisement effectiveness with target audience"

guiding_prompt: |
  You are evaluating consumer reactions to the following advertisement.
  Focus on understanding engagement, conversion intent, and brand perception.

agent_personality_modifiers:
  - "React authentically to this advertisement as a real consumer would"
  - "Consider whether this product/service actually addresses your needs"
  - "Share honest feedback, including any skepticism about marketing claims"

checkpoint_questions:
  - question: "Would you try/buy this product after seeing this ad? (yes/no)"
    type: "yes-no"
    metric_name: "estimated_conversion"
    display_label: "Estimated Conversion"
    tooltip: "Percentage of agents who expressed intent to buy/try the product."

  - question: "How engaging was this advertisement? Rate 1-10."
    type: "scale"
    metric_name: "engagement_score"
    display_label: "Engagement Score"
    tooltip: "Mean engagement rating across all agents."

report_sections:
  - title: "Conversion Analysis"
    prompt: "Summarize the estimated conversion rate and key purchase drivers."
  - title: "Engagement Patterns"
    prompt: "Analyze which elements of the ad drove the most discussion."
  - title: "Skepticism & Objections"
    prompt: "Identify the main reasons agents were skeptical or disinterested."
  - title: "Target Audience Fit"
    prompt: "Evaluate which demographics responded best to the ad."
  - title: "Optimization Recommendations"
    prompt: "Suggest specific changes to improve ad performance."
```

```yaml
# config/prompts/product-market-fit.yaml
name: "PMF Discovery"
code: "pmf-discovery"
description: "Discover product-market fit across demographics"

guiding_prompt: |
  You are evaluating whether the following product concept addresses real needs.
  Focus on understanding which demographics would benefit most and why.

agent_personality_modifiers:
  - "Evaluate this product concept based on your actual daily habits and pain points"
  - "Be honest about whether you would actually use or pay for this"
  - "Consider alternatives you currently use and whether this is genuinely better"

checkpoint_questions:
  - question: "Is this product something you need? Rate 1-10."
    type: "scale"
    metric_name: "product_interest"
    threshold: 7
    threshold_direction: "gte"
    display_label: "Product Interest"
    tooltip: "Percentage of agents who rated the product need ≥ 7 out of 10."

  - question: "How well does this product fit your lifestyle? Rate 1-10."
    type: "scale"
    metric_name: "target_fit_score"
    display_label: "Target Fit Score"
    tooltip: "Mean fit score across target demographic agents."

report_sections:
  - title: "Product Interest"
    prompt: "Summarize overall interest level and how it changed."
  - title: "Best-Fit Demographics"
    prompt: "Identify which demographic groups showed the highest interest."
  - title: "Pain Points Addressed"
    prompt: "Analyze which specific problems the product solves for different groups."
  - title: "Competitive Alternatives"
    prompt: "Summarize what alternatives agents currently use."
  - title: "Market Entry Recommendations"
    prompt: "Recommend target demographics and positioning strategy."
```

```yaml
# config/prompts/customer-review.yaml
name: "Customer Review"
code: "customer-review"
description: "Simulate customer reviews and satisfaction feedback"

guiding_prompt: |
  You are simulating authentic customer reviews for the following product/service.
  Focus on realistic satisfaction levels, specific praise and complaints.

agent_personality_modifiers:
  - "Write a review as if you genuinely experienced this product or service"
  - "Include specific details about what worked and what didn't"
  - "Rate your satisfaction honestly — don't default to extreme scores"

checkpoint_questions:
  - question: "How satisfied are you with this product/service? Rate 1-10."
    type: "scale"
    metric_name: "satisfaction"
    display_label: "Satisfaction"
    tooltip: "Mean satisfaction score across all agents (1-10 scale)."

  - question: "Would you recommend this to a friend? Rate 1-10."
    type: "scale"
    metric_name: "recommendation"
    threshold: 8
    threshold_direction: "gte"
    display_label: "Recommendation (NPS)"
    tooltip: "Percentage of agents who would recommend (score ≥ 8), following Net Promoter Score methodology."

report_sections:
  - title: "Overall Satisfaction"
    prompt: "Summarize the satisfaction distribution and key trends."
  - title: "Top Praise Points"
    prompt: "Identify what agents liked most, with evidence."
  - title: "Top Complaints"
    prompt: "Identify the most common complaints and their severity."
  - title: "Segment Analysis"
    prompt: "Break down satisfaction by demographic segment."
  - title: "Improvement Priorities"
    prompt: "Recommend prioritized improvements based on complaint frequency and severity."
```

## ConfigService Implementation

```python
# backend/src/mckainsey/services/config_service.py

import yaml
from pathlib import Path
from functools import lru_cache

CONFIG_DIR = Path(__file__).parent.parent.parent.parent.parent / "config"

class ConfigService:
    """Loads and caches YAML config files for countries and use cases."""

    @lru_cache(maxsize=16)
    def get_country_config(self, country_code: str) -> dict:
        path = CONFIG_DIR / "countries" / f"{country_code}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Country config not found: {country_code}")
        with open(path) as f:
            return yaml.safe_load(f)

    @lru_cache(maxsize=16)
    def get_prompt_config(self, use_case: str) -> dict:
        path = CONFIG_DIR / "prompts" / f"{use_case}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Prompt config not found: {use_case}")
        with open(path) as f:
            return yaml.safe_load(f)

    def list_countries(self) -> list[dict]:
        countries = []
        for f in (CONFIG_DIR / "countries").glob("*.yaml"):
            cfg = yaml.safe_load(f.read_text())
            countries.append({
                "name": cfg["name"],
                "code": cfg["code"],
                "flag_emoji": cfg["flag_emoji"],
                "available": cfg.get("available", True),
            })
        return countries

    def list_use_cases(self) -> list[dict]:
        cases = []
        for f in (CONFIG_DIR / "prompts").glob("*.yaml"):
            cfg = yaml.safe_load(f.read_text())
            cases.append({
                "name": cfg["name"],
                "code": cfg["code"],
                "description": cfg["description"],
            })
        return cases

    def get_checkpoint_questions(self, use_case: str) -> list[dict]:
        cfg = self.get_prompt_config(use_case)
        return cfg.get("checkpoint_questions", [])

    def get_agent_personality_modifiers(self, use_case: str) -> list[str]:
        cfg = self.get_prompt_config(use_case)
        return cfg.get("agent_personality_modifiers", [])

    def get_report_sections(self, use_case: str) -> list[dict]:
        cfg = self.get_prompt_config(use_case)
        return cfg.get("report_sections", [])
```

## Refactoring Checklist

- [x] All hardcoded Singapore field names → read from country YAML
- [x] All hardcoded prompts in `simulation_service.py` → `config_service.get_agent_personality_modifiers()`
- [x] All hardcoded checkpoint questions → `config_service.get_checkpoint_questions()`
- [x] All hardcoded report section prompts → `config_service.get_report_sections()`
- [x] `quick_start.sh` no longer exits if Ollama is not installed
- [x] Provider detection is lazy (checked when simulation starts, not at boot)

## Tests

- [x] `ConfigService` loads valid YAML files correctly
- [x] `ConfigService` raises `FileNotFoundError` for missing country/use-case
- [x] `list_countries()` returns all YAML files in countries dir
- [x] `get_checkpoint_questions()` returns correct question format
- [x] Invalid YAML gracefully handled (logged, not crashed)
