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
      :root { --green: #22B14C; --ink: #111827; --muted: #6b7280; --line: #e5e7eb; --bg: #f6f7f8; }
      body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin: 0; background: var(--bg); color: var(--ink); }
      .container { max-width: 820px; margin: 24px auto; padding: 0 16px 48px; }
      h2 { font-size: 22px; }
      h3 { font-size: 16px; margin: 22px 0 10px; }
      .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
      .card { border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; background: white; }
      .card h4 { margin: 0 0 8px 0; font-size: 14px; }
      label { display:block; font-size: 12px; color:#374151; margin-bottom: 4px; }
      input, select { width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 8px; box-sizing: border-box; }
      .check { display:flex; gap:10px; align-items:flex-start; }
      .check input { width:auto; margin-top: 3px; }
      .check .txt { flex:1; }
      .check .txt .title { font-weight: 600; font-size: 14px; }
      .check .txt .desc { font-size: 12px; color: var(--muted); margin-top: 2px; }
      button { padding: 10px 16px; border: 0; border-radius: 10px; background: var(--green); color: white; cursor:pointer; font-weight: 600; }
      button.secondary { background: white; color: var(--ink); border: 1px solid var(--line); font-weight: 500; }
      button:disabled { opacity: 0.65; cursor: default; }
      .muted { color: var(--muted); font-size: 13px; line-height: 1.45; }
      .hidden { display: none !important; }
      .mode-card { margin-bottom: 14px; }
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

      .results { display: flex; flex-direction: column; gap: 14px; margin-top: 8px; }
      .kicker { font-size: 11px; letter-spacing: 0.04em; text-transform: uppercase; color: var(--muted); font-weight: 700; margin: 0 0 6px; }
      .hero { background: white; border: 1px solid var(--line); border-radius: 14px; padding: 16px; }
      .hero-main { display: flex; gap: 14px; align-items: flex-start; }
      .hero img, .row-card img { width: 72px; height: 72px; object-fit: cover; border-radius: 10px; border: 1px solid var(--line); background: #fff; }
      .row-card img { width: 52px; height: 52px; }
      .prod-name { font-size: 16px; font-weight: 700; margin: 0 0 4px; }
      .prod-why { color: #374151; font-size: 14px; line-height: 1.4; margin: 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
      .role-tag { font-size: 11px; color: var(--muted); font-weight: 600; margin-bottom: 2px; }
      .prod-actions { display: flex; gap: 10px; align-items: center; margin-top: 8px; flex-wrap: wrap; }
      .link { color: var(--green); font-weight: 600; font-size: 13px; text-decoration: none; }
      .step-list { display: flex; flex-direction: column; gap: 8px; }
      .row-card { display: flex; gap: 12px; align-items: flex-start; background: white; border: 1px solid var(--line); border-radius: 12px; padding: 12px; }
      .step-num { flex: 0 0 24px; height: 24px; border-radius: 999px; background: var(--green); color: white; font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; margin-top: 2px; }
      .tip { font-size: 13px; color: #374151; background: #f0faf3; border-radius: 10px; padding: 10px 12px; line-height: 1.45; }
      details.more { margin-top: 6px; }
      details.more summary { cursor: pointer; color: var(--muted); font-size: 12px; }
      details.more p { margin: 8px 0 0; font-size: 13px; color: #374151; line-height: 1.45; }
      .pair { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
      @media (max-width: 640px) { .pair { grid-template-columns: 1fr; } .hero-main { flex-direction: column; } }
      .empty { color: var(--muted); font-size: 14px; padding: 16px 0; }
    </style>
  </head>
  <body>
    <div class="container">
      <div style="display:flex; gap:12px; align-items:baseline; justify-content:space-between; flex-wrap:wrap;">
        <h2 style="margin:0;">Plant Doctor Product Guide</h2>
      </div>
      <p class="muted">Tell us what’s going on. We’ll suggest what to use first, then what to add.</p>

    <div class="card mode-card">
      <label style="margin-bottom:8px;">I want to</label>
      <div class="mode-row">
        <label><input type="radio" name="rec_mode" value="problems" checked /><span>Fix a problem</span></label>
        <label><input type="radio" name="rec_mode" value="goals" /><span>Improve results</span></label>
      </div>
    </div>

    <div class="grid">
      <div class="card" id="card_intent">
        <label>Stage</label>
        <select id="intent">
          <option value="establishment_mode">Just planting / establishing</option>
          <option value="maintenance_mode" selected>Keep it healthy</option>
          <option value="performance_mode">Push for best results</option>
        </select>
      </div>
      <div class="card">
        <label>Season</label>
        <select id="season">
          <option value="unknown">Unknown</option>
          <option value="spring">Spring</option>
          <option value="summer">Summer</option>
          <option value="autumn">Autumn</option>
          <option value="winter">Winter</option>
        </select>
      </div>
      <div class="card hidden" id="card_goal_vertical">
        <label>Goal area</label>
        <select id="goal_vertical">
          <option value="lawn">Lawn goals</option>
          <option value="garden">Garden goals</option>
          <option value="farm">Farm goals</option>
        </select>
      </div>
      <div class="card" id="card_use_case">
        <label>Where are you using it?</label>
        <select id="use_case">
          <option value="">Not sure</option>
          <option value="lawn">Lawn</option>
          <option value="garden_beds">Garden beds</option>
          <option value="pots">Pots / planters</option>
          <option value="indoor_plants">Indoor plants</option>
          <option value="farms">Farm / acreage</option>
        </select>
      </div>
      <div class="card">
        <label>How sure are you?</label>
        <select id="confidence_level">
          <option value="not_sure">Not sure</option>
          <option value="somewhat_sure" selected>Somewhat sure</option>
          <option value="very_sure">Very sure</option>
        </select>
      </div>
    </div>

    <div id="section_goals" class="hidden">
      <h3>What do you want?</h3>
      <p class="muted">Tick one or more. These change with where you’re using it.</p>
      <div id="goals_need_place" class="tip hidden">Choose where you’re using it above, and we’ll show lawn, garden, or farm goals.</div>
      <div id="goal_panel_lawn" class="grid hidden">
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="deep_green_colour"/><div class="txt"><div class="title">Deep green colour</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="thickening_and_density"/><div class="txt"><div class="title">Thickening and density</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="fast_recovery_from_stress"/><div class="txt"><div class="title">Fast recovery from stress</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="weed_suppression_through_dominance"/><div class="txt"><div class="title">Weed suppression through dominance</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="low_maintenance_resilience"/><div class="txt"><div class="title">Low maintenance resilience</div></div></div></div>
      </div>
      <div id="goal_panel_garden" class="grid hidden">
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="strong_flowering_and_fruiting"/><div class="txt"><div class="title">More flowers, fruit and veg</div><div class="desc">Blooms, cropping, and productive plants.</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="improved_soil_fertility"/><div class="txt"><div class="title">Richer soil over time</div><div class="desc">Biology, structure, and nutrient holding.</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="root_development_transplant"/><div class="txt"><div class="title">Stronger roots and transplanting</div><div class="desc">New plantings, seedlings, and establishment.</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="pest_and_disease_resilience"/><div class="txt"><div class="title">Pest and disease resilience</div><div class="desc">Tougher plants under pressure.</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="consistent_growth_across_seasons"/><div class="txt"><div class="title">Steady growth through the year</div><div class="desc">Less boom-and-bust between seasons.</div></div></div></div>
      </div>
      <div id="goal_panel_farm" class="grid hidden">
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="yield_increase"/><div class="txt"><div class="title">Yield increase</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="soil_efficiency"/><div class="txt"><div class="title">Soil efficiency</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="water_efficiency"/><div class="txt"><div class="title">Water efficiency</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="crop_uniformity"/><div class="txt"><div class="title">Crop uniformity</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="reduced_input_dependency"/><div class="txt"><div class="title">Reduced input dependency over time</div></div></div></div>
      </div>
    </div>

    <div id="section_symptoms">
    <h3>What’s wrong?</h3>
    <div class="grid">
      <div class="card">
        <div class="check"><input id="yellowing" type="checkbox"/><div class="txt"><div class="title" id="yellowing_title">Yellowing</div><div class="desc" id="yellowing_desc">Pale lawn or yellow leaves on plants.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="slow_growth" type="checkbox"/><div class="txt"><div class="title" id="slow_growth_title">Slow growth</div><div class="desc" id="slow_growth_desc">Not filling out — lawn or plants.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="weak_roots" type="checkbox"/><div class="txt"><div class="title" id="weak_roots_title">Weak roots</div><div class="desc" id="weak_roots_desc">Pulls up easily, wilts in heat, or struggles after planting.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="nutrient_lockout" type="checkbox"/><div class="txt"><div class="title">Nutrient lockout</div><div class="desc">Fertilised but no response, symptoms persist.</div></div></div>
      </div>
      <div class="card" id="card_patchy_lawn">
        <div class="check"><input id="patchy_lawn" type="checkbox"/><div class="txt"><div class="title">Patchy lawn</div><div class="desc">Uneven growth, thin areas.</div></div></div>
      </div>
      <div class="card" id="card_poor_flowering">
        <div class="check"><input id="poor_flowering" type="checkbox"/><div class="txt"><div class="title">Poor flowering or fruiting</div><div class="desc">Few blooms, small fruit, or plants that won’t crop.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="compaction" type="checkbox"/><div class="txt"><div class="title">Compaction</div><div class="desc">Hard ground, poor drainage, poor root penetration.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="poor_water_retention" type="checkbox"/><div class="txt"><div class="title">Poor water retention</div><div class="desc">Dries quickly, needs frequent watering.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="fungal_issues" type="checkbox"/><div class="txt"><div class="title" id="fungal_title">Fungal issues</div><div class="desc" id="fungal_desc">Spots, mildew, circular patches, or disease pressure.</div></div></div>
      </div>
    </div>
    </div>

    <div id="section_soil">
    <h3>Soil</h3>
    <div class="grid">
      <div class="card">
        <div class="check"><input id="sandy" type="checkbox"/><div class="txt"><div class="title">Sandy</div><div class="desc">Drains fast, nutrients leach.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="clay" type="checkbox"/><div class="txt"><div class="title">Clay</div><div class="desc">Heavy, holds water, compacts easily.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="acidic" type="checkbox"/><div class="txt"><div class="title">Acidic</div><div class="desc">Low pH. Skip if you enter a measured pH.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="alkaline" type="checkbox"/><div class="txt"><div class="title">Alkaline</div><div class="desc">High pH. Skip if you enter a measured pH.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="low_organic_matter" type="checkbox"/><div class="txt"><div class="title">Low organic matter</div><div class="desc">Poor soil life and nutrient buffering.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="hydrophobic" type="checkbox"/><div class="txt"><div class="title">Hydrophobic (water repellent)</div><div class="desc">Water beads/runs off, dry patch.</div></div></div>
      </div>
    </div>
    </div>

    <details class="fold" id="section_soil_test">
    <summary>I have a soil test (optional)</summary>
    <p class="muted">pH is the most useful number. Home kits are usually water pH; Australian labs are often CaCl₂.</p>
    <div class="grid">
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

    <div class="actions">
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
      function heroCard(p, kicker) {
        if (!p) return "";
        return `
          <article class="hero">
            <p class="kicker">${esc(kicker)}</p>
            <div class="hero-main">
              ${prodImg(p)}
              <div>
                <h4 class="prod-name">${esc(p.name)}</h4>
                <p class="prod-why">${esc(oneLiner(p))}</p>
                <div class="prod-actions">${viewLink(p)}</div>
                ${extraWhy(p)}
              </div>
            </div>
          </article>`;
      }
      function stepRow(p, n) {
        if (!p) return "";
        const role = roleHint(p);
        return `
          <div class="row-card">
            <div class="step-num">${n}</div>
            ${prodImg(p)}
            <div>
              ${role ? `<div class="role-tag">${esc(role)}</div>` : ""}
              <div class="prod-name" style="font-size:15px;">${esc(p.name)}</div>
              <p class="prod-why">${esc(oneLiner(p))}</p>
              <div class="prod-actions">${viewLink(p)}</div>
              ${extraWhy(p)}
            </div>
          </div>`;
      }
      function compactProduct(p, kicker) {
        if (!p) return "";
        return `
          <div class="row-card">
            ${prodImg(p)}
            <div>
              ${kicker ? `<div class="role-tag">${esc(kicker)}</div>` : ""}
              <div class="prod-name" style="font-size:15px;">${esc(p.name)}</div>
              <p class="prod-why">${esc(oneLiner(p))}</p>
              <div class="prod-actions">${viewLink(p)}</div>
              ${extraWhy(p)}
            </div>
          </div>`;
      }
      function championCol(slot, audience) {
        const p = slot && slot.product;
        if (!p) return "";
        const detail = slot.description
          ? `<details class="more"><summary>Best for</summary><p>${esc(slot.description)}</p></details>`
          : extraWhy(p);
        return `
          <div class="row-card" style="flex-direction:column; gap:8px;">
            <div class="role-tag">${esc(audience)}</div>
            <div style="display:flex; gap:10px; align-items:flex-start;">
              ${prodImg(p)}
              <div>
                <div class="prod-name" style="font-size:15px;">${esc(p.name)}</div>
                <p class="prod-why">${esc(oneLiner(p) || slot.label || "")}</p>
                <div class="prod-actions">${viewLink(p)}</div>
                ${detail}
              </div>
            </div>
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

        document.getElementById("friendly").innerHTML = html || `<div class="empty">No recommendation returned.</div>`;
      }

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
          document.getElementById("results_heading").scrollIntoView({ behavior: "smooth", block: "start" });
        } catch (err) {
          document.getElementById("friendly").innerHTML = `<div class="empty">Couldn’t get a recommendation. Try again.</div>`;
        } finally {
          btn.disabled = false;
          btn.textContent = "Get recommendation";
        }
      });

      document.getElementById("reset").addEventListener("click", () => {
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
        document.getElementById("friendly").innerHTML = `<div class="empty">Fill in the form and tap Get recommendation.</div>`;
      });
    </script>
    </div>
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

