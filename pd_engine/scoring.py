from __future__ import annotations

from dataclasses import dataclass

from .goal_layer import (
    effective_goal_weights,
    goal_alignment_01,
    goal_multiplier,
    goal_pair_synergy_bonus,
)
from .types import (
    Intent,
    Product,
    RoleType,
    ScoredProduct,
    Season,
    UserInput,
)


@dataclass(frozen=True)
class Weights:
    problem: float = 1.0
    soil: float = 0.7
    use_case: float = 0.6
    goal_segment: float = 1.0  # CSV lawn/garden/farm goal rankings
    seasonal: float = 0.25
    synergy: float = 0.2

    # Role multipliers
    role_mult_soil_structure: float = 1.35
    role_mult_biology: float = 1.25
    role_mult_uptake: float = 1.18
    role_mult_nutrition: float = 1.0
    role_mult_visual: float = 0.75
    role_mult_bundle: float = 1.45


def role_multiplier(
    role: RoleType,
    *,
    intent: Intent,
) -> float:
    # Intent can skew “aggressiveness” a bit without breaking the role ordering.
    if role == RoleType.SOIL_STRUCTURE:
        m = 1.35 if intent != "maintenance_mode" else 1.25
    elif role == RoleType.BIOLOGY:
        m = 1.25
    elif role == RoleType.UPTAKE:
        m = 1.18
    elif role == RoleType.NUTRITION:
        m = 1.0
    elif role == RoleType.VISUAL:
        m = 0.75 if intent != "rescue_mode" else 0.85
    elif role == RoleType.BUNDLE:
        m = 1.45
    else:
        m = 1.0
    return m


def _dot01(user: dict[str, float], prod: dict[str, float]) -> float:
    # user weights are 0..1. prod are typically 0..5 or 1..3; normalize per-key.
    total = 0.0
    denom = 0.0
    for k, w in user.items():
        if w <= 0:
            continue
        denom += w
        total += w * float(prod.get(k, 0.0))
    if denom <= 0:
        return 0.0
    return total / denom


def _goal_scores_for_product(product: Product, vertical: str | None) -> dict[str, float]:
    if vertical == "lawn":
        return product.lawn_goal_scores
    if vertical == "garden":
        return product.garden_goal_scores
    if vertical == "farm":
        return product.farm_goal_scores
    return {}


def _garden_stage_alignment_bonus(product: Product, user: UserInput) -> tuple[float, str | None]:
    """
    Nudge named garden lines (FFR vs RSL) so stage/intent matches real use:
    establishment + root development favours the vegetative / planting line (RSL)
    over reproductive formulations (FFR), even when flowering is also ticked.
    """
    if user.recommendation_mode != "goals" or user.goal_vertical != "garden":
        return 0.0, None
    blob = f"{product.name} {product.category}".lower()

    wf = float(user.goal_weights.get("strong_flowering_and_fruiting", 0.0))
    wr = float(user.goal_weights.get("root_development_transplant", 0.0))
    has_ff = wf >= 0.35
    has_root = wr >= 0.35

    def _ffr_line() -> bool:
        if product.id in ("575", "721"):
            return True
        return "flowers" in blob and "fruit" in blob

    def _rsl_line() -> bool:
        if product.id == "1156":
            return True
        return "roots, shoots" in blob and "leaves" in blob

    # Planting / establishment: vegetative & roots over flower/fruit SKUs when root goal is on
    if user.intent == "establishment_mode" and has_root:
        if _rsl_line():
            return (
                1.72,
                "Establishment / planting — Roots, Shoots & Leaves line (vegetative growth & roots)",
            )
        if has_ff and _ffr_line():
            return (
                0.32,
                "Flower/fruit formulation de-emphasised during establishment when root goal is active",
            )

    if has_ff and _ffr_line():
        return 1.55, "Flowering/fruiting stage product (aligned with selected garden goal)"

    if has_root and _rsl_line():
        return 1.35, "Root establishment / vegetative line (aligned with selected garden goal)"

    return 0.0, None


