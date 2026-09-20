from __future__ import annotations

from dataclasses import dataclass

from .constraints import (
    incompatible_with_stack,
    iron_humic_spacing_needed,
    is_gardenish,
    is_valid_primary,
    product_fits_context,
    recommended_max_stack,
    role_is_warranted,
    wants_garden_flowering,
    wants_lawn_deep_green,
)
from .types import Product, RoleType, ScoredProduct, UserInput


ROLE_ORDER: list[RoleType] = [
    RoleType.SOIL_STRUCTURE,
    RoleType.SOIL_CHEMISTRY,
    RoleType.BIOLOGY,
    RoleType.UPTAKE,
    RoleType.NUTRITION,
    RoleType.VISUAL,
]

# If a Lawn Lovers core SKU is close to the role leader, prefer it.
_CORE_PICK_RATIO = 0.85
_FFR_LIQUID = "721"
_ACTIV8 = ("A8M", "A8X")


@dataclass(frozen=True)
class StackPlan:
    primary: Product
    stack: list[Product]
    notes: list[str]


def _preferred_core(product: Product, user: UserInput) -> bool:
    if not product.is_core_range:
        return False
    if is_gardenish(user) and product.id == "A8X":
        return False
    # EDTA chelate stays available on alkaline soil; Liquid Iron is the usual lawn colour pick otherwise.
    if product.id == "LIR" and float(user.soils.get("alkaline", 0.0)) >= 0.35:
        return False
    return True


def _first_eligible(scored: list[ScoredProduct], role: RoleType, stack: list[Product], user: UserInput) -> list[ScoredProduct]:
    iron_in_stack = any(p.is_iron_based for p in stack)
    out: list[ScoredProduct] = []
    for sp in scored:
        if sp.product.role_type != role:
            continue
        if any(p.id == sp.product.id for p in stack):
            continue
        # Prefer seaweed as the default biology layer.
        # Neem only when disease/pest is in play. Worm Magic is added later for tired soils.
        if role == RoleType.BIOLOGY and sp.product.id in ("758", "WMP", "WMB"):
            if sp.product.id == "758":
                fungal = float(user.problems.get("fungal_issues", 0.0)) >= 0.35
                pest_goal = float(user.goal_weights.get("pest_and_disease_resilience", 0.0)) >= 0.35
                if not fungal and not pest_goal:
                    continue
            else:
                continue
        res = incompatible_with_stack(sp.product, stack, user)
        if not res.ok:
            continue
        if sp.product.is_iron_based and any(p.is_iron_based for p in stack):
            continue
        out.append(sp)
    if out:
        return out
    # Second pass: if uptake was skipped for tank-mix, still allow a humic later in the program.
    if iron_in_stack and role == RoleType.UPTAKE:
        for sp in scored:
            if sp.product.role_type != role:
                continue
            if any(p.id == sp.product.id for p in stack):
                continue
            if incompatible_with_stack(sp.product, stack, user).ok:
                out.append(sp)
    return out


def _pick_from_role(scored: list[ScoredProduct], role: RoleType, stack: list[Product], user: UserInput) -> Product | None:
    candidates = _first_eligible(scored, role, stack, user)
    if not candidates:
        return None
    core = next((sp for sp in candidates if _preferred_core(sp.product, user)), None)
    if core is not None:
        return core.product
    return candidates[0].product


def _finish_plan(stack: list[Product], notes: list[str]) -> StackPlan:
    if iron_humic_spacing_needed(stack):
        notes.append(
            "Apply liquid iron on a different day from seaweed, humic, compost tea, or soil wetter — do not mix them in the same sprayer."
        )
    primary = stack[0]
    rest = stack[1:]
    role_rank = {r: i for i, r in enumerate(ROLE_ORDER)}
    rest_sorted = sorted(rest, key=lambda p: role_rank.get(p.role_type, 999))
    return StackPlan(primary=primary, stack=[primary] + rest_sorted, notes=notes)


