# Plant Doctor Product Guide — how recommendations are decided

Use this when testing the app. It describes **what the engine is trying to do**, not every code path.

The live plan is meant to stay short. Open **Why we chose these** at the bottom of a result for a plain-language recap of that run.

Catalog scores live in `plant_doctor_recommendation_engine_template.csv`. Engine rules live in `pd_engine/`. Changing a CSV cell changes ranking; changing code changes *when* a product is allowed in at all.

---

## 1. Two modes

| Mode in the form | What it optimises for |
| --- | --- |
| **Fix a problem** | Symptoms + soil + where it is used. Intent is always “fix what’s wrong”. |
| **Improve results** | Lawn or garden **goals**. Symptoms are ignored. “Where are you using it?” picks which goal set you see. |

**Where are you using it?** is the main switch between lawn and garden. Lawn stays the primary business path. Garden (beds, veg, flowers, pots) unlocks garden products instead of turf specialists. The form does not offer indoor, planters, or farm / acreage as separate choices.

---

## 2. How a result is built (order of operations)

1. Read the form (symptoms or goals, soil, season, optional soil test).
2. **Score every product** from the CSV.
3. **Drop products that don’t fit** (hard constraints — see section 6).
4. Pick a **primary** (highest valid score).
5. Add **supporting layers** only when that role is warranted (section 5).
6. Show matching **kits** under **Or use a kit** — kits never replace the step-by-step plan.
7. On lawns, sometimes show **Champion Fairway vs Greens Grade** as a choice, not a score split.

Typical stack order (after the hero product):

**Soil structure → soil pH → biology (seaweed) → uptake (humic / Stimulizer) → feed → colour (iron)**

Default cap is **4 products** (5 if nutrient lockout *and* a structure issue are both on).

Biology (seaweed) and uptake are almost always allowed as support layers. Gypsum, lime, wetter, zeolite, fertiliser, and iron only appear when the situation calls for them.

---

## 3. Scoring weights

Each product gets a **base score**, then a **role multiplier**.

### Symptom mode (Fix a problem)

```
base =
  1.40 × problem match
+ 0.90 × soil match
+ 0.85 × use-case match
+ 0.15 × seasonal match
+ 0.08 × synergy
+ targeted bonuses
+ lawn/garden context fit

final = base × role multiplier
```

Problem / soil / season numbers come from the CSV (usually 0–5). Use-case columns are 0 or 1 (Lawn, Garden Beds, Pots, Indoor, Farms).

**Problem match** is the average of the CSV scores for the symptoms the user ticked. Tick yellowing only → use the Yellowing Leaves column. Tick yellowing + slow growth → average of those two columns.

### Goals mode (Improve results)

Goals dominate. Context (soil, place, season, symptoms) is a light overlay:

```
base =
  1.20 × goal CSV fit × goal-alignment multiplier
+ 0.15 × 0.85 × use-case
+ 0.12 × 0.15 × season
+ 0.28 × 0.90 × soil
+ 0.05 × 0.08 × synergy
+ 0.05 × 1.40 × problem   (usually 0 — symptoms are off)
+ pair synergy (small)
+ garden stage bonus
+ lawn/garden context fit

final = base × role multiplier
```

**Goal-alignment multiplier** maps CSV goal fit (0–5) onto about **0.94–1.28** (slightly tighter in rescue-style intent). A product that scores 5/5 on the selected goals gets a lift; a weak fit does not.

If several goals are ticked, no single goal can take more than **42%** of the effective weight.

---

## 4. What “success” means by vertical

These are the built-in priorities **when more than one goal is ticked**. A single ticked goal still drives ranking via that product’s CSV column.

### Lawn

| Goal | Share |
| --- | --- |
| Thickening and density | 28% |
| Fast recovery from stress | 22% |
| Deep green colour | 18% |
| Weed suppression through dominance | 16% |
| Low maintenance resilience | 16% |

Colour is real, but **density and recovery outrank colour** so iron-only answers don’t win every lawn goal.

### Garden

| Goal | Share |
| --- | --- |
| Improved soil fertility over time | 28% |
| Root development and transplant success | 26% |
| Strong flowering and fruiting | 18% |
| Pest and disease resilience | 14% |
| Consistent growth across seasons | 14% |

### Farm

