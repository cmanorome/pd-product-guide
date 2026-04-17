from __future__ import annotations

from dataclasses import dataclass

from .types import Product, RoleType, UserInput


@dataclass(frozen=True)
class ConstraintResult:
    ok: bool
    reason: str | None = None


def incompatible_with_stack(candidate: Product, stack: list[Product], user: UserInput) -> ConstraintResult:
    # Rule: no multiple iron-based products in same stack
    if candidate.is_iron_based and any(p.is_iron_based for p in stack):
        return ConstraintResult(ok=False, reason="Avoid stacking multiple iron-based products.")

    # Rule: lime and iron sulphate cannot be recommended together (same stack)
    if candidate.is_lime_based and any(p.is_iron_sulphate for p in stack):
        return ConstraintResult(ok=False, reason="Do not combine lime/dolomite with iron sulphate.")
    if candidate.is_iron_sulphate and any(p.is_lime_based for p in stack):
        return ConstraintResult(ok=False, reason="Do not combine iron sulphate with lime/dolomite.")

    # Rule: fertilisers are not primary when nutrient lockout is present without uptake/biology first
    lockout = float(user.problems.get("nutrient_lockout", 0.0))
    if lockout >= 0.5:
        if candidate.role_type == RoleType.NUTRITION:
            has_unlock_layer = any(
                p.role_type in (RoleType.UPTAKE, RoleType.BIOLOGY, RoleType.SOIL_CHEMISTRY) for p in stack
            )
            if not has_unlock_layer:
                return ConstraintResult(
                    ok=False,
                    reason="Nutrient lockout present: address biology/uptake/chemistry before fertiliser.",
                )

    # Rule: visual response products must not be foundational
    if candidate.role_type == RoleType.VISUAL:
        has_foundation = any(p.role_type in (RoleType.SOIL_STRUCTURE, RoleType.SOIL_CHEMISTRY, RoleType.BIOLOGY, RoleType.UPTAKE) for p in stack)
        if not has_foundation:
            return ConstraintResult(
                ok=False,
                reason="Visual products must come after soil/biology/uptake foundations.",
            )

    return ConstraintResult(ok=True)


def is_valid_primary(primary: Product, user: UserInput) -> ConstraintResult:
    lockout = float(user.problems.get("nutrient_lockout", 0.0))
    if primary.role_type == RoleType.VISUAL:
        return ConstraintResult(ok=False, reason="Visual products cannot be primary/foundation recommendations.")
    if lockout >= 0.5 and primary.role_type == RoleType.NUTRITION:
        return ConstraintResult(
            ok=False,
            reason="Nutrient lockout present: do not lead with fertiliser without unlock layers.",
        )
    return ConstraintResult(ok=True)