def _worm_magic_sku(user: UserInput) -> str | None:
    """Pellets for tired/sandy soil; tea for weak roots / transplant. Seaweed stays the default biology pick."""
    low_om = float(user.soils.get("low_organic_matter", 0.0)) >= 0.35
    sandy = float(user.soils.get("sandy", 0.0)) >= 0.35
    weak = float(user.problems.get("weak_roots", 0.0)) >= 0.35
    fertility = float(user.goal_weights.get("improved_soil_fertility", 0.0)) >= 0.35
    roots_goal = float(user.goal_weights.get("root_development_transplant", 0.0)) >= 0.35
    if low_om or sandy or fertility:
        return "WMP"
    if weak or roots_goal:
        return "WMB"
    return None


def _with_worm_magic(
    stack: list[Product],
    scored: list[ScoredProduct],
    user: UserInput,
    cap: int,
) -> list[Product]:
    if any(p.id in ("WMP", "WMB") for p in stack):
        return stack
    sku = _worm_magic_sku(user)
    if not sku or len(stack) >= cap:
        return stack
    if sku == "WMB" and any(p.is_iron_based for p in stack):
        sku = "WMP"
    chosen: Product | None = None
    for sp in scored:
        if sp.product.id == sku:
            chosen = sp.product
            break
    if chosen is None:
        return stack
    if not incompatible_with_stack(chosen, stack, user).ok:
        if sku == "WMB":
            for sp in scored:
                if sp.product.id == "WMP" and incompatible_with_stack(sp.product, stack, user).ok:
                    return stack + [sp.product]
        return stack
    return stack + [chosen]


def _ensure_core_seaweed(
    stack: list[Product],
    scored: list[ScoredProduct],
    user: UserInput,
    cap: int,
) -> list[Product]:
    if any(p.id == "SWS" for p in stack) or len(stack) >= cap:
        return stack
    if not any(p.id in ("WMP", "WMB") for p in stack):
        return stack
    for sp in scored:
        if sp.product.id == "SWS" and incompatible_with_stack(sp.product, stack, user).ok:
            return stack + [sp.product]
    return stack


def _product_by_id(scored: list[ScoredProduct], sku: str) -> Product | None:
    for sp in scored:
        if sp.product.id == sku:
            return sp.product
    return None


def _make_room(stack: list[Product], cap: int, keep: set[str]) -> list[Product]:
    if len(stack) < cap:
        return stack
    out = list(stack)
    for i in range(len(out) - 1, 0, -1):
        if out[i].id not in keep:
            out.pop(i)
            if len(out) < cap:
                return out
    return out


def _append_sku(
    stack: list[Product],
    scored: list[ScoredProduct],
    user: UserInput,
    sku: str,
    cap: int,
    keep: set[str],
) -> list[Product]:
    if any(p.id == sku for p in stack):
        return stack
    prod = _product_by_id(scored, sku)
    if prod is None or not product_fits_context(prod, user).ok:
        return stack
    stack = list(stack)
    keep = set(keep)
    keep.add(stack[0].id)
    keep.add(sku)
    if len(stack) >= cap:
        stack = _make_room(stack, cap, keep)
    if len(stack) >= cap:
        return stack
    return stack + [prod]


def _with_garden_flower_feed(
    stack: list[Product],
    scored: list[ScoredProduct],
    user: UserInput,
    cap: int,
    notes: list[str],
) -> list[Product]:
    if not wants_garden_flowering(user):
        return stack
    keep = {stack[0].id, _FFR_LIQUID, *_ACTIV8, "SWS", "STM"}
    stack = _append_sku(stack, scored, user, _FFR_LIQUID, cap, keep)
    has_ffr = any(p.id in (_FFR_LIQUID, "575") for p in stack)
    has_a8 = any(p.id in _ACTIV8 for p in stack)
    if has_ffr and not has_a8:
        stack = _append_sku(stack, scored, user, "A8M", cap, keep)
        if not any(p.id in _ACTIV8 for p in stack):
            stack = _append_sku(stack, scored, user, "A8X", cap, keep)
    a8 = next((p for p in stack if p.id in _ACTIV8), None)
    if any(p.id == _FFR_LIQUID for p in stack) and a8 is not None:
        a8_label = "Activ8EXTRA" if a8.id == "A8X" else "Activ8Mate"
        notes.append(
            f"Alternate between Flowers, Fruits & Roots and {a8_label} each feed. "
            "FFR is for flowering/fruiting; Activ8 is the regular feed. Do not mix those two in the same sprayer. "
            "Seaweed or Stimulizer can mix with that day's feed."
        )
    return stack


