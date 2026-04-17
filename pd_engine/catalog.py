from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from .goal_columns import FARM_GOAL_COLS, GARDEN_GOAL_COLS, LAWN_GOAL_COLS
from .types import Product, RoleType, Season


_PROBLEM_COLS = {
    "yellowing": "Yellowing Leaves",
    "slow_growth": "Slow Growth",
    "compaction": "Compacted Soil",
    "poor_water_retention": "Poor Water Retention",
    "nutrient_lockout": "Nutrient Lockout",
    "patchy_lawn": "Patchy Lawn",
    "fungal_issues": "Fungal Issues",
    "weak_roots": "Weak Roots",
}

_SOIL_COLS = {
    "sandy": "Sandy Soil",
    "clay": "Clay Soil",
    "acidic": "Acidic Soil",
    "alkaline": "Alkaline Soil",
    "low_organic_matter": "Low Organic Matter",
    "hydrophobic": "Hydrophobic Soil",
}

_SEASON_COLS: dict[Season, str] = {
    "spring": "Spring",
    "summer": "Summer",
    "autumn": "Autumn",
    "winter": "Winter",
}

_USE_CASE_COLS = {
    "lawn": "Lawn",
    "garden_beds": "Garden Beds",
    "indoor_plants": "Indoor Plants",
    "pots": "Pots",
    "farms": "Farms",
}


def _to_float(v: str | None, default: float = 0.0) -> float:
    if v is None:
        return default
    s = str(v).strip()
    if s == "":
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def _infer_role_type(category: str, role_raw: str, primary_function: str, name: str) -> RoleType:
    blob = " ".join([category, role_raw, primary_function, name])
    b = _norm(blob)

    if "bundle" in b or "pack" in b or "starter" in b or "pro pack" in b or "system bundle" in b:
        return RoleType.BUNDLE

    if any(k in b for k in ["gypsum", "compaction", "clay buster", "soil wetter", "wetting", "hydrophobic", "drainage"]):
        return RoleType.SOIL_STRUCTURE

    if any(k in b for k in ["lime", "dolomite", "ph", "alkaline", "acidic", "calcium carbonate", "magnesium carbonate"]):
        return RoleType.SOIL_CHEMISTRY

    if any(k in b for k in ["seaweed", "inocul", "microb", "biolog", "biostimul"]):
        return RoleType.BIOLOGY

    if any(k in b for k in ["fulvic", "humic", "chelat", "stimulizer", "uptake", "transport", "efficiency"]):
        return RoleType.UPTAKE

    if any(k in b for k in ["fertiliser", "fertilizer", "npk", "nitrogen", "granular", "slow-release", "controlled-release"]):
        return RoleType.NUTRITION

    if any(k in b for k in ["iron", "green", "greening", "chlorosis", "colour", "color"]):
        return RoleType.VISUAL

    return RoleType.NUTRITION


def _extract_visual_assets(visual_code_html: str) -> tuple[str | None, str | None]:
    """
    The template CSV stores an HTML snippet in the 'VISUAL CODE' column.
    We extract the first <img src="..."> and first <a href="...">.
    """
    s = visual_code_html or ""
    img = None
    url = None

    m_img = re.search(r'<img[^>]+src\s*=\s*"([^"]+)"', s, flags=re.IGNORECASE)
    if m_img:
        img = m_img.group(1).strip()

    m_a = re.search(r'<a[^>]+href\s*=\s*"([^"]+)"', s, flags=re.IGNORECASE)
    if m_a:
        url = m_a.group(1).strip()

    return img or None, url or None


