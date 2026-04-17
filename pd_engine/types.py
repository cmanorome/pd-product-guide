from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class RoleType(str, Enum):
    SOIL_STRUCTURE = "soil_structure"
    SOIL_CHEMISTRY = "soil_chemistry"
    BIOLOGY = "biology"
    UPTAKE = "uptake"
    NUTRITION = "nutrition"
    VISUAL = "visual"
    BUNDLE = "bundle"


Intent = Literal[
    "rescue_mode",
    "maintenance_mode",
    "performance_mode",
    "establishment_mode",
    "diagnosis_mode",
]

Season = Literal["spring", "summer", "autumn", "winter", "unknown"]

ProblemKey = Literal[
    "yellowing",
    "slow_growth",
    "weak_roots",
    "nutrient_lockout",
    "patchy_lawn",
    "compaction",
    "poor_water_retention",
    "fungal_issues",
]

SoilKey = Literal[
    "sandy",
    "clay",
    "acidic",
    "alkaline",
    "low_organic_matter",
    "hydrophobic",
]

UseCaseKey = Literal["lawn", "garden_beds", "indoor_plants", "pots", "farms"]

RecommendationMode = Literal["problems", "goals"]
GoalVertical = Literal["lawn", "garden", "farm"]


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    category: str
    role_type: RoleType

    # Optional ecommerce assets (from VISUAL CODE column)
    image_url: str | None = None
    product_url: str | None = None

    # Scores: 0-5 for problems, 1-3 for soil tags, 0-3 season relevance
    problem_scores: dict[ProblemKey, float] = field(default_factory=dict)
    soil_scores: dict[SoilKey, float] = field(default_factory=dict)
    use_case_scores: dict[UseCaseKey, float] = field(default_factory=dict)  # 0..1 in CSV
    # GOALS - LAWNS / GARDENS / FARMS (rankings from CSV; typically 0–5)
    lawn_goal_scores: dict[str, float] = field(default_factory=dict)
    garden_goal_scores: dict[str, float] = field(default_factory=dict)
    farm_goal_scores: dict[str, float] = field(default_factory=dict)
    seasonal_scores: dict[Season, float] = field(default_factory=dict)

    # System tags (boolean)
    improves_soil_structure: bool = False
    improves_biology: bool = False
    improves_uptake: bool = False
    improves_fertiliser_efficiency: bool = False
    improves_water_infiltration: bool = False
    improves_visual_greening: bool = False

    # Compatibility tags / hazards (boolean flags derived from catalog)
    is_iron_based: bool = False
    is_lime_based: bool = False
    is_iron_sulphate: bool = False

    # Free-text reasoning hooks (optional)
    short_reason: str | None = None
    problem_explanation: str | None = None
    why_this_works: str | None = None
    app_logic_notes: str | None = None


@dataclass(frozen=True)
class UserInput:
    intent: Intent
    season: Season = "unknown"
    use_case: UseCaseKey | None = None

    # "problems" = symptom + soil weighting; "goals" = CSV goal-segment weighting
    recommendation_mode: RecommendationMode = "problems"
    # Which goal block to use (lawn / garden / farm) when recommendation_mode is "goals"
    goal_vertical: GoalVertical | None = None
    # Selected goals for that vertical (internal keys -> 0..1 weight, usually 1.0 when checked)
    goal_weights: dict[str, float] = field(default_factory=dict)

    problems: dict[ProblemKey, float] = field(default_factory=dict)  # 0..1 intensity
    soils: dict[SoilKey, float] = field(default_factory=dict)  # 0..1 confidence

    # 0..1: how confident we are in diagnosis. Low triggers bundle override.
    confidence: float = 0.6


@dataclass(frozen=True)
class ScoredProduct:
    product: Product
    score: float
    breakdown: dict[str, float]
    reasons: list[str]


@dataclass(frozen=True)
class Recommendation:
    intent: Intent
    season: Season
    primary: Product
    # Problems: primary + layered steps (may include nutrition). Goals: foundation primary + non-NUTRITION
    # supports only; fertiliser is primary_fertiliser or the CHAMPION pair in explanations.
    stack: list[Product]
    upgrade_path: list[Product]  # bundle suggestions (shown last in UI)
    explanations: dict[str, object]  # structured explainability payload
    # Goals: top-scoring NUTRITION when CHAMPION pair is not used (champion_turf_pair covers fertiliser slot).
    primary_fertiliser: Product | None = None