Farm goal columns still exist in the CSV, but **farm / acreage is not a form option**. Testers using the website will only see lawn and garden.

### Stage (goals mode only)

Shown as **Just planting / Keep it healthy / Push for best results**.

- **Planting:** extra weight on roots, soil fertility, density, yield.
- **Keep it healthy:** slight lift on low-maintenance / consistent growth.
- **Best results:** extra weight on colour, density, flowering, yield, uniformity.

Symptom mode does **not** use this dropdown; it always scores as “fix the problem”.

**Complementary pairs** (small bonus if both goals are ticked *and* the product scores ≥ 3 on both):

- Roots + soil fertility
- Water efficiency + soil efficiency
- Density + colour
- Weed suppression + density

---

## 5. Role multipliers

Applied after the base score. This is why a “pretty good” iron product can beat a “pretty good” fertiliser when yellowing is ticked.

| Role | When | Multiplier |
| --- | --- | --- |
| Soil structure (gypsum, wetter, zeolite) | Not maintenance | 1.30 |
| Soil structure | Maintenance | 1.22 |
| Soil chemistry (lime / dolomite) | Acidic, alkaline, or lockout | 1.28 |
| Soil chemistry | Otherwise | 1.05 |
| Biology (seaweed) | Always | 1.20 |
| Uptake (humic / fulvic / Stimulizer) | Always | 1.15 |
| Nutrition (fertiliser) | Goals mode | 1.12 |
| Nutrition | Slow growth, no lockout | 1.25 |
| Nutrition | Other symptom cases | 0.95 |
| Visual (iron colour) | Yellowing ticked | 1.20 |
| Visual | No yellowing | 0.70 |
| Kit / bundle | Scoring only — not used as the plan | 1.10 |

High-nitrogen products (MaxGreen, Activ8EXTRA) are **cut 15%** in **summer if fungal issues** are ticked.

### When a supporting role is allowed in the stack

| Role | Added when |
| --- | --- |
| Soil structure | Clay, sandy, hydrophobic, compaction, or poor water holding |
| Soil chemistry | Acidic, alkaline, or nutrient lockout |
| Biology | Always |
| Uptake | Always |
| Nutrition (symptom mode) | Slow growth, patchy lawn, weak roots, fungal issues, or poor flowering |
| Nutrition (goals mode) | Shown as **Feed with**, not mixed into the same stack loop |
| Visual / colour | Yellowing |

---

## 6. Hard rules (product can score well and still be excluded)

These are pass/fail, not weights.

**Place**

- Flowers, Fruits & Roots is **not** a lawn feed.
- Turf specialists (Champion, Lawn Envy, MaxGreen, lawn kits) are **not** used for garden nutrition.
- Granular bed/turf feeds (Roots, Shoots & Leaves; Champion; FFR granular) are aimed at garden beds, not a dedicated indoor/pot path (those options were removed from the form).

**Soil chemistry**

- Lime / dolomite only if soil is acidic (checkbox or measured pH). Never on alkaline.
- Gypsum only for **clay or compaction** — not for “weak roots” alone (that was pulling gypsum onto garden transplant cases).
- Wetter only for hydrophobic soil or poor water holding.
- Zeolite only for sandy, low organic matter, or lockout.

**Program safety**

- Do not stack two iron products.
- Do not mix lime with iron in the same plan.
- Nutrient lockout: do **not** lead with fertiliser; unlock with biology / uptake / chemistry first.
- Iron can be the **hero** when yellowing is the main issue and lockout is not.
- Liquid iron + seaweed / humic / wetter can share a **program** but not a **tank**. The UI should warn: apply iron on a different day. Stimulizer is the uptake that *can* tank-mix with iron.

**Biology pick**

- Default biology is **Seaweed Secrets**, not neem.
- Neem is used when fungal issues or the garden pest/disease goal is on.

---

## 7. Extra bonuses (symptom mode)

On top of CSV scores, the engine nudges a few named jobs:

| Situation | Nudge |
| --- | --- |
| Lawn + yellowing + iron product | +0.90 (+1.15 if alkaline) |
| Garden / general yellowing + iron | +0.55 |
| Alkaline + yellowing + **Kendon chelate** | extra +0.25 |
| Garden + poor flowering + FFR | +1.05 |
| Garden + slow growth + Roots, Shoots & Leaves or Activ8Mate | +0.40 |
| Garden + weak roots + Roots, Shoots & Leaves | +0.90 |
| Garden + weak roots (no flowering) + FFR | −0.45 (don’t use flower/fruit feed for transplant shock) |