def _with_lawn_iron(
    stack: list[Product],
    scored: list[ScoredProduct],
    user: UserInput,
    cap: int,
) -> list[Product]:
    if not wants_lawn_deep_green(user):
        return stack
    if any(p.is_iron_based or p.id == "LEN" for p in stack):
        return stack
    keep = {stack[0].id, "SWS", "LIR", "STM", "A8X"}
    return _append_sku(stack, scored, user, "LIR", cap, keep)


def _with_humate_note(stack: list[Product], notes: list[str]) -> None:
    if any(p.id == "513" for p in stack):
        notes.append(
            "Spread Humate granules on the top layer of soil, under mulch, or dug in. They do not need to be watered in."
        )


def _with_garden_natives_note(user: UserInput, notes: list[str]) -> None:
    if not is_gardenish(user):
        return
    notes.append(
        "For natives and other sensitive plants, use Seaweed Secrets and Activ8Mate at half strength."
    )


def _apply_calendar_stack_rules(
    stack: list[Product],
    scored: list[ScoredProduct],
    user: UserInput,
    cap: int,
    notes: list[str],
) -> list[Product]:
    stack = _with_garden_flower_feed(stack, scored, user, cap, notes)
    stack = _with_lawn_iron(stack, scored, user, cap)
    _with_garden_natives_note(user, notes)
    _with_humate_note(stack, notes)
    return stack


def _pick_primary_from(scored: list[ScoredProduct], user: UserInput, *, skip_nutrition: bool = False) -> Product | None:
    first: ScoredProduct | None = None
    core: ScoredProduct | None = None
    for sp in scored:
        if skip_nutrition and sp.product.role_type == RoleType.NUTRITION:
            continue
        if not is_valid_primary(sp.product, user).ok:
            continue
        if first is None:
            first = sp
        if core is None and _preferred_core(sp.product, user):
            core = sp
        if first is not None and core is not None:
            break
    if first is None:
        return None
    if core is not None and core.score >= first.score * _CORE_PICK_RATIO:
        return core.product
    return first.product


def build_stack(scored: list[ScoredProduct], user: UserInput, *, max_stack: int | None = None) -> StackPlan:
    """
    Problems mode stacking:
    - best valid primary
    - extra layers only when the user's symptoms/soils warrant that role
    """
    notes: list[str] = []
    cap = max_stack if max_stack is not None else recommended_max_stack(user)

    primary = _pick_primary_from(scored, user)
    if primary is None:
        for sp in scored:
            if sp.product.role_type != RoleType.VISUAL and product_fits_context(sp.product, user).ok:
                primary = sp.product
                notes.append("Fallback primary selection applied.")
                break
    if primary is None:
        for sp in scored:
            if sp.product.role_type != RoleType.VISUAL:
                primary = sp.product
                notes.append("Fallback primary selection applied.")
                break
    if primary is None:
        raise RuntimeError("No valid primary product found.")

    stack: list[Product] = [primary]

    for role in ROLE_ORDER:
        if len(stack) >= cap:
            break
        if role == primary.role_type:
            continue
        if (
            user.recommendation_mode == "problems"
            and role == RoleType.NUTRITION
            and primary.role_type != RoleType.NUTRITION
            and not role_is_warranted(role, user)
        ):
            continue
        if not role_is_warranted(role, user) and role != RoleType.NUTRITION:
            continue
        picked = _pick_from_role(scored, role, stack, user)
        if picked is not None:
            stack.append(picked)

    stack = _with_worm_magic(stack, scored, user, cap)
    stack = _ensure_core_seaweed(stack, scored, user, cap)
    stack = _apply_calendar_stack_rules(stack, scored, user, cap, notes)
    return _finish_plan(stack, notes)


