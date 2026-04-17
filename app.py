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
      body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin: 0; background: #f9fafb; }
      .container { max-width: 980px; margin: 24px auto; padding: 0 16px; }
      .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
      .card { border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px; background: white; }
      .card h4 { margin: 0 0 8px 0; font-size: 14px; color: #111827; }
      .pill { display:inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; border: 1px solid #e5e7eb; background: #f9fafb; color:#111827; }
      .stack { display:flex; flex-direction:column; gap:10px; }
      .stack-item { border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px; background: white; }
      .stack-item .meta { display:flex; gap:8px; flex-wrap:wrap; margin-top: 6px; }
      .row { display:flex; gap: 10px; align-items:center; justify-content:space-between; }
      label { display:block; font-size: 12px; color:#374151; margin-bottom: 4px; }
      input, select { width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 8px; }
      .check { display:flex; gap:10px; align-items:flex-start; }
      .check input { width:auto; margin-top: 2px; }
      .check .txt { flex:1; }
      .check .txt .title { font-weight: 600; color:#111827; }
      .check .txt .desc { font-size: 12px; color:#6b7280; margin-top: 2px; }
      button { padding: 10px 14px; border: 0; border-radius: 10px; background:#22B14C; color: white; cursor:pointer; }
      button.secondary { background:#22B14C; }
      pre { background: #0b1020; color: #e5e7eb; padding: 14px; border-radius: 10px; overflow:auto; }
      .muted { color:#6b7280; font-size: 12px; }
      .hidden { display: none !important; }
      .mode-card { width: 100%; max-width: 100%; box-sizing: border-box; }
      /* Radios stay small; labels get room so text doesn’t squash (side‑by‑side when wide, wrap on narrow). */
      .mode-row {
        display: flex; flex-wrap: wrap; gap: 12px 16px; width: 100%; align-items: flex-start;
      }
      .mode-row label {
        display: flex; gap: 10px; align-items: flex-start; cursor: pointer;
        font-size: 14px; color: #111827; line-height: 1.45;
        flex: 1 1 280px;
        min-width: min(100%, 260px);
        max-width: 100%;
        box-sizing: border-box;
        padding: 10px 12px; border: 1px solid #e5e7eb; border-radius: 10px; background: #fafafa;
      }
      .mode-row label input[type="radio"] { width: auto; margin-top: 3px; flex-shrink: 0; }
      .mode-row label span.lbl { flex: 1; min-width: 0; }
      .champion-pair-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        gap: 14px;
        margin-top: 12px;
      }
      .champion-slot {
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 12px;
        background: #fafafa;
      }
      .champion-slot-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
        margin-bottom: 8px;
      }
      .champion-slot-title { font-size: 13px; font-weight: 600; color: #111827; }
      .champion-notice {
        font-size: 12px;
        color: #4b5563;
        line-height: 1.45;
        margin-bottom: 10px;
        padding: 8px 10px;
        background: #f3f4f6;
        border-radius: 8px;
        border-left: 3px solid #22B14C;
      }
      .champion-visual {
        display: flex;
        gap: 12px;
        align-items: flex-start;
      }
      .stack-group > h4 { margin: 0 0 4px 0; font-size: 14px; color: #111827; }
      .stack-group-body {
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin-top: 10px;
      }
    </style>
  </head>
  <body>
    <div class="container">
      <div style="display:flex; gap:12px; align-items:baseline; justify-content:space-between; flex-wrap:wrap;">
        <h2 style="margin:0;">Plant Doctor Product Guide</h2>
        <div class="muted">Virtual agronomist recommendations</div>
      </div>
      <p class="muted">Choose <strong>symptoms</strong> to diagnose issues, or <strong>goals</strong> for outcome-based picks (lawn / garden / farm). <strong>Soil conditions</strong> and <strong>season</strong> apply in both modes.</p>

    <div class="card mode-card" style="margin-bottom:14px;">
      <label style="margin-bottom:8px;">Recommendation style</label>
      <div class="mode-row">
        <label><input type="radio" name="rec_mode" value="problems" checked /><span class="lbl">Symptoms (fix problems) — use the problem checkboxes below.</span></label>
        <label><input type="radio" name="rec_mode" value="goals" /><span class="lbl">Goals (what I want to achieve) — use lawn / garden / farm goal rankings.</span></label>
      </div>
    </div>

    <div class="grid">
      <div class="card" id="card_intent">
        <label>Intent (goals only)</label>
        <select id="intent">
          <option value="establishment_mode">Establishment</option>
          <option value="maintenance_mode" selected>Maintenance</option>
          <option value="performance_mode">Performance</option>
        </select>
        <div class="muted" style="margin-top:6px;">Symptom mode always uses <strong>rescue-style</strong> weighting (fix the problem). Intent only applies to goals.</div>
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
        <div class="muted" style="margin-top:6px;">Seasonal relevance applies in <strong>both</strong> symptom and goal modes.</div>
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
        <label>How sure are you about your selections?</label>
        <select id="confidence_level">
          <option value="not_sure">Not sure</option>
          <option value="somewhat_sure" selected>Somewhat sure</option>
          <option value="very_sure">Very sure</option>
        </select>
        <div class="muted" style="margin-top:6px;">
          This helps the engine decide whether to recommend a single product stack or a full “bundle” when things are uncertain.
        </div>
      </div>
    </div>

    <div id="section_goals" class="hidden">
      <h3>Goals</h3>
      <p class="muted">Tick one or more outcomes below. Scores use the <strong>GOALS – LAWNS / GARDENS / FARMS</strong> columns in your catalog. Soil and season still refine the ranking.</p>
      <div id="goal_panel_lawn" class="grid">
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="deep_green_colour"/><div class="txt"><div class="title">Deep green colour</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="thickening_and_density"/><div class="txt"><div class="title">Thickening and density</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="fast_recovery_from_stress"/><div class="txt"><div class="title">Fast recovery from stress</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="weed_suppression_through_dominance"/><div class="txt"><div class="title">Weed suppression through dominance</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="low_maintenance_resilience"/><div class="txt"><div class="title">Low maintenance resilience</div></div></div></div>
      </div>
      <div id="goal_panel_garden" class="grid hidden">
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="strong_flowering_and_fruiting"/><div class="txt"><div class="title">Strong flowering and fruiting</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="improved_soil_fertility"/><div class="txt"><div class="title">Improved soil fertility over time</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="root_development_transplant"/><div class="txt"><div class="title">Root development and transplant success</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="pest_and_disease_resilience"/><div class="txt"><div class="title">Pest and disease resilience</div></div></div></div>
        <div class="card"><div class="check"><input class="goal-cb" type="checkbox" data-goal-key="consistent_growth_across_seasons"/><div class="txt"><div class="title">Consistent growth across seasons</div></div></div></div>
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
    <h3>Problems (symptoms)</h3>
    <div class="grid">
      <div class="card">
        <div class="check"><input id="yellowing" type="checkbox"/><div class="txt"><div class="title">Yellowing</div><div class="desc">Pale or yellow colour, chlorosis.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="slow_growth" type="checkbox"/><div class="txt"><div class="title">Slow growth</div><div class="desc">Not thickening up or growing out.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="weak_roots" type="checkbox"/><div class="txt"><div class="title">Weak roots</div><div class="desc">Pulls up easily, struggles in heat/dry.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="nutrient_lockout" type="checkbox"/><div class="txt"><div class="title">Nutrient lockout</div><div class="desc">Fertilised but no response, symptoms persist.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="patchy_lawn" type="checkbox"/><div class="txt"><div class="title">Patchy lawn</div><div class="desc">Uneven growth, thin areas.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="compaction" type="checkbox"/><div class="txt"><div class="title">Compaction</div><div class="desc">Hard ground, poor drainage, poor root penetration.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="poor_water_retention" type="checkbox"/><div class="txt"><div class="title">Poor water retention</div><div class="desc">Dries quickly, needs frequent watering.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="fungal_issues" type="checkbox"/><div class="txt"><div class="title">Fungal issues</div><div class="desc">Circular patches, disease pressure.</div></div></div>
      </div>
    </div>
    </div>

    <div id="section_soil">
    <h3>Soil type / conditions</h3>
    <p class="muted">Used in <strong>both</strong> recommendation styles so products match your soil context.</p>
    <div class="grid">
      <div class="card">
        <div class="check"><input id="sandy" type="checkbox"/><div class="txt"><div class="title">Sandy</div><div class="desc">Drains fast, nutrients leach.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="clay" type="checkbox"/><div class="txt"><div class="title">Clay</div><div class="desc">Heavy, holds water, compacts easily.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="acidic" type="checkbox"/><div class="txt"><div class="title">Acidic</div><div class="desc">Low pH, can lock nutrients.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="alkaline" type="checkbox"/><div class="txt"><div class="title">Alkaline</div><div class="desc">High pH, iron/micronutrients can lock out.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="low_organic_matter" type="checkbox"/><div class="txt"><div class="title">Low organic matter</div><div class="desc">Poor soil life and nutrient buffering.</div></div></div>
      </div>
      <div class="card">
        <div class="check"><input id="hydrophobic" type="checkbox"/><div class="txt"><div class="title">Hydrophobic (water repellent)</div><div class="desc">Water beads/runs off, dry patch.</div></div></div>
      </div>
    </div>
    </div>

    <p style="margin-top: 16px;">
      <button id="run">Get Recommendation</button>
      <button id="reset" class="secondary" style="margin-left:8px;">Reset</button>
    </p>

    <h3>Result</h3>
    <div id="friendly" class="stack">
      <div class="stack-item">
        <div class="muted">Click “Get Recommendation”.</div>
      </div>
    </div>

    <script>
      const ids = [
        "intent","season","use_case","confidence_level",
        "yellowing","slow_growth","weak_roots","nutrient_lockout","patchy_lawn","compaction","poor_water_retention","fungal_issues",
        "sandy","clay","acidic","alkaline","low_organic_matter","hydrophobic"
      ];
      function syncRecModeUI() {
        const mode = document.querySelector('input[name="rec_mode"]:checked').value;
        document.getElementById("section_symptoms").classList.toggle("hidden", mode === "goals");
        document.getElementById("section_goals").classList.toggle("hidden", mode === "problems");
        const u = document.getElementById("card_use_case");
        if (u) u.classList.toggle("hidden", mode === "goals");
        const gvCard = document.getElementById("card_goal_vertical");
        if (gvCard) gvCard.classList.toggle("hidden", mode === "problems");
        const cardIntent = document.getElementById("card_intent");
        if (cardIntent) cardIntent.classList.toggle("hidden", mode === "problems");
        const goalsMode = mode === "goals";
        if (goalsMode) {
          const uc = document.getElementById("use_case");
          if (uc) uc.value = "";
        }
      }
      function syncGoalPanels() {
        const gv = document.getElementById("goal_vertical").value;
        document.getElementById("goal_panel_lawn").classList.toggle("hidden", gv !== "lawn");
        document.getElementById("goal_panel_garden").classList.toggle("hidden", gv !== "garden");
        document.getElementById("goal_panel_farm").classList.toggle("hidden", gv !== "farm");
      }
      document.querySelectorAll('input[name="rec_mode"]').forEach((r) => r.addEventListener("change", syncRecModeUI));
      document.getElementById("goal_vertical").addEventListener("change", syncGoalPanels);
      syncRecModeUI();
      syncGoalPanels();

      function payload() {
        const mode = document.querySelector('input[name="rec_mode"]:checked').value;
        const p = { recommendation_mode: mode };
        for (const id of ids) {
          const el = document.getElementById(id);
          if (!el) continue;
          if (el.type === "checkbox") p[id] = el.checked;
          else p[id] = el.value;
        }
        if (mode === "problems") {
          p.intent = "rescue_mode";
        } else if (mode === "goals") {
          const gv = document.getElementById("goal_vertical").value;
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

      /** Recommendation / what this fixes / why this works — shared by product cards and CHAMPION slots. */
      function productExplBlock(p) {
        if (!p) return "";
        const shortReason = p.short_reason ? `<div class="muted" style="margin-top:8px;"><strong>Recommendation:</strong> ${esc(p.short_reason)}</div>` : "";
        const problemExpl = p.problem_explanation ? `<div class="muted" style="margin-top:8px;"><strong>What this fixes:</strong> ${esc(p.problem_explanation)}</div>` : "";
        const whyWorks = p.why_this_works ? `<div class="muted" style="margin-top:8px;"><strong>Why it works:</strong> ${esc(p.why_this_works)}</div>` : "";
        if (!shortReason && !problemExpl && !whyWorks) return "";
        return `<div style="margin-top:10px;">${shortReason}${problemExpl}${whyWorks}</div>`;
      }

      function productCardInner(title, p, extraPills=[]) {
        if (!p) return "";
        const pills = [
          `<span class="pill">${esc(p.role_type)}</span>`,
          ...(p.category ? [`<span class="pill">${esc(p.category)}</span>`] : []),
          ...extraPills.map(x => `<span class="pill">${esc(x)}</span>`)
        ].join("");
        const img = p.image_url ? `<img src="${esc(p.image_url)}" alt="${esc(p.name)}" style="width:72px;height:72px;object-fit:cover;border-radius:10px;border:1px solid #e5e7eb;" />` : "";
        const link = p.product_url ? `<a href="${esc(p.product_url)}" target="_blank" rel="noopener noreferrer" class="pill" style="text-decoration:none;">View product</a>` : "";
        const explBlock = productExplBlock(p);
        return `
            <div class="row">
              <h4>${esc(title)}</h4>
              <div class="meta">
                <span class="pill">ID: ${esc(p.id)}</span>
                ${link}
              </div>
            </div>
            <div style="display:flex; gap:12px; align-items:center; margin-top: 6px;">
              ${img}
              <div style="flex:1;">
                <div><strong>${esc(p.name)}</strong></div>
                <div class="meta" style="margin-top:6px;">${pills}</div>
                ${explBlock}
              </div>
            </div>
        `;
      }

      function productCard(title, p, extraPills=[]) {
        if (!p) return "";
        return `<div class="stack-item">${productCardInner(title, p, extraPills)}</div>`;
      }

      function championSlotInner(slot) {
        const p = slot.product;
        if (!p) return "";
        const img = p.image_url
          ? `<img src="${esc(p.image_url)}" alt="${esc(p.name)}" style="width:72px;height:72px;object-fit:cover;border-radius:10px;border:1px solid #e5e7eb;" />`
          : "";
        const productUrl = p.product_url || p.productUrl || "";
        const viewLink = productUrl
          ? `<a href="${esc(productUrl)}" target="_blank" rel="noopener noreferrer" class="pill" style="text-decoration:none;display:inline-block;">View product</a>`
          : "";
        const pills = [
          `<span class="pill">${esc(p.role_type)}</span>`,
          ...(p.category ? [`<span class="pill">${esc(p.category)}</span>`] : []),
        ].join("");
        return `
          <div class="champion-slot">
            <div class="champion-slot-meta">
              <span class="pill">${esc(slot.tag)}</span>
              <span class="champion-slot-title">${esc(slot.label)}</span>
            </div>
            ${slot.description ? `<div class="champion-notice">${esc(slot.description)}</div>` : ""}
            <div class="champion-visual">
              ${img}
              <div style="flex:1; min-width:0;">
                <div><strong>${esc(p.name)}</strong></div>
                <div class="meta" style="margin-top:6px;">
                  <span class="pill">ID: ${esc(p.id)}</span>
                  ${pills}
                </div>
              </div>
            </div>
            ${viewLink ? `<div class="champion-view-row" style="margin-top:10px;">${viewLink}</div>` : ""}
            ${productExplBlock(p)}
          </div>
        `;
      }

      function renderChampionPair(cp) {
        if (!cp || !cp.fairway || !cp.greens_grade) return "";
        return `
          <div class="stack-item">
            <h4 style="margin:0 0 4px 0;">${esc(cp.title)}</h4>
            <div class="muted">${esc(cp.subtitle)}</div>
            <div class="champion-pair-grid">
              ${championSlotInner(cp.fairway)}
              ${championSlotInner(cp.greens_grade)}
            </div>
          </div>
        `;
      }

      function renderFriendly(data) {
        const ex = data.explanations || {};
        const override = ex.bundle_override === true;
        const reason = ex.bundle_reason || "";

        let html = "";
        if (ex.input && ex.input.warning) {
          html += `<div class="stack-item"><div class="muted">${esc(ex.input.warning)}</div></div>`;
        }
        if (override) {
          html += `<div class="stack-item"><div class="pill">Bundle recommended (best match)</div><div class="muted" style="margin-top:6px;">${esc(reason)}</div></div>`;
        }
        html += productCard("Primary product", data.primary);

        const goalsMode = ex.input && ex.input.recommendation_mode === "goals";
        const cp = data.champion_turf_pair || (ex && ex.champion_turf_pair);
        const champFertSlot =
          goalsMode && cp && cp.fairway && cp.greens_grade;
        const showChampionPair =
          cp && cp.fairway && cp.greens_grade && (!goalsMode || champFertSlot);

        if (showChampionPair) {
          html += renderChampionPair(cp);
        } else if (goalsMode && data.primary_fertiliser) {
          if (data.primary_fertiliser.id === data.primary.id) {
            html += `<div class="stack-item"><div class="muted">Your leading <strong>fertiliser</strong> pick matches the primary product above.</div></div>`;
          } else {
            html += productCard("Primary fertiliser", data.primary_fertiliser);
          }
        }

        if (goalsMode && Array.isArray(data.stack) && data.stack.length > 1) {
          const pfId = data.primary_fertiliser ? data.primary_fertiliser.id : null;
          const champIds = champFertSlot ? new Set(["886", "892"]) : null;
          const extra = data.stack.slice(1).filter((p) => {
            if (!p) return false;
            if (pfId && p.id === pfId) return false;
            if (champIds && champIds.has(String(p.id))) return false;
            return true;
          });
          if (extra.length) {
            const nested = extra.map((p, idx) => `<div class="stack-item">${productCardInner(`Additional ${idx + 1}`, p)}</div>`).join("");
            html += `<div class="stack-item stack-group">
              <h4>Additional products</h4>
              <div class="muted">Supporting layers after your primary and fertiliser picks (soil → biology → uptake → optional colour).</div>
              <div class="stack-group-body">${nested}</div>
            </div>`;
          }
        } else if (!goalsMode && Array.isArray(data.stack) && data.stack.length > 1) {
          const nested = data.stack.slice(1).map((p, idx) => `<div class="stack-item">${productCardInner(`Step ${idx + 1}`, p)}</div>`).join("");
          html += `<div class="stack-item stack-group">
            <h4>Recommended steps</h4>
            <div class="muted">These are supporting products layered in the right order (soil → biology → uptake → nutrition → optional quick colour).</div>
            <div class="stack-group-body">${nested}</div>
          </div>`;
        }

        // When bundle override is active, also show the best non-bundle stack.
        if (override && ex.individual_plan && Array.isArray(ex.individual_plan.stack) && ex.individual_plan.stack.length) {
          const nested = ex.individual_plan.stack.map((p, idx) => {
            const title = idx === 0 ? "Individual plan — primary" : `Individual plan — step ${idx}`;
            return `<div class="stack-item">${productCardInner(title, p, ["individual"])}</div>`;
          }).join("");
          html += `<div class="stack-item stack-group">
            <h4>Prefer individual products instead?</h4>
            <div class="muted">Here’s the best “build it yourself” plan using single products (same engine rules, same correct order).</div>
            <div class="stack-group-body">${nested}</div>
          </div>`;
        }

        if (Array.isArray(data.upgrade_path) && data.upgrade_path.length) {
          const nested = data.upgrade_path.map((p) => `<div class="stack-item">${productCardInner("Bundle option", p, ["upgrade"])}</div>`).join("");
          html += `<div class="stack-item stack-group">
            <h4>Upgrade options (bundles)</h4>
            <div class="muted">Use these when the situation is complex or uncertain.</div>
            <div class="stack-group-body">${nested}</div>
          </div>`;
        }

        document.getElementById("friendly").innerHTML = html || `<div class="stack-item"><div class="muted">No recommendation returned.</div></div>`;
      }

      document.getElementById("run").addEventListener("click", async () => {
        const res = await fetch("/api/recommend", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload())
        });
        const data = await res.json();
        renderFriendly(data);
      });

      document.getElementById("reset").addEventListener("click", () => {
        // dropdown defaults
        document.getElementById("intent").value = "maintenance_mode";
        document.getElementById("season").value = "unknown";
        document.getElementById("use_case").value = "";
        document.getElementById("confidence_level").value = "somewhat_sure";
        document.querySelector('input[name="rec_mode"][value="problems"]').checked = true;
        document.getElementById("goal_vertical").value = "lawn";
        document.querySelectorAll(".goal-cb").forEach((cb) => { cb.checked = false; });

        // checkboxes
        [
          "yellowing","slow_growth","weak_roots","nutrient_lockout","patchy_lawn","compaction","poor_water_retention","fungal_issues",
          "sandy","clay","acidic","alkaline","low_organic_matter","hydrophobic"
        ].forEach((id) => {
          const el = document.getElementById(id);
          if (el) el.checked = false;
        });
        syncRecModeUI();
        syncGoalPanels();

        // outputs
        document.getElementById("friendly").innerHTML = `
          <div class="stack-item">
            <div class="muted">Click “Get Recommendation”.</div>
          </div>
        `;
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