**Lawn vs garden context fit**

- Garden place: garden-only lines (FFR, RSL, garden kits, most humics) **+0.55**. Activ8Mate **+0.35**. Activ8EXTRA **−0.12**. Turf specialists **−1.0** (and they are already blocked).
- Lawn place: products with Lawn = 0 and Garden Beds = 1 **−0.55** (stops RSL stealing turf density goals).

---

## 8. Optional soil test

Leave blank if unused. A measured **pH overrides** acidic/alkaline checkboxes.

| Method | Acidic | Near-neutral | Alkaline |
| --- | --- | --- | --- |
| Water (home kit) | below ~6.0 | 6.0–7.2 | above ~7.2 |
| CaCl₂ (AU lab) | below ~5.3 | 5.3–6.5 | above ~6.5 |

Organic matter **below 2%** is treated as low OM (biology / carbon products become more relevant).

A soil-test entry also slightly increases confidence.

---

## 9. Champion pair (lawns only)

Champion Fairway and Greens Grade are **two intensities of the same turf fertiliser**, not competing SKUs. The UI may show both:

- **Everyday lawns** — Fairway  
- **Fine / low-cut** — Greens Grade  

This block is **off** for garden.

It appears when the user is in a lawn context **and** Champion is competitive vs the rest of the catalog (not on every lawn click). In lawn **goals** mode it must also be near the best goal-match in the catalog.

---

## 10. Kits

Kits are scored like other products but **never become the default plan**, even if many symptoms are ticked.

They only appear under **Or use a kit**. Lawn kits for lawns; garden kits (Gardener’s Choice, soil enhancer packs) for garden users.

---

## 11. What testers should usually see

These are expected *leads*, not the only legal stack. Supporting seaweed / humic / Stimulizer is normal.

| Test | Expect to start with (or feed with) |
| --- | --- |
| Lawn + yellowing | Liquid Iron. Champion pair may also show. Kit fold, not the hero. |
| Lawn + yellowing + alkaline pH (~7.8 water) | Kendon Iron Chelate preferred over sulphate. No lime. |
| Lawn + acidic pH (~5.2 water) | Lime/dolomite allowed if chemistry is in play; skip extra lime if pH is already OK. |
| Lawn + thickening / density goal | Champion pair as the fertiliser choice; not Flowers, Fruits & Roots. |
| Garden beds + yellowing | Liquid iron is still valid (chlorosis). Kits should be **garden** kits, not Lawn Lovers. No Champion. |
| Garden beds + slow growth | Roots, Shoots & Leaves (or Activ8Mate). |
| Garden beds + poor flowering, or flowering goal | Flowers, Fruits & Roots liquid. |
| Garden beds + planting + root goal | Roots, Shoots & Leaves leads. |
| Garden beds + richer soil goal | Humic / seaweed first; Activ8Mate as the feed. |
| Clay + compaction (any place) | Gypsum is allowed. |
| Weak roots **without** clay/compaction | **Not** gypsum; garden → seaweed / RSL style feed. |
| Nutrient lockout | Don’t lead with NPK; biology/uptake/chemistry first. |
| Iron + seaweed in the same plan | Warning to apply iron on a different day. |

---

## 12. How to review a run

1. Check **Where are you using it?** — lawn vs garden changes the catalog more than any weighting.
2. Read the hero + numbered steps. Roles should match the table in section 5.
3. Open **Why we chose these** — it should mention the place, the symptoms or goals, and each step’s job.
4. Open **Or use a kit** only if you are checking bundles.
5. If a product feels wrong, ask: **was it scored high**, or **was a better product blocked** (section 6)? Blocked products cannot appear no matter how well they score.

CSV columns testers care about: Yellowing Leaves, Slow Growth, Weak Roots, Nutrient Lockout, Patchy Lawn, Fungal Issues, Compacted Soil, Poor Water Retention, Lawn / Garden Beds / Pots / Indoor / Farms, the soil columns, season columns, and the goal columns for that vertical.