def _garden_feed_should_lead(user: UserInput) -> bool:
    if user.recommendation_mode != "goals" or user.goal_vertical != "garden":
        return False
    gw = user.goal_weights
    flower = float(gw.get("strong_flowering_and_fruiting", 0.0))
    roots = float(gw.get("root_development_transplant", 0.0))
    fertility = float(gw.get("improved_soil_fertility", 0.0))
    if flower >= 0.35 and fertility < 0.35:
        return True
    if user.intent == "establishment_mode" and roots >= 0.35 and flower < 0.35:
        return True
    return False


def _pick_goals_foundation_primary(scored: list[ScoredProduct], user: UserInput) -> tuple[Product, list[str]]:
    notes: list[str] = []
    if wants_garden_flowering(user):
        for sp in scored:
            if sp.product.id == _FFR_LIQUID and is_valid_primary(sp.product, user).ok:
                return sp.product, notes
    if _garden_feed_should_lead(user):
        for sp in scored:
            if sp.product.role_type != RoleType.NUTRITION:
                continue
            if is_valid_primary(sp.product, user).ok:
                return sp.product, notes
    primary = _pick_primary_from(scored, user, skip_nutrition=True)
    if primary is not None:
        return primary, notes
    primary = _pick_primary_from(scored, user)
    if primary is not None:
        return primary, notes
    for sp in scored:
        if sp.product.role_type != RoleType.VISUAL:
            notes.append("Fallback primary selection applied.")
            return sp.product, notes
    raise RuntimeError("No valid primary product found.")


def build_stack_goals(scored: list[ScoredProduct], user: UserInput, *, max_stack: int | None = None) -> StackPlan:
    cap = max_stack if max_stack is not None else recommended_max_stack(user)
    primary, notes = _pick_goals_foundation_primary(scored, user)
    stack: list[Product] = [primary]

    for role in ROLE_ORDER:
        if role == RoleType.NUTRITION:
            continue
        if len(stack) >= cap:
            break
        if role == primary.role_type:
            continue
        if not role_is_warranted(role, user):
            continue
        picked = _pick_from_role(scored, role, stack, user)
        if picked is not None:
            stack.append(picked)

    stack = _with_worm_magic(stack, scored, user, cap)
    stack = _ensure_core_seaweed(stack, scored, user, cap)
    stack = _apply_calendar_stack_rules(stack, scored, user, cap, notes)
    return _finish_plan(stack, notes)


def ensure_goals_fertiliser(
    plan: StackPlan,
    scored: list[ScoredProduct],
    user: UserInput,
    *,
    max_stack: int,
) -> StackPlan:
    if user.recommendation_mode != "goals":
        return plan
    if any(p.role_type == RoleType.NUTRITION for p in plan.stack):
        return plan

    in_stack = {p.id for p in plan.stack}
    chosen: Product | None = None
    for sp in scored:
        if sp.product.role_type != RoleType.NUTRITION:
            continue
        if sp.product.id in in_stack:
            continue
        if incompatible_with_stack(sp.product, plan.stack, user).ok:
            chosen = sp.product
            break

    notes = list(plan.notes)
    if chosen is None:
        notes.append("Goals mode: no compatible fertiliser could be added (constraints).")
        return StackPlan(primary=plan.primary, stack=plan.stack, notes=notes)

    stack = list(plan.stack)
    if len(stack) >= max_stack:
        vis_idx = next((i for i, p in enumerate(stack) if i > 0 and p.role_type == RoleType.VISUAL), None)
        if vis_idx is not None:
            stack.pop(vis_idx)
        else:
            stack.pop()

    stack.append(chosen)
    notes.append("Goals mode: added a recommended fertiliser so the plan always includes nutrition.")
    return _finish_plan(stack, notes)
