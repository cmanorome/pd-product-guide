from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from pd_engine import recommend


ROOT = Path(__file__).resolve().parent
CATALOG_CSV = ROOT / "plant_doctor_recommendation_engine_template.csv"

app = FastAPI(title="PD Agronomy Recommendation Engine", version="0.1.0")

# If you embed this on another domain, update this list.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _to_payload(form: dict[str, Any]) -> dict[str, Any]:
    def f01(v: Any, default: float = 0.0) -> float:
        try:
            x = float(v)
            return max(0.0, min(1.0, x))
        except Exception:
            return default

    def truthy(v: Any) -> bool:
        if isinstance(v, bool):
            return v
        s = str(v or "").strip().lower()
        return s in {"1", "true", "yes", "y", "on", "checked"}

    confidence_label = str(form.get("confidence_level") or "somewhat_sure").strip().lower()
    confidence_map = {
        "not_sure": 0.45,
        "somewhat_sure": 0.6,
        "very_sure": 0.85,
    }
    confidence = confidence_map.get(confidence_label, 0.6)

    problems = {
        "yellowing": 1.0 if truthy(form.get("yellowing")) else 0.0,
        "slow_growth": 1.0 if truthy(form.get("slow_growth")) else 0.0,
        "weak_roots": 1.0 if truthy(form.get("weak_roots")) else 0.0,
        "nutrient_lockout": 1.0 if truthy(form.get("nutrient_lockout")) else 0.0,
        "patchy_lawn": 1.0 if truthy(form.get("patchy_lawn")) else 0.0,
        "compaction": 1.0 if truthy(form.get("compaction")) else 0.0,
        "poor_water_retention": 1.0 if truthy(form.get("poor_water_retention")) else 0.0,
        "fungal_issues": 1.0 if truthy(form.get("fungal_issues")) else 0.0,
        "poor_flowering": 1.0 if truthy(form.get("poor_flowering")) else 0.0,
    }
    soils = {
        "sandy": 1.0 if truthy(form.get("sandy")) else 0.0,
        "clay": 1.0 if truthy(form.get("clay")) else 0.0,
        "acidic": 1.0 if truthy(form.get("acidic")) else 0.0,
        "alkaline": 1.0 if truthy(form.get("alkaline")) else 0.0,
        "low_organic_matter": 1.0 if truthy(form.get("low_organic_matter")) else 0.0,
        "hydrophobic": 1.0 if truthy(form.get("hydrophobic")) else 0.0,
    }

    # Drop zeros to keep payload clean
    problems = {k: v for k, v in problems.items() if v > 0}
    soils = {k: v for k, v in soils.items() if v > 0}

    rec_mode = str(form.get("recommendation_mode") or "problems").strip().lower()
    if rec_mode not in ("problems", "goals"):
        rec_mode = "problems"

    intent = str(form.get("intent") or "maintenance_mode").strip().lower()
    if rec_mode == "problems":
        intent = "rescue_mode"
    elif rec_mode == "goals" and intent in ("diagnosis_mode", "rescue_mode"):
        intent = "maintenance_mode"

    gv = str(form.get("goal_vertical") or "").strip().lower()
    if gv not in ("lawn", "garden", "farm"):
        gv = ""
    uc_for_gv = str(form.get("use_case") or "").strip().lower()
    if rec_mode == "goals" and not gv:
        if uc_for_gv == "lawn":
            gv = "lawn"
        elif uc_for_gv == "farms":
            gv = "farm"
        elif uc_for_gv in ("garden_beds", "pots", "indoor_plants"):
            gv = "garden"

    goal_weights: dict[str, float] = {}
    gw = form.get("goal_weights")
    if isinstance(gw, dict):
        for k, v in gw.items():
            try:
                fv = float(v)
                if fv > 0:
                    goal_weights[str(k).strip()] = max(0.0, min(1.0, fv))
            except (TypeError, ValueError):
                pass

    return {
        "intent": intent,
        "season": (form.get("season") or "unknown"),
        "use_case": (form.get("use_case") or ""),
        "recommendation_mode": rec_mode,
        "goal_vertical": gv,
        "goal_weights": goal_weights,
        "confidence": f01(form.get("confidence", confidence), confidence),
        "problems": problems,
        "soils": soils,
        "soil_ph": form.get("soil_ph") or None,
        "soil_ph_method": form.get("soil_ph_method") or "water",
        "organic_matter_pct": form.get("organic_matter_pct") or None,
    }


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Plant Doctor Product Guide</title>
    <style>
      :root { --green: #22B14C; --green-dark: #14532d; --ink: #111827; --muted: #6b7280; --line: #e5e7eb; --bg: #f6f7f8; }
      * { box-sizing: border-box; }
      body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin: 0; background: var(--bg); color: var(--ink); }
      .header {
        background: var(--green);
        color: #f0fdfa;
        padding: 32px 0 24px;
        margin-bottom: 22px;
      }
      .container { max-width: 820px; margin: 0 auto; padding: 0 16px; }
      main.container { padding-bottom: 48px; }
      .eyebrow {
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-size: 11px;
        margin: 0 0 8px;
        opacity: 0.95;
      }
      h1 { margin: 0 0 8px; font-size: clamp(26px, 4vw, 34px); }
      .subtitle { margin: 0; color: #dcfce7; max-width: 720px; }
      h3 { font-size: 16px; margin: 22px 0 10px; }
      .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
      .card { border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; background: white; }
      .card h4 { margin: 0 0 8px 0; font-size: 14px; }
      label { display:block; font-size: 12px; color:#374151; margin-bottom: 4px; }
      input, select { width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 8px; }
      button { padding: 10px 16px; border: 0; border-radius: 10px; background: var(--green); color: white; cursor:pointer; font-weight: 600; }
      button.secondary { background: white; color: var(--ink); border: 1px solid var(--line); font-weight: 500; }
      button:disabled { opacity: 0.65; cursor: default; }
      .muted { color: var(--muted); font-size: 13px; line-height: 1.45; }
      .hidden { display: none !important; }
      .ask.card {
        display: flex;
        flex-direction: column;
        gap: 18px;
        padding: 18px 20px 20px;
        counter-reset: ask;
      }
      .ask-step {
        display: grid;
        grid-template-columns: 28px minmax(0, 1fr);
        gap: 10px 14px;
        align-items: start;
        counter-increment: ask;
      }
      .ask-num {
        width: 28px;
        height: 28px;
        border-radius: 99px;
        background: var(--green-dark);
        color: #fff;
        font-size: 13px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-top: 2px;
      }
      .ask-num::before { content: counter(ask); }
      .ask-step h3 { margin: 4px 0 8px; }
      .ask-step > div > label { margin-bottom: 8px; }
      .ask-step .muted { margin: 0 0 10px; }
      .ask-fields {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 10px 12px;
      }
      .check-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 8px;
      }
      .check-item {
        display: flex;
        gap: 10px;
        align-items: flex-start;
        margin: 0;
        padding: 10px 12px;
        border: 1px solid var(--line);
        border-radius: 10px;
        background: #fafafa;
        cursor: pointer;
      }
      .check-item:has(input:checked) {
        border-color: var(--green);
        background: #f0faf3;
      }
      .check-item input { width: auto; margin: 0; margin-top: 2px; }
      .check-item .title { display: block; font-weight: 600; font-size: 14px; line-height: 1.3; }
      .check-item .desc { display: block; font-size: 12px; color: var(--muted); margin-top: 2px; }
      .ask .fold { margin-top: 10px; }
      .ask.card.is-collapsed { gap: 0; padding: 14px 16px; }
      .ask-summary {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
      }
      .ask-summary .kicker { margin: 0 0 2px; }
      .ask-summary p { margin: 0; font-size: 14px; }
      .ask-summary-actions { display: flex; gap: 8px; flex-wrap: wrap; }
      .mode-row { display: flex; flex-wrap: wrap; gap: 10px; }
      .mode-row label {
        display: flex; gap: 8px; align-items: center; cursor: pointer;
        font-size: 14px; flex: 1 1 220px; margin: 0;
        padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; background: #fafafa;
      }
      .mode-row label:has(input:checked) { border-color: var(--green); background: #f0faf3; }
      .mode-row label input[type="radio"] { width: auto; margin: 0; }
      .actions { display: flex; gap: 8px; margin: 18px 0 8px; position: sticky; bottom: 12px; background: var(--bg); padding: 8px 0; z-index: 2; }
      details.fold { border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; background: white; margin-top: 14px; }
      details.fold > summary { cursor: pointer; font-weight: 600; font-size: 14px; }
      details.fold > summary + * { margin-top: 10px; }
      .why-list { margin: 0; padding-left: 18px; }
      .why-list li { margin: 0 0 8px; font-size: 13px; line-height: 1.45; color: #374151; }

      .results { display: flex; flex-direction: column; gap: 14px; margin-top: 8px; }
      .kicker { font-size: 11px; letter-spacing: 0.04em; text-transform: uppercase; color: var(--muted); font-weight: 700; margin: 0 0 6px; }
      .hero { background: white; border: 1px solid var(--line); border-radius: 14px; padding: 16px; }
      .hero img, .row-card img { width: 72px; height: 72px; object-fit: cover; border-radius: 10px; border: 1px solid var(--line); background: #fff; }
      .row-card img { width: 52px; height: 52px; }
      .prod, .row-card {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr);
        column-gap: 14px;
        row-gap: 8px;
        align-items: start;
      }
      .prod > img, .row-card > img { grid-column: 1; grid-row: 1 / span 2; }
      .prod-title { grid-column: 2; grid-row: 1; min-width: 0; }
      .prod-body { grid-column: 2; grid-row: 2; min-width: 0; }
      .prod-name { font-size: 16px; font-weight: 700; margin: 0; }
      .row-card .prod-name { font-size: 15px; }
      .prod-why { color: #374151; font-size: 14px; line-height: 1.4; margin: 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
      .role-tag { font-size: 11px; color: var(--muted); font-weight: 600; margin-bottom: 2px; }
      .prod-actions { display: flex; gap: 10px; align-items: center; margin-top: 8px; flex-wrap: wrap; }
      .link { color: var(--green); font-weight: 600; font-size: 13px; text-decoration: none; }
      .step-list { display: flex; flex-direction: column; gap: 8px; }
      .row-card { background: white; border: 1px solid var(--line); border-radius: 12px; padding: 12px; column-gap: 12px; }
      .row-card.has-step { grid-template-columns: 24px auto minmax(0, 1fr); }
      .row-card.has-step .step-num { grid-column: 1; grid-row: 1; }
      .row-card.has-step > img { grid-column: 2; grid-row: 1 / span 2; }
      .row-card.has-step .prod-title { grid-column: 3; grid-row: 1; }
      .row-card.has-step .prod-body { grid-column: 3; grid-row: 2; }
      .champ-card .champ-audience { grid-column: 1 / -1; grid-row: 1; }
      .champ-card > img { grid-column: 1; grid-row: 2 / span 2; }
      .champ-card .prod-title { grid-column: 2; grid-row: 2; }
      .champ-card .prod-body { grid-column: 2; grid-row: 3; }
      .step-num { width: 24px; height: 24px; border-radius: 999px; background: var(--green); color: white; font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; margin-top: 2px; }
      .tip { font-size: 13px; color: #374151; background: #f0faf3; border-radius: 10px; padding: 10px 12px; line-height: 1.45; }
      details.more { margin-top: 6px; }
      details.more summary { cursor: pointer; color: var(--muted); font-size: 12px; }
      details.more p { margin: 8px 0 0; font-size: 13px; color: #374151; line-height: 1.45; }
      .use-row { display: flex; flex-wrap: wrap; gap: 5px; margin: 6px 0 2px; }
      .use-chip {
        display: inline-flex; align-items: center; gap: 5px;
        font-size: 11px; color: #374151; background: #f8faf9;
        border: 1px solid var(--line); border-radius: 99px; padding: 2px 8px 2px 6px;
      }
      .use-dot, .use-mix {
        width: 9px; height: 9px; border-radius: 99px; flex: 0 0 auto;
      }
      .use-mix { position: relative; width: 14px; }
      .use-mix i {
        position: absolute; top: 0; width: 9px; height: 9px; border-radius: 99px;
        border: 1px solid #fff;
      }
      .use-mix i:first-child { left: 0; background: #0c783c; }
      .use-mix i:last-child { left: 5px; background: #e4a818; }
      .use-dot.independent { background: #e4a818; }
      .use-dot.water_in { background: #3c6cb4; }
      .use-dot.soil_drench { background: #cc5424; }
      .use-dot.foliar { background: #0c783c; }
      .use-dot.fertigation { background: #183c9c; }
      .use-dot.hydroponic { background: #18a8a8; }
      .use-dot.hose_on { background: #60b43c; }
      .use-dot.mix_with_iron { background: #e4a818; }
      .pair { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
      @media (max-width: 640px) {
        .pair { grid-template-columns: 1fr; }
        .prod > img, .row-card > img { grid-row: 1; }
        .prod-title { grid-row: 1; }
        .prod-body { grid-column: 1 / -1; grid-row: 2; }
        .row-card.has-step > img { grid-row: 1; }
        .row-card.has-step .prod-title { grid-row: 1; }
        .row-card.has-step .prod-body { grid-column: 1 / -1; grid-row: 2; }
        .champ-card > img { grid-row: 2; }
        .champ-card .prod-title { grid-row: 2; }
        .champ-card .prod-body { grid-column: 1 / -1; grid-row: 3; }
        .prod-why { -webkit-line-clamp: 4; }
      }
      .empty { color: var(--muted); font-size: 14px; padding: 16px 0; }
    </style>
  </head>
  <body>
    <header class="header">
      <div class="container">
        <p class="eyebrow">Plant Doctor</p>
        <h1>Product Guide</h1>
        <p class="subtitle">Tell us what’s going on. We’ll suggest what to use first, then what to add.</p>
      </div>
    </header>
    <main class="container">

    <div class="ask card" id="ask_wrap">
      <div id="ask_summary" class="ask-summary hidden">
        <div>
          <p class="kicker">Your answers</p>
          <p id="ask_summary_text"></p>
        </div>
        <div class="ask-summary-actions">
          <button type="button" id="edit_answers" class="secondary">Change answers</button>
          <button type="button" id="reset_collapsed" class="secondary">Reset</button>
        </div>
      </div>
      <div id="ask_panel">
      <section class="ask-step">
        <span class="ask-num"></span>
        <div>
          <label>I want to</label>
          <div class="mode-row">
            <label><input type="radio" name="rec_mode" value="problems" checked /><span>Fix a problem</span></label>
            <label><input type="radio" name="rec_mode" value="goals" /><span>Improve results</span></label>
          </div>
        </div>
      </section>

      <section class="ask-step">
        <span class="ask-num"></span>
        <div>
          <div class="ask-fields">
            <div id="card_intent">
              <label for="intent">Stage</label>
              <select id="intent">
                <option value="establishment_mode">Just planting / establishing</option>
                <option value="maintenance_mode" selected>Keep it healthy</option>
                <option value="performance_mode">Push for best results</option>
              </select>
            </div>
            <div>
              <label for="season">Season</label>
              <select id="season">
                <option value="unknown">Unknown</option>
                <option value="spring">Spring</option>
                <option value="summer">Summer</option>
                <option value="autumn">Autumn</option>
                <option value="winter">Winter</option>
              </select>
            </div>
            <div class="hidden" id="card_goal_vertical">
              <label for="goal_vertical">Goal area</label>
              <select id="goal_vertical">
                <option value="lawn">Lawn goals</option>
                <option value="garden">Garden goals</option>
                <option value="farm">Farm goals</option>
              </select>
            </div>
            <div id="card_use_case">
              <label for="use_case">Where are you using it?</label>
              <select id="use_case">
                <option value="">Not sure</option>
                <option value="lawn">Lawn</option>
                <option value="garden_beds">Garden (beds, veg, flowers, pots)</option>
              </select>
            </div>
            <div>
              <label for="confidence_level">How sure are you?</label>
              <select id="confidence_level">
                <option value="not_sure">Not sure</option>
                <option value="somewhat_sure" selected>Somewhat sure</option>
                <option value="very_sure">Very sure</option>
              </select>
            </div>
          </div>
        </div>
      </section>

      <section id="section_goals" class="ask-step hidden">
        <span class="ask-num"></span>
        <div>
          <h3>What do you want?</h3>
          <p class="muted">Tick one or more. These change with where you’re using it.</p>
          <div id="goals_need_place" class="tip hidden">Choose where you’re using it above, and we’ll show lawn or garden goals.</div>
          <div id="goal_panel_lawn" class="check-grid hidden">
            <label class="check-item"><input class="goal-cb" type="checkbox" data-goal-key="deep_green_colour"/><span><span class="title">Deep green colour</span></span></label>
            <label class="check-item"><input class="goal-cb" type="checkbox" data-goal-key="thickening_and_density"/><span><span class="title">Thickening and density</span></span></label>
            <label class="check-item"><input class="goal-cb" type="checkbox" data-goal-key="fast_recovery_from_stress"/><span><span class="title">Fast recovery from stress</span></span></label>
            <label class="check-item"><input class="goal-cb" type="checkbox" data-goal-key="weed_suppression_through_dominance"/><span><span class="title">Weed suppression through dominance</span></span></label>
            <label class="check-item"><input class="goal-cb" type="checkbox" data-goal-key="low_maintenance_resilience"/><span><span class="title">Low maintenance resilience</span></span></label>
          </div>
          <div id="goal_panel_garden" class="check-grid hidden">
            <label class="check-item"><input class="goal-cb" type="checkbox" data-goal-key="strong_flowering_and_fruiting"/><span><span class="title">More flowers, fruit and veg</span><span class="desc">Blooms, cropping, and productive plants.</span></span></label>
            <label class="check-item"><input class="goal-cb" type="checkbox" data-goal-key="improved_soil_fertility"/><span><span class="title">Richer soil over time</span><span class="desc">Biology, structure, and nutrient holding.</span></span></label>
            <label class="check-item"><input class="goal-cb" type="checkbox" data-goal-key="root_development_transplant"/><span><span class="title">Stronger roots and transplanting</span><span class="desc">New plantings, seedlings, and establishment.</span></span></label>
            <label class="check-item"><input class="goal-cb" type="checkbox" data-goal-key="pest_and_disease_resilience"/><span><span class="title">Pest and disease resilience</span><span class="desc">Tougher plants under pressure.</span></span></label>
            <label class="check-item"><input class="goal-cb" type="checkbox" data-goal-key="consistent_growth_across_seasons"/><span><span class="title">Steady growth through the year</span><span class="desc">Less boom-and-bust between seasons.</span></span></label>
          </div>
          <div id="goal_panel_farm" class="check-grid hidden">
            <label class="check-item"><input class="goal-cb" type="checkbox" data-goal-key="yield_increase"/><span><span class="title">Yield increase</span></span></label>
            <label class="check-item"><input class="goal-cb" type="checkbox" data-goal-key="soil_efficiency"/><span><span class="title">Soil efficiency</span></span></label>
            <label class="check-item"><input class="goal-cb" type="checkbox" data-goal-key="water_efficiency"/><span><span class="title">Water efficiency</span></span></label>
            <label class="check-item"><input class="goal-cb" type="checkbox" data-goal-key="crop_uniformity"/><span><span class="title">Crop uniformity</span></span></label>
            <label class="check-item"><input class="goal-cb" type="checkbox" data-goal-key="reduced_input_dependency"/><span><span class="title">Reduced input dependency over time</span></span></label>
          </div>
        </div>
      </section>

      <section id="section_symptoms" class="ask-step">
        <span class="ask-num"></span>
        <div>
          <h3>What’s wrong?</h3>
          <div class="check-grid">
            <label class="check-item"><input id="yellowing" type="checkbox"/><span><span class="title" id="yellowing_title">Yellowing</span><span class="desc" id="yellowing_desc">Pale lawn or yellow leaves on plants.</span></span></label>
            <label class="check-item"><input id="slow_growth" type="checkbox"/><span><span class="title" id="slow_growth_title">Slow growth</span><span class="desc" id="slow_growth_desc">Not filling out — lawn or plants.</span></span></label>
            <label class="check-item"><input id="weak_roots" type="checkbox"/><span><span class="title" id="weak_roots_title">Weak roots</span><span class="desc" id="weak_roots_desc">Pulls up easily, wilts in heat, or struggles after planting.</span></span></label>
            <label class="check-item"><input id="nutrient_lockout" type="checkbox"/><span><span class="title">Nutrient lockout</span><span class="desc">Fertilised but no response, symptoms persist.</span></span></label>
            <label class="check-item" id="card_patchy_lawn"><input id="patchy_lawn" type="checkbox"/><span><span class="title">Patchy lawn</span><span class="desc">Uneven growth, thin areas.</span></span></label>
            <label class="check-item" id="card_poor_flowering"><input id="poor_flowering" type="checkbox"/><span><span class="title">Poor flowering or fruiting</span><span class="desc">Few blooms, small fruit, or plants that won’t crop.</span></span></label>
            <label class="check-item"><input id="compaction" type="checkbox"/><span><span class="title">Compaction</span><span class="desc">Hard ground, poor drainage, poor root penetration.</span></span></label>
            <label class="check-item"><input id="poor_water_retention" type="checkbox"/><span><span class="title">Poor water retention</span><span class="desc">Dries quickly, needs frequent watering.</span></span></label>
            <label class="check-item"><input id="fungal_issues" type="checkbox"/><span><span class="title" id="fungal_title">Fungal issues</span><span class="desc" id="fungal_desc">Spots, mildew, circular patches, or disease pressure.</span></span></label>
          </div>
        </div>
      </section>

      <section class="ask-step">
        <span class="ask-num"></span>
        <div>
          <h3>Soil</h3>
          <div class="check-grid">
            <label class="check-item"><input id="sandy" type="checkbox"/><span><span class="title">Sandy</span><span class="desc">Drains fast, nutrients leach.</span></span></label>
            <label class="check-item"><input id="clay" type="checkbox"/><span><span class="title">Clay</span><span class="desc">Heavy, holds water, compacts easily.</span></span></label>
            <label class="check-item"><input id="acidic" type="checkbox"/><span><span class="title">Acidic</span><span class="desc">Low pH. Skip if you enter a measured pH.</span></span></label>
            <label class="check-item"><input id="alkaline" type="checkbox"/><span><span class="title">Alkaline</span><span class="desc">High pH. Skip if you enter a measured pH.</span></span></label>
            <label class="check-item"><input id="low_organic_matter" type="checkbox"/><span><span class="title">Low organic matter</span><span class="desc">Poor soil life and nutrient buffering.</span></span></label>
            <label class="check-item"><input id="hydrophobic" type="checkbox"/><span><span class="title">Hydrophobic (water repellent)</span><span class="desc">Water beads/runs off, dry patch.</span></span></label>
          </div>
          <details class="fold" id="section_soil_test">
            <summary>I have a soil test (optional)</summary>
            <p class="muted">pH is the most useful number. Home kits are usually water pH; Australian labs are often CaCl₂.</p>
            <div class="ask-fields">
              <div>
                <label for="soil_ph">Soil pH</label>
                <input id="soil_ph" type="number" min="3.5" max="10.5" step="0.1" placeholder="e.g. 6.2" />
                <div class="muted" style="margin-top:6px;" id="soil_ph_hint">Leave blank if you haven’t tested.</div>
              </div>
              <div>
                <label for="soil_ph_method">Measured in</label>
                <select id="soil_ph_method">
                  <option value="water" selected>Water (home kit)</option>
                  <option value="cacl2">CaCl₂ (lab report)</option>
                </select>
              </div>
              <div>
                <label for="organic_matter_pct">Organic matter %</label>
                <input id="organic_matter_pct" type="number" min="0" max="20" step="0.1" placeholder="e.g. 1.8" />
              </div>
            </div>
          </details>
        </div>
      </section>
      </div>
    </div>

    <div class="actions" id="actions">
      <button id="run">Get recommendation</button>
      <button id="reset" class="secondary" type="button">Reset</button>
    </div>

    <h3 id="results_heading">Your plan</h3>
    <div id="friendly" class="results">
      <div class="empty">Fill in the form and tap Get recommendation.</div>
    </div>

    <script>
      const ids = [
        "intent","season","use_case","confidence_level",
        "yellowing","slow_growth","weak_roots","nutrient_lockout","patchy_lawn","poor_flowering","compaction","poor_water_retention","fungal_issues",
        "sandy","clay","acidic","alkaline","low_organic_matter","hydrophobic"
      ];
      function verticalFromUseCase(uc) {
        if (uc === "lawn") return "lawn";
        if (uc === "farms") return "farm";
        if (uc === "garden_beds" || uc === "pots" || uc === "indoor_plants") return "garden";
        return "";
      }
      function setTxt(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
      }
      function syncPlaceUI() {
        const mode = document.querySelector('input[name="rec_mode"]:checked').value;
        const uc = document.getElementById("use_case").value;
        const garden = ["garden_beds","pots","indoor_plants"].includes(uc);
        const lawn = uc === "lawn";
        const farm = uc === "farms";
        const v = verticalFromUseCase(uc);

        document.getElementById("section_symptoms").classList.toggle("hidden", mode === "goals");
        document.getElementById("section_goals").classList.toggle("hidden", mode === "problems");
        const gvCard = document.getElementById("card_goal_vertical");
        if (gvCard) gvCard.classList.add("hidden");
        const cardIntent = document.getElementById("card_intent");
        if (cardIntent) cardIntent.classList.toggle("hidden", mode === "problems");

        const need = document.getElementById("goals_need_place");
        if (need) need.classList.toggle("hidden", mode !== "goals" || v !== "");
        document.getElementById("goal_panel_lawn").classList.toggle("hidden", v !== "lawn");
        document.getElementById("goal_panel_garden").classList.toggle("hidden", v !== "garden");
        document.getElementById("goal_panel_farm").classList.toggle("hidden", v !== "farm");

        const patchyCard = document.getElementById("card_patchy_lawn");
        const flowerCard = document.getElementById("card_poor_flowering");
        if (patchyCard) patchyCard.classList.toggle("hidden", garden || farm);
        if (flowerCard) flowerCard.classList.toggle("hidden", lawn);
        if (garden || farm) {
          const p = document.getElementById("patchy_lawn");
          if (p) p.checked = false;
        }
        if (lawn) {
          const f = document.getElementById("poor_flowering");
          if (f) f.checked = false;
        }

        if (garden) {
          setTxt("yellowing_title", "Yellowing leaves");
          setTxt("yellowing_desc", "Pale leaves on veg, flowers, shrubs, or pots.");
          setTxt("slow_growth_title", "Slow or weak growth");
          setTxt("slow_growth_desc", "Not putting on leaves, looking tired.");
          setTxt("weak_roots_title", "Weak roots or transplant shock");
          setTxt("weak_roots_desc", "Wilts easily, or struggles after planting.");
          setTxt("fungal_title", "Disease or fungus");
          setTxt("fungal_desc", "Spots, mildew, or rotting leaves.");
        } else if (lawn) {
          setTxt("yellowing_title", "Yellowing");
          setTxt("yellowing_desc", "Pale or yellow turf, chlorosis.");
          setTxt("slow_growth_title", "Slow growth");
          setTxt("slow_growth_desc", "Not thickening up or growing out.");
          setTxt("weak_roots_title", "Weak roots");
          setTxt("weak_roots_desc", "Pulls up easily, struggles in heat or dry.");
          setTxt("fungal_title", "Fungal issues");
          setTxt("fungal_desc", "Circular patches or disease pressure.");
        } else {
          setTxt("yellowing_title", "Yellowing");
          setTxt("yellowing_desc", "Pale lawn or yellow leaves on plants.");
          setTxt("slow_growth_title", "Slow growth");
          setTxt("slow_growth_desc", "Not filling out — lawn or plants.");
          setTxt("weak_roots_title", "Weak roots");
          setTxt("weak_roots_desc", "Pulls up easily, wilts in heat, or struggles after planting.");
          setTxt("fungal_title", "Fungal issues");
          setTxt("fungal_desc", "Spots, mildew, circular patches, or disease pressure.");
        }
      }
      function syncRecModeUI() { syncPlaceUI(); }
      function syncGoalPanels() { syncPlaceUI(); }
      document.querySelectorAll('input[name="rec_mode"]').forEach((r) => r.addEventListener("change", syncPlaceUI));
      document.getElementById("goal_vertical").addEventListener("change", syncPlaceUI);
      document.getElementById("use_case").addEventListener("change", syncPlaceUI);
      syncPlaceUI();

      function updatePhHint() {
        const hint = document.getElementById("soil_ph_hint");
        const phEl = document.getElementById("soil_ph");
        const method = document.getElementById("soil_ph_method").value;
        if (!hint || !phEl) return;
        const v = phEl.value;
        if (v === "") {
          hint.textContent = "Leave blank if you haven’t tested.";
          return;
        }
        const ph = parseFloat(v);
        if (Number.isNaN(ph)) return;
        const cacl2 = method === "cacl2";
        let msg = "";
        if (cacl2) {
          if (ph < 5.3) msg = "Acidic (CaCl₂) — lime/dolomite may help; skip extra lime if you already applied recently.";
          else if (ph <= 6.5) msg = "Near-neutral (CaCl₂) — no lime from pH alone.";
          else msg = "Alkaline (CaCl₂) — skip lime. Iron chlorosis is more likely; chelated iron is preferred.";
        } else {
          if (ph < 6.0) msg = "Acidic (water) — lime/dolomite may help nutrient availability.";
          else if (ph <= 7.2) msg = "Near-neutral (water) — no lime from pH alone.";
          else msg = "Alkaline (water) — skip lime. Iron and some traces lock out more easily.";
        }
        hint.textContent = msg;
      }
      document.getElementById("soil_ph").addEventListener("input", updatePhHint);
      document.getElementById("soil_ph_method").addEventListener("change", updatePhHint);

      function payload() {
        const mode = document.querySelector('input[name="rec_mode"]:checked').value;
        const p = { recommendation_mode: mode };
        for (const id of ids) {
          const el = document.getElementById(id);
          if (!el) continue;
          if (el.type === "checkbox") p[id] = el.checked;
          else p[id] = el.value;
        }
        const phEl = document.getElementById("soil_ph");
        const omEl = document.getElementById("organic_matter_pct");
        if (phEl && phEl.value !== "") p.soil_ph = phEl.value;
        p.soil_ph_method = document.getElementById("soil_ph_method").value;
        if (omEl && omEl.value !== "") p.organic_matter_pct = omEl.value;
        if (mode === "problems") {
          p.intent = "rescue_mode";
        } else if (mode === "goals") {
          const gv = verticalFromUseCase(document.getElementById("use_case").value);
          p.goal_vertical = gv;
          p.goal_weights = {};
          const panel = document.getElementById("goal_panel_" + gv);
          if (panel) {
            panel.querySelectorAll(".goal-cb:checked").forEach((cb) => {
              const k = cb.getAttribute("data-goal-key");
              if (k) p.goal_weights[k] = 1.0;
            });
          }
        }
        return p;
      }

      function esc(s) {
        return String(s ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
      }

      function prodImg(p) {
        if (!p || !p.image_url) return "";
        return `<img src="${esc(p.image_url)}" alt="" />`;
      }
      function viewLink(p) {
        const u = p && (p.product_url || p.productUrl);
        if (!u) return "";
        return `<a class="link" href="${esc(u)}" target="_blank" rel="noopener noreferrer">View product</a>`;
      }
      function roleHint(p) {
        const map = {
          visual: "Colour",
          nutrition: "Feed",
          biology: "Soil life",
          uptake: "Uptake",
          structure: "Soil",
          chemistry: "Soil pH",
          bundle: "Kit",
        };
        return (p && map[p.role_type]) || "";
      }
      function oneLiner(p) {
        if (!p) return "";
        if (p.short_reason) return p.short_reason;
        const t = p.problem_explanation || p.why_this_works || "";
        const cut = t.split(". ")[0].trim();
        if (!cut) return "";
        return /[.!?]$/.test(cut) ? cut : cut + ".";
      }
      function extraWhy(p) {
        if (!p) return "";
        const extra = [p.problem_explanation, p.why_this_works]
          .filter(Boolean)
          .find((t) => t !== p.short_reason);
        if (!extra) return "";
        return `<details class="more"><summary>Why this helps</summary><p>${esc(extra)}</p></details>`;
      }
      function applyTip(p) {
        if (!p) return "";
        const bits = [p.apply_rate, p.apply_frequency, p.mix_note].filter(Boolean);
        if (!bits.length) return "";
        return `<details class="more"><summary>How to apply</summary><p>${esc(bits.join(" "))}</p></details>`;
      }
      const USAGE_META = [
        { key: "mix_together", label: "Mix as concentrates" },
        { key: "independent", label: "Apply independently" },
        { key: "water_in", label: "Water in" },
        { key: "soil_drench", label: "Soil drench" },
        { key: "foliar", label: "Foliar" },
        { key: "fertigation", label: "Fertigation" },
        { key: "hydroponic", label: "Hydroponic" },
        { key: "hose_on", label: "Hose on" },
        { key: "mix_with_iron", label: "Can mix with iron" },
      ];
      function usageMark(key) {
        if (key === "mix_together") return `<span class="use-mix" aria-hidden="true"><i></i><i></i></span>`;
        return `<i class="use-dot ${esc(key)}" aria-hidden="true"></i>`;
      }
      function renderUsage(p) {
        const flags = (p && p.usage) || {};
        const chips = USAGE_META.filter((u) => flags[u.key]).map((u) =>
          `<span class="use-chip">${usageMark(u.key)}${esc(u.label)}</span>`
        );
        return chips.length ? `<div class="use-row">${chips.join("")}</div>` : "";
      }
      function prodCopy(p, extras) {
        return `
          <div class="prod-body">
            ${renderUsage(p)}
            <p class="prod-why">${esc(oneLiner(p) || (extras && extras.why) || "")}</p>
            <div class="prod-actions">${viewLink(p)}</div>
            ${(extras && extras.detail) || extraWhy(p)}
            ${applyTip(p)}
          </div>`;
      }
      function heroCard(p, kicker) {
        if (!p) return "";
        return `
          <article class="hero">
            <p class="kicker">${esc(kicker)}</p>
            <div class="prod">
              ${prodImg(p)}
              <div class="prod-title">
                <h4 class="prod-name">${esc(p.name)}</h4>
              </div>
              ${prodCopy(p)}
            </div>
          </article>`;
      }
      function stepRow(p, n) {
        if (!p) return "";
        const role = roleHint(p);
        return `
          <div class="row-card has-step">
            <div class="step-num">${n}</div>
            ${prodImg(p)}
            <div class="prod-title">
              ${role ? `<div class="role-tag">${esc(role)}</div>` : ""}
              <div class="prod-name">${esc(p.name)}</div>
            </div>
            ${prodCopy(p)}
          </div>`;
      }
      function compactProduct(p, kicker) {
        if (!p) return "";
        return `
          <div class="row-card">
            ${prodImg(p)}
            <div class="prod-title">
              ${kicker ? `<div class="role-tag">${esc(kicker)}</div>` : ""}
              <div class="prod-name">${esc(p.name)}</div>
            </div>
            ${prodCopy(p)}
          </div>`;
      }
      function championCol(slot, audience) {
        const p = slot && slot.product;
        if (!p) return "";
        const detail = slot.description
          ? `<details class="more"><summary>Best for</summary><p>${esc(slot.description)}</p></details>`
          : extraWhy(p);
        return `
          <div class="row-card champ-card">
            <div class="role-tag champ-audience">${esc(audience)}</div>
            ${prodImg(p)}
            <div class="prod-title">
              <div class="prod-name">${esc(p.name)}</div>
            </div>
            ${prodCopy(p, { why: slot.label, detail })}
          </div>`;
      }
      function renderChampionPair(cp) {
        if (!cp || !cp.fairway || !cp.greens_grade) return "";
        return `
          <div>
            <p class="kicker">Choose your fertiliser</p>
            <p class="muted" style="margin:0 0 8px;">Everyday lawns vs fine, low-cut turf.</p>
            <div class="pair">
              ${championCol(cp.fairway, "Everyday lawns")}
              ${championCol(cp.greens_grade, "Fine / low-cut")}
            </div>
          </div>`;
      }
      function tipBox(text) {
        if (!text) return "";
        return `<div class="tip">${text}</div>`;
      }
      function foldBlock(title, inner) {
        if (!inner) return "";
        return `<details class="fold"><summary>${esc(title)}</summary>${inner}</details>`;
      }

      function renderFriendly(data) {
        const ex = data.explanations || {};
        const goalsMode = ex.input && ex.input.recommendation_mode === "goals";
        const cp = data.champion_turf_pair || ex.champion_turf_pair;
        const champIds = new Set(["886", "892"]);
        const showChampionPair = !!(cp && cp.fairway && cp.greens_grade);
        const primaryIsChamp = data.primary && champIds.has(String(data.primary.id));

        let html = "";
        if (ex.input && ex.input.warning) {
          html += tipBox(esc(ex.input.warning));
        }
        const soilNotes = (ex.input && Array.isArray(ex.input.soil_test_notes)) ? ex.input.soil_test_notes : [];
        if (soilNotes.length) {
          html += tipBox(soilNotes.map(esc).join(" "));
        }

        if (showChampionPair && primaryIsChamp) {
          html += renderChampionPair(cp);
        } else {
          html += heroCard(data.primary, "Start with");
          if (goalsMode && data.primary_fertiliser && data.primary_fertiliser.id !== data.primary.id) {
            html += `<div><p class="kicker">Feed with</p>${compactProduct(data.primary_fertiliser, "Feed")}</div>`;
          }
          if (showChampionPair) {
            html += foldBlock("Lawn fertiliser options", renderChampionPair(cp));
          }
        }

        const stackNotes = Array.isArray(ex.notes) ? ex.notes.filter(Boolean) : [];
        const extras = [];
        if (Array.isArray(data.stack) && data.stack.length > 1) {
          const pfId = data.primary_fertiliser ? data.primary_fertiliser.id : null;
          const skipChamp = showChampionPair && (primaryIsChamp || goalsMode);
          data.stack.slice(1).forEach((p) => {
            if (!p) return;
            if (pfId && p.id === pfId) return;
            if (skipChamp && champIds.has(String(p.id))) return;
            extras.push(p);
          });
        }
        if (extras.length) {
          html += `<div>
            <p class="kicker">Then add</p>
            <div class="step-list">${extras.map((p, i) => stepRow(p, i + 1)).join("")}</div>
          </div>`;
        }
        if (stackNotes.length) {
          html += tipBox(stackNotes.map(esc).join("<br/>"));
        }

        if (Array.isArray(data.upgrade_path) && data.upgrade_path.length) {
          const nested = `<p class="muted" style="margin:0 0 8px;">Kits if you’d rather one mix than a few bottles.</p>
            <div class="step-list">${data.upgrade_path.map((p) => compactProduct(p, "Kit")).join("")}</div>`;
          html += foldBlock("Or use a kit", nested);
        }

        const why = Array.isArray(ex.choice_summary) ? ex.choice_summary.filter(Boolean) : [];
        if (why.length) {
          html += foldBlock(
            "Why we chose these",
            `<ul class="why-list">${why.map((line) => `<li>${esc(line)}</li>`).join("")}</ul>`
          );
        }

        document.getElementById("friendly").innerHTML = html || `<div class="empty">No recommendation returned.</div>`;
      }

      const intentLabels = {
        establishment_mode: "Just planting",
        maintenance_mode: "Keep it healthy",
        performance_mode: "Best results",
      };
      const placeLabels = {
        lawn: "Lawn",
        garden_beds: "Garden",
      };
      function summarizeAnswers() {
        const mode = document.querySelector('input[name="rec_mode"]:checked').value;
        const uc = document.getElementById("use_case").value;
        const season = document.getElementById("season").value;
        const intent = document.getElementById("intent").value;
        const parts = [
          placeLabels[uc] || "Place not set",
          mode === "goals" ? "Improve results" : "Fix a problem",
        ];
        if (mode === "goals" && intentLabels[intent]) parts.push(intentLabels[intent]);
        if (season && season !== "unknown") {
          parts.push(season.charAt(0).toUpperCase() + season.slice(1));
        }
        return parts.join(" · ");
      }
      function collapseQuestions() {
        document.getElementById("ask_wrap").classList.add("is-collapsed");
        document.getElementById("ask_panel").classList.add("hidden");
        document.getElementById("ask_summary").classList.remove("hidden");
        document.getElementById("ask_summary_text").textContent = summarizeAnswers();
        document.getElementById("actions").classList.add("hidden");
      }
      function expandQuestions() {
        document.getElementById("ask_wrap").classList.remove("is-collapsed");
        document.getElementById("ask_panel").classList.remove("hidden");
        document.getElementById("ask_summary").classList.add("hidden");
        document.getElementById("ask_summary_text").textContent = "";
        document.getElementById("actions").classList.remove("hidden");
      }
      document.getElementById("edit_answers").addEventListener("click", () => {
        expandQuestions();
        document.getElementById("ask_wrap").scrollIntoView({ behavior: "smooth", block: "start" });
      });

      document.getElementById("run").addEventListener("click", async () => {
        const btn = document.getElementById("run");
        btn.disabled = true;
        btn.textContent = "Working…";
        try {
          const res = await fetch("/api/recommend", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload())
          });
          const data = await res.json();
          renderFriendly(data);
          collapseQuestions();
          document.getElementById("results_heading").scrollIntoView({ behavior: "smooth", block: "start" });
        } catch (err) {
          document.getElementById("friendly").innerHTML = `<div class="empty">Couldn’t get a recommendation. Try again.</div>`;
        } finally {
          btn.disabled = false;
          btn.textContent = "Get recommendation";
        }
      });

      function resetForm() {
        // dropdown defaults
        document.getElementById("intent").value = "maintenance_mode";
        document.getElementById("season").value = "unknown";
        document.getElementById("use_case").value = "";
        document.getElementById("confidence_level").value = "somewhat_sure";
        document.getElementById("soil_ph").value = "";
        document.getElementById("soil_ph_method").value = "water";
        document.getElementById("organic_matter_pct").value = "";
        const phHint = document.getElementById("soil_ph_hint");
        if (phHint) phHint.textContent = "Leave blank if you haven’t tested.";
        document.querySelector('input[name="rec_mode"][value="problems"]').checked = true;
        document.getElementById("goal_vertical").value = "lawn";
        // Goal panel follows "Where are you using it?" — do not force lawn.
        document.querySelectorAll(".goal-cb").forEach((cb) => { cb.checked = false; });

        // checkboxes
        [
          "yellowing","slow_growth","weak_roots","nutrient_lockout","patchy_lawn","poor_flowering","compaction","poor_water_retention","fungal_issues",
          "sandy","clay","acidic","alkaline","low_organic_matter","hydrophobic"
        ].forEach((id) => {
          const el = document.getElementById(id);
          if (el) el.checked = false;
        });
        syncRecModeUI();
        syncGoalPanels();

        // outputs
        expandQuestions();
        document.getElementById("friendly").innerHTML = `<div class="empty">Fill in the form and tap Get recommendation.</div>`;
      }
      document.getElementById("reset").addEventListener("click", resetForm);
      document.getElementById("reset_collapsed").addEventListener("click", resetForm);
    </script>
    </main>
  </body>
</html>
"""


@app.post("/api/recommend")
async def api_recommend(request: Request) -> dict[str, Any]:
    body = await request.json()
    payload = _to_payload(body or {})
    rec = recommend(payload, catalog_csv_path=CATALOG_CSV)

    def product_obj(p: Any) -> dict[str, Any]:
        return {
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "role_type": p.role_type.value,
            "image_url": getattr(p, "image_url", None),
            "product_url": getattr(p, "product_url", None),
            "short_reason": getattr(p, "short_reason", None),
            "problem_explanation": getattr(p, "problem_explanation", None),
            "why_this_works": getattr(p, "why_this_works", None),
            "apply_rate": getattr(p, "apply_rate", None),
            "apply_frequency": getattr(p, "apply_frequency", None),
            "mix_note": getattr(p, "mix_note", None),
            "usage": getattr(p, "usage_flags", None) or {},
        }

    ex = rec.explanations
    out: dict[str, Any] = {
        "input": payload,
        "primary": product_obj(rec.primary),
        "stack": [product_obj(p) for p in rec.stack],
        "upgrade_path": [product_obj(p) for p in rec.upgrade_path],
        "explanations": ex,
        "champion_turf_pair": ex.get("champion_turf_pair"),
    }
    if rec.primary_fertiliser is not None:
        out["primary_fertiliser"] = product_obj(rec.primary_fertiliser)
    else:
        out["primary_fertiliser"] = None
    return out