def load_products_from_template_csv(path: str | Path) -> list[Product]:
    p = Path(path)
    with p.open("r", newline="", encoding="utf-8-sig") as f:
        # Template CSV includes a grouping row above the real header.
        # We scan until we find the real header containing "Product Name".
        raw = f.read()

    lines = raw.splitlines(True)
    header_idx = None
    for i, line in enumerate(lines):
        if "Product Name" in line and "SKU" in line and "Role Type" in line:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"Could not locate catalog header row in CSV: {p}")

    with p.open("r", newline="", encoding="utf-8-sig") as f2:
        # Rewind by reopening and skipping lines up to header
        for _ in range(header_idx):
            f2.readline()
        reader = csv.DictReader(f2)
        products: list[Product] = []

        for row in reader:
            name = (row.get("Product Name") or "").strip()
            sku = (row.get("SKU") or "").strip()
            visual_code = (row.get("VISUAL CODE") or "").strip()
            category = (row.get("Category") or "").strip()
            primary_function = (row.get("Primary Function") or "").strip()
            role_raw = (row.get("Role Type") or "").strip()

            if not name or not sku:
                continue

            role_type = _infer_role_type(category, role_raw, primary_function, name)

            problem_scores = {k: _to_float(row.get(col), 0.0) for k, col in _PROBLEM_COLS.items()}
            soil_scores = {k: _to_float(row.get(col), 0.0) for k, col in _SOIL_COLS.items()}
            use_case_scores = {k: _to_float(row.get(col), 0.0) for k, col in _USE_CASE_COLS.items()}
            lawn_goal_scores = {k: _to_float(row.get(col), 0.0) for k, col in LAWN_GOAL_COLS.items()}
            garden_goal_scores = {k: _to_float(row.get(col), 0.0) for k, col in GARDEN_GOAL_COLS.items()}
            farm_goal_scores = {k: _to_float(row.get(col), 0.0) for k, col in FARM_GOAL_COLS.items()}
            seasonal_scores = {season: _to_float(row.get(col), 0.0) for season, col in _SEASON_COLS.items()}

            blob = _norm(" ".join([name, category, primary_function, role_raw]))
            is_iron_sulphate = ("iron sulphate" in blob) or ("ferrous sulphate" in blob)
            is_lime_based = "lime" in blob or "dolomite" in blob or "calcium carbonate" in blob
            is_iron_based = (" iron" in f" {blob}") or ("fe" in blob and "chelate" in blob) or is_iron_sulphate

            # Boolean system tags inferred from roles + keywords
            improves_soil_structure = role_type == RoleType.SOIL_STRUCTURE or any(
                k in blob for k in ["gypsum", "wetting", "wetter", "drainage", "structure", "infiltration"]
            )
            improves_biology = role_type == RoleType.BIOLOGY or any(k in blob for k in ["seaweed", "inocul", "microb"])
            improves_uptake = role_type == RoleType.UPTAKE or any(k in blob for k in ["fulvic", "chelat", "transport"])
            improves_fertiliser_efficiency = any(k in blob for k in ["zeolite", "efficiency", "humic", "fulvic"])
            improves_water_infiltration = any(k in blob for k in ["wetting", "wetter", "hydrophobic", "infiltration"])
            improves_visual_greening = role_type == RoleType.VISUAL or any(k in blob for k in ["greening", "chlorophyll", "iron"])

            image_url, product_url = _extract_visual_assets(visual_code)

            products.append(
                Product(
                    id=sku,
                    name=name,
                    category=category,
                    role_type=role_type,
                    image_url=image_url,
                    product_url=product_url,
                    problem_scores=problem_scores,  # type: ignore[arg-type]
                    soil_scores=soil_scores,  # type: ignore[arg-type]
                    use_case_scores=use_case_scores,  # type: ignore[arg-type]
                    lawn_goal_scores=lawn_goal_scores,
                    garden_goal_scores=garden_goal_scores,
                    farm_goal_scores=farm_goal_scores,
                    seasonal_scores=seasonal_scores,
                    improves_soil_structure=improves_soil_structure,
                    improves_biology=improves_biology,
                    improves_uptake=improves_uptake,
                    improves_fertiliser_efficiency=improves_fertiliser_efficiency,
                    improves_water_infiltration=improves_water_infiltration,
                    improves_visual_greening=improves_visual_greening,
                    is_iron_based=is_iron_based,
                    is_lime_based=is_lime_based,
                    is_iron_sulphate=is_iron_sulphate,
                    short_reason=(row.get("Short Recommendation Reason") or "").strip() or None,
                    problem_explanation=(row.get("Problem Explanation") or "").strip() or None,
                    why_this_works=(row.get("Why This Works") or "").strip() or None,
                    app_logic_notes=(row.get("App Logic considerations") or "").strip() or None,
                )
            )

    return products


@dataclass(frozen=True)
class Catalog:
    products: list[Product]

    @classmethod
    def from_csv(cls, path: str | Path) -> "Catalog":
        return cls(products=load_products_from_template_csv(path))

    def by_role(self, role: RoleType) -> list[Product]:
        return [p for p in self.products if p.role_type == role]

