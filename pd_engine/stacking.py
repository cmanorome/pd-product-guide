from __future__ import annotations

from dataclasses import dataclass

from .constraints import incompatible_with_stack, is_valid_primary
from .types import Product, RoleType, ScoredProduct, UserInput


ROLE_ORDER: list[RoleType] = [
    RoleType.SOIL_STRUCTURE,
    RoleType.SOIL_CHEMISTRY,
    RoleType.BIOLOGY,
    RoleType.UPTAKE,
    RoleType.NUTRITION,
    RoleType.VISUAL,
]


@dataclass(frozen=True)
class StackPlan:
    primary: Product
    stack: list[Product]  # includes primary at index 0
    notes: list[str]


def build_stack(scored: list[ScoredProduct], user: UserInput, *, max_stack: int = 4) -> StackPlan:
    """
    Deterministic “product stacking”:
    - choose the best valid primary
    - add 0..(max_stack-1) supporting products, respecting role order and hard constraints

    Problems mode: do not add a separate fertiliser (nutrition) layer unless the primary
    product is already nutrition — fixing issues may not require an NPK step.
    """
    notes: list[str] = []

    # Pick primary: highest scored that passes primary constraints
    primary: Product | None = None
    for sp in scored:
        res = is_valid_primary(sp.product, user)
        if res.ok:
            primary = sp.product
            break
    if primary is None:
        # fallback: best non-visual
        for sp in scored:
            if sp.product.role_type != RoleType.VISUAL:
                primary = sp.product
                notes.append("Fallback primary selection applied.")
                break
    if primary is None:
        raise RuntimeError("No valid primary product found.")

    stack: list[Product] = [primary]

    # Add support in role-layer order, preferring high score within each role.
    for role in ROLE_ORDER:
        if len(stack) >= max_stack:
            break
        if role == primary.role_type:
            continue
        if (
            user.recommendation_mode == "problems"
            and role == RoleType.NUTRITION
            and primary.role_type != RoleType.NUTRITION
        ):
            continue

        candidates = [sp.product for sp in scored if sp.product.role_type == role]
        for c in candidates:
            if len(stack) >= max_stack:
                break
            res = incompatible_with_stack(c, stack, user)
            if not res.ok:
                continue
            # Avoid redundant same-function add-ons (simple v1 heuristic)
            if c.is_iron_based and any(p.is_iron_based for p in stack):
                continue
            stack.append(c)
            break

    # Re-order stack by role order (primary stays first, rest ordered)
    primary = stack[0]
    rest = stack[1:]
    role_rank = {r: i for i, r in enumerate(ROLE_ORDER)}
    rest_sorted = sorted(rest, key=lambda p: role_rank.get(p.role_type, 999))
    stack = [primary] + rest_sorted

    return StackPlan(primary=primary, stack=stack, notes=notes)


def _pick_goals_foundation_primary(scored: list[ScoredProduct], user: UserInput) -> tuple[Product, list[str]]:
    """
    Prefer a non-nutrition foundation so goals mode can show fertiliser as its own line.
    Falls back to nutrition when no other valid primary exists.
    """
    notes: list[str] = []
    for sp in scored:
        if not is_valid_primary(sp.product, user).ok:
            continue
        if sp.product.role_type != RoleType.NUTRITION:
            return sp.product, notes
    for sp in scored:
        if is_valid_primary(sp.product, user).ok:
            return sp.product, notes
    for sp in scored:
        if sp.product.role_type != RoleType.VISUAL:
            notes.append("Fallback primary selection applied.")
            return sp.product, notes
    raise RuntimeError("No valid primary product found.")


def build_stack_goals(scored: list[ScoredProduct], user: UserInput, *, max_stack: int = 4) -> StackPlan:
    """
    Goals mode: one foundation primary (prefer soil/chemistry/biology/uptake over nutrition),
    then supporting layers only — nutrition is surfaced separately as primary_fertiliser
    (or the CHAMPION pair in explanations), not mixed into this stack.
    """
    primary, notes = _pick_goals_foundation_primary(scored, user)
    stack: list[Product] = [primary]

    for role in ROLE_ORDER:
        if role == RoleType.NUTRITION:
            continue
        if len(stack) >= max_stack:
            break
        if role == primary.role_type:
            continue
        candidates = [sp.product for sp in scored if sp.product.role_type == role]
        for c in candidates:
            if len(stack) >= max_stack:
                break
            res = incompatible_with_stack(c, stack, user)
            if not res.ok:
                continue
            if c.is_iron_based and any(p.is_iron_based for p in stack):
                continue
            stack.append(c)
            break

    primary = stack[0]
    rest = stack[1:]
    role_rank = {r: i for i, r in enumerate(ROLE_ORDER)}
    rest_sorted = sorted(rest, key=lambda p: role_rank.get(p.role_type, 999))
    return StackPlan(primary=primary, stack=[primary] + rest_sorted, notes=notes)


def ensure_goals_fertiliser(
    plan: StackPlan,
    scored: list[ScoredProduct],
    user: UserInput,
    *,
    max_stack: int,
) -> StackPlan:
    """
    In goals mode, every plan should include at least one fertiliser (nutrition role),
    since outcome-based picks expect visible NPK / fertiliser options. The base stack
    can fill max_stack with soil / biology / uptake before nutrition is reached.
    """
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
    primary = stack[0]
    rest = stack[1:]
    role_rank = {r: i for i, r in enumerate(ROLE_ORDER)}
    rest_sorted = sorted(rest, key=lambda p: role_rank.get(p.role_type, 999))
    final_stack = [primary] + rest_sorted
    notes.append("Goals mode: added a recommended fertiliser so the plan always includes nutrition.")
    return StackPlan(primary=primary, stack=final_stack, notes=notes)

