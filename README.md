# PD Recommendation Engine (v1 scaffold)

This workspace contains a **deterministic, constraint-based agronomy recommendation engine** that:

- Loads the product catalog from `plant_doctor_recommendation_engine_template.csv`
- Normalizes each product into required structured attributes (`id`, `name`, `category`, `role_type`)
- Scores products using a weighted formula (problem match + soil match + seasonal + synergy) with **role multipliers**
- Applies **hard constraints** (e.g. lime vs iron sulphate, no multiple iron products, nutrient lockout gating, visual-not-foundational)
- Builds a structured output:
  - **primary** product
  - **stack** (1–4 products) ordered: soil correction → biology → uptake → nutrition → optional visual
  - optional **upgrade_path** (bundles)
- Implements **bundle override** behavior when complexity/uncertainty is high

## Run the demo

```bash
python3 demo_recommend.py
```

## Run as a website app (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Then open `http://localhost:8000` and submit the form.

## JSON API

- `POST /api/recommend` with a JSON body (same fields as the form)
- Returns structured `primary`, `stack`, and optional `upgrade_path`

Or pass your own input JSON file:

```bash
python3 demo_recommend.py sample_input.json
```

## Input shape (example)

```json
{
  "intent": "diagnosis_mode",
  "season": "autumn",
  "confidence": 0.45,
  "problems": {
    "yellowing": 0.8,
    "slow_growth": 0.6,
    "nutrient_lockout": 0.7,
    "patchy_lawn": 0.5,
    "compaction": 0.4
  },
  "soils": {
    "alkaline": 0.7,
    "clay": 0.4
  }
}
```

Supported problem keys:

- `yellowing`
- `slow_growth`
- `weak_roots`
- `nutrient_lockout`
- `patchy_lawn`
- `compaction`
- `poor_water_retention`
- `fungal_issues`

Supported soil keys:

- `sandy`
- `clay`
- `acidic`
- `alkaline`
- `low_organic_matter`
- `hydrophobic`

