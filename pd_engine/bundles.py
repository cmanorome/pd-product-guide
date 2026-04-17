from __future__ import annotations

from dataclasses import dataclass

from .types import Product, RoleType, ScoredProduct, UserInput

def _bundle_matches_goals_vertical(product: Product, user: UserInput) -> bool:
    """
    In goals mode, drop bundles whose CSV goal-column totals skew to another vertical
    (e.g. no garden-heavy bundles when lawn goals are selected).
    """
    if user.recommendation_mode != "goals" or not user.goal_vertical:
        return True
    if product.role_type != RoleType.BUNDLE:
        return True
    lawn_tot = sum(float(v) for v in product.lawn_goal_scores.values())
    garden_tot = sum(float(v) for v in product.garden_goal_scores.values())
    farm_tot = sum(float(v) for v in product.farm_goal_scores.values())
    gv = user.goal_vertical
    if gv == "lawn":
        return garden_tot <= lawn_tot
    if gv == "garden":
        return lawn_tot <= garden_tot
    if gv == "farm":
        return max(lawn_tot, garden_tot) <= farm_tot
    return True


@dataclass(frozen=True)
class BundleDecision:
    should_override: bool
    reason: str | None


def bundle_override_decision(user: UserInput) -> BundleDecision:
    if user.recommendation_mode == "goals":
        active_goals = [k for k, v in user.goal_weights.items() if float(v) >= 0.35]
        if user.confidence <= 0.5 and len(active_goals) >= 4:
            return BundleDecision(
                True,
                "Many goals selected with lower confidence — a full-system bundle is suggested.",
            )
        return BundleDecision(False, None)

    # Core triggers from your spec (symptom / soil mode)
    active_problems = [k for k, v in user.problems.items() if float(v) >= 0.35]
    overlap = (float(user.problems.get("nutrient_lockout", 0.0)) >= 0.5) and (
        float(user.problems.get("compaction", 0.0)) >= 0.35
        or float(user.problems.get("poor_water_retention", 0.0)) >= 0.35
        or float(user.problems.get("hydrophobic", 0.0)) >= 0.35  # may appear via soils in some payloads
    )

    if user.intent in ("rescue_mode", "diagnosis_mode") and user.confidence <= 0.55:
        return BundleDecision(True, "Low confidence in rescue/diagnosis: default to full-system bundle.")
    if len(active_problems) >= 3:
        return BundleDecision(True, "Multiple overlapping problems detected: default to a bundle.")
    if user.confidence <= 0.45 and len(active_problems) >= 2:
        return BundleDecision(True, "Low confidence with multiple issues: default to a bundle.")
    if overlap:
        return BundleDecision(True, "Soil limitation + lockout overlap: default to a bundle.")
    return BundleDecision(False, None)


def top_bundles(
    scored: list[ScoredProduct],
    *,
    user: UserInput | None = None,
    limit: int = 3,
) -> list[Product]:
    bundles = [
        sp
        for sp in scored
        if sp.product.role_type == RoleType.BUNDLE
        and (user is None or _bundle_matches_goals_vertical(sp.product, user))
    ]
    bundles_sorted = sorted(bundles, key=lambda s: s.score, reverse=True)
    return [b.product for b in bundles_sorted[:limit]]