def score_product(product: Product, user: UserInput, *, weights: Weights) -> ScoredProduct:
    problem_match = _dot01(user.problems, product.problem_scores)  # 0..5-ish
    soil_match = _dot01(user.soils, product.soil_scores)  # 0..3-ish
    use_case_match = 0.0
    if user.use_case:
        use_case_match = float(product.use_case_scores.get(user.use_case, 0.0))  # 0..1

    goal_match = 0.0  # weighted CSV fit under effective goal weights
    eff_goal_w: dict[str, float] = {}
    goal_alignment_0_1 = 0.0
    g_mult = 1.0
    pair_goal_bonus = 0.0
    if user.recommendation_mode == "goals" and user.goal_vertical and user.goal_weights:
        eff_goal_w = effective_goal_weights(user)
        goal_match = _dot01(eff_goal_w, _goal_scores_for_product(product, user.goal_vertical))
        goal_alignment_0_1, _ = goal_alignment_01(product, user.goal_vertical, eff_goal_w)
        g_mult = goal_multiplier(goal_alignment_0_1, user.intent)
        pair_goal_bonus = goal_pair_synergy_bonus(product, user.goal_vertical, eff_goal_w)

    seasonal = 0.0
    if user.season != "unknown":
        seasonal = float(product.seasonal_scores.get(user.season, 0.0))

    # Context inference: treat as “lawn scenario” when lawn-specific problems are selected.
    lawn_context = (
        user.use_case == "lawn"
        or user.goal_vertical == "lawn"
        or (
            user.use_case is None
            and user.goal_vertical is None
            and (
                float(user.problems.get("patchy_lawn", 0.0)) > 0
                or float(user.problems.get("yellowing", 0.0)) > 0
                or float(user.problems.get("slow_growth", 0.0)) > 0
            )
        )
    )

    # Synergy “potential”: rewards multi-function foundations
    synergy = 0.0
    synergy += 0.4 if product.improves_soil_structure else 0.0
    synergy += 0.35 if product.improves_biology else 0.0
    synergy += 0.3 if product.improves_uptake else 0.0
    synergy += 0.2 if product.improves_fertiliser_efficiency else 0.0
    synergy += 0.2 if product.improves_water_infiltration else 0.0
    synergy += 0.15 if product.improves_visual_greening else 0.0

    # Targeted bonuses (symptom mode only)
    targeted_bonus = 0.0
    yellowing = float(user.problems.get("yellowing", 0.0))
    patchy = float(user.problems.get("patchy_lawn", 0.0))
    if user.recommendation_mode == "problems":
        # Lawn + yellowing: pull iron / colour-correction products up strongly (turf chlorosis).
        lawn_yellowing = yellowing >= 0.35 and (
            user.use_case == "lawn" or patchy >= 0.35
        )
        if product.is_iron_based and lawn_yellowing:
            targeted_bonus += 1.15
        elif yellowing >= 0.5 and product.is_iron_based:
            targeted_bonus += 0.55
        if (
            lawn_context
            and product.role_type == RoleType.BUNDLE
            and yellowing >= 0.5
            and patchy >= 0.35
            and product.is_iron_based
        ):
            targeted_bonus += 0.4

    stage_alignment_bonus = 0.0
    stage_note: str | None = None
    if user.recommendation_mode == "goals":
        stage_alignment_bonus, stage_note = _garden_stage_alignment_bonus(product, user)

    if user.recommendation_mode == "goals":
        # Context “engine” (soil, season, use-case, light synergy) × goal multiplier layer.
        context_engine = (
            0.35 * weights.use_case * use_case_match
            + 0.42 * weights.seasonal * seasonal
            + 0.38 * weights.soil * soil_match
            + 0.10 * weights.synergy * synergy
            + 0.05 * weights.problem * problem_match
        )
        base = (
            context_engine * g_mult
            + pair_goal_bonus
            + stage_alignment_bonus
        )
    else:
        base = (
            weights.problem * problem_match
            + weights.soil * soil_match
            + weights.use_case * use_case_match
            + weights.seasonal * seasonal
            + weights.synergy * synergy
            + targeted_bonus
        )

    mult = role_multiplier(
        product.role_type,
        intent=user.intent,
    )
    final = base * mult

    reasons: list[str] = []
    if user.recommendation_mode == "goals":
        reasons.append(
            f"Goal layer: align={goal_alignment_0_1:.2f} × mult={g_mult:.2f} (weighted priorities + intent)"
        )
        reasons.append(f"Goal CSV fit (effective weights): {goal_match:.2f}")
        if pair_goal_bonus > 0:
            reasons.append(f"Complementary goal synergy: +{pair_goal_bonus:.2f}")
        if soil_match > 0:
            reasons.append(f"Soil match: {soil_match:.2f}")
        if stage_alignment_bonus > 0 and stage_note:
            reasons.append(f"Stage alignment: +{stage_alignment_bonus:.2f} ({stage_note})")
    else:
        if problem_match > 0:
            reasons.append(f"Problem match: {problem_match:.2f}")
        if soil_match > 0:
            reasons.append(f"Soil match: {soil_match:.2f}")
    if use_case_match > 0:
        reasons.append(f"Use-case match: {use_case_match:.2f}")
    if seasonal > 0:
        reasons.append(f"Seasonal relevance: {seasonal:.2f}")
    if user.recommendation_mode == "problems" and targeted_bonus > 0:
        reasons.append(f"Targeted bonus: {targeted_bonus:.2f}")
    reasons.append(f"Role priority: {product.role_type.value} × {mult:.2f}")

    return ScoredProduct(
        product=product,
        score=final,
        breakdown={
            "goal_scoring_active": 1.0 if user.recommendation_mode == "goals" else 0.0,
            "problem_match": problem_match,
            "soil_match": soil_match,
            "use_case_match": use_case_match,
            "goal_match": goal_match,
            "goal_alignment_01": goal_alignment_0_1,
            "goal_multiplier": g_mult,
            "pair_goal_synergy": pair_goal_bonus,
            "seasonal": seasonal,
            "synergy": synergy,
            "stage_alignment_bonus": stage_alignment_bonus,
            "targeted_bonus": targeted_bonus,
            "role_multiplier": mult,
            "base": base,
            "final": final,
        },
        reasons=reasons,
    )


def sort_scored(scored: list[ScoredProduct]) -> list[ScoredProduct]:
    return sorted(scored, key=lambda s: s.score, reverse=True)


def season_from_month(month: int) -> Season:
    # Southern hemisphere friendly by default (AU-focused).
    if month in (9, 10, 11):
        return "spring"
    if month in (12, 1, 2):
        return "summer"
    if month in (3, 4, 5):
        return "autumn"
    if month in (6, 7, 8):
        return "winter"
    return "unknown"

