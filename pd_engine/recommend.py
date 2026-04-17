from __future__ import annotations

from pathlib import Path

from .bundles import bundle_override_decision, top_bundles
from .catalog import Catalog
from .champion_turf import (
    CHAMPION_FAIRWAY_ID,
    CHAMPION_GREENS_ID,
    FAIRWAY_BLURB,
    FAIRWAY_LABEL,
    FAIRWAY_TAG,
    GREENS_BLURB,
    GREENS_LABEL,
    GREENS_TAG,
    champion_turf_pair_warranted,
)
from .goal_layer import effective_goal_weights
from .intent import build_user_input
from .scoring import Weights, score_product, sort_scored
from .stacking import build_stack, build_stack_goals
from .types import Recommendation, RoleType, UserInput, ScoredProduct


def _champion_turf_pair(
    catalog: Catalog,
    user: UserInput,
    product_dict,
    scored_sorted: list[ScoredProduct],
) -> dict[str, object] | None:
    """Surface both CHAMPION SKUs with tags only when scoring/goal weighting favours them vs the catalog."""
    if not champion_turf_pair_warranted(user, scored_sorted):
        return None
    by_id = {p.id: p for p in catalog.products}
    fair = by_id.get(CHAMPION_FAIRWAY_ID)
    greens = by_id.get(CHAMPION_GREENS_ID)
    if fair is None or greens is None:
        return None
    return {
        "title": "CHAMPION professional turf fertilisers",
        "subtitle": "Both are valid turf nutrition options — choose by mowing height, maintenance intensity, and how precise the surface must be.",
        "fairway": {
            "tag": FAIRWAY_TAG,
            "label": FAIRWAY_LABEL,
            "description": FAIRWAY_BLURB,
            "product": product_dict(fair),
        },
        "greens_grade": {
            "tag": GREENS_TAG,
            "label": GREENS_LABEL,
            "description": GREENS_BLURB,
            "product": product_dict(greens),
        },
    }


def _goals_primary_fertiliser(scored_sorted: list[ScoredProduct], user: UserInput):
    """Highest-scored NUTRITION product for goals mode (explicit fertiliser line in UI)."""
    if user.recommendation_mode != "goals":
        return None
    for sp in scored_sorted:
        if sp.product.role_type == RoleType.NUTRITION:
            return sp.product
    return None


def recommend(
    raw_input: dict,
    *,
    catalog_csv_path: str | Path = Path(__file__).resolve().parents[1] / "plant_doctor_recommendation_engine_template.csv",
    max_stack: int = 4,
    weights: Weights | None = None,
) -> Recommendation:
    """
    Main entry point.

    Input is a dict so you can feed it from UI, API, or an LLM parser.
    Output is a fully structured Recommendation object (deterministic).
    """
    user: UserInput = build_user_input(raw_input)
    w = weights or Weights()

    catalog = Catalog.from_csv(catalog_csv_path)
    scored = [score_product(p, user, weights=w) for p in catalog.products]
    scored_sorted = sort_scored(scored)

    def product_dict(p) -> dict:
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

    bundle_decision = bundle_override_decision(user)
    upgrade = top_bundles(scored_sorted, user=user, limit=3)

    def input_snapshot() -> dict:
        snap = {
            "recommendation_mode": user.recommendation_mode,
            "goal_vertical": user.goal_vertical,
            "goal_weights": user.goal_weights,
            "use_case": user.use_case,
        }
        if user.recommendation_mode == "goals" and not user.goal_weights:
            snap["warning"] = "No goals selected — pick at least one goal, or results will be weak."
        elif user.recommendation_mode == "goals" and user.goal_vertical and user.goal_weights:
            egw = effective_goal_weights(user)
            if egw:
                snap["effective_goal_weights"] = egw
        return snap

    if bundle_decision.should_override and upgrade:
        primary = upgrade[0]
        stack = [primary]

        # Even when we override to a bundle, we still generate the best
        # “build it yourself” individual stack for transparency.
        non_bundle_scored = [sp for sp in scored_sorted if sp.product.role_type != RoleType.BUNDLE]
        if user.recommendation_mode == "goals":
            individual_plan = (
                build_stack_goals(non_bundle_scored, user, max_stack=max_stack)
                if non_bundle_scored
                else None
            )
        else:
            individual_plan = build_stack(non_bundle_scored, user, max_stack=max_stack) if non_bundle_scored else None

        champ = _champion_turf_pair(catalog, user, product_dict, scored_sorted)
        fert_primary = (
            None
            if (user.recommendation_mode == "goals" and champ is not None)
            else (_goals_primary_fertiliser(scored_sorted, user) if user.recommendation_mode == "goals" else None)
        )
        explanations = {
            "bundle_override": True,
            "bundle_reason": bundle_decision.reason,
            "intent": user.intent,
            "confidence": user.confidence,
            "input": input_snapshot(),
            "champion_turf_pair": champ,
            "individual_plan": (
                None
                if individual_plan is None
                else {
                    "primary": product_dict(individual_plan.primary),
                    "stack": [product_dict(p) for p in individual_plan.stack],
                    "notes": individual_plan.notes,
                }
            ),
            "top_candidates": [
                {
                    "id": sp.product.id,
                    "name": sp.product.name,
                    "role_type": sp.product.role_type.value,
                    "score": sp.score,
                    "breakdown": sp.breakdown,
                }
                for sp in scored_sorted[:10]
            ],
        }
        return Recommendation(
            intent=user.intent,
            season=user.season,
            primary=primary,
            stack=stack,
            upgrade_path=upgrade[1:],
            explanations=explanations,
            primary_fertiliser=fert_primary,
        )

    # Normal mode: prefer individual products as the core plan.
    # Bundles are suggested as upgrades unless override triggers.
    non_bundle_scored = [sp for sp in scored_sorted if sp.product.role_type != RoleType.BUNDLE]
    if user.recommendation_mode == "goals":
        plan = build_stack_goals(non_bundle_scored or scored_sorted, user, max_stack=max_stack)
    else:
        plan = build_stack(non_bundle_scored or scored_sorted, user, max_stack=max_stack)

    champ = _champion_turf_pair(catalog, user, product_dict, scored_sorted)
    fert_primary = (
        None
        if (user.recommendation_mode == "goals" and champ is not None)
        else (_goals_primary_fertiliser(scored_sorted, user) if user.recommendation_mode == "goals" else None)
    )

    # Upgrade path: bundles appear as a “shortcut” option.
    upgrade_path = []
    if upgrade:
        if user.confidence <= 0.6 or user.intent in ("rescue_mode", "diagnosis_mode"):
            upgrade_path = upgrade[:2]
        else:
            upgrade_path = upgrade[:1]

    explanations = {
        "bundle_override": False,
        "intent": user.intent,
        "confidence": user.confidence,
        "input": input_snapshot(),
        "champion_turf_pair": champ,
        "notes": plan.notes,
        "top_candidates": [
            {
                "id": sp.product.id,
                "name": sp.product.name,
                "role_type": sp.product.role_type.value,
                "score": sp.score,
                "breakdown": sp.breakdown,
            }
            for sp in scored_sorted[:10]
        ],
    }

    return Recommendation(
        intent=user.intent,
        season=user.season,
        primary=plan.primary,
        stack=plan.stack,
        upgrade_path=upgrade_path,
        explanations=explanations,
        primary_fertiliser=fert_primary,
    )

