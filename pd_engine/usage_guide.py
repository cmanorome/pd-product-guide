"""Plant Doctor application notes — rates, timing, and mix rules.

Loaded from NEW DATA/product_usage_guide.csv (label PDF extract).
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

USAGE_KEYS = (
    "mix_together",
    "independent",
    "water_in",
    "soil_drench",
    "foliar",
    "fertigation",
    "hydroponic",
    "hose_on",
    "mix_with_iron",
)

_GUIDE_PATH = Path(__file__).resolve().parents[1] / "NEW DATA" / "product_usage_guide.csv"
_RATES_PATH = Path(__file__).resolve().parents[1] / "NEW DATA" / "product_usage_guide_rates.csv"


def _truthy(v: str | None) -> bool:
    return str(v or "").strip() in {"1", "true", "yes", "on"}


def _first_sentence(text: str, *, max_len: int = 160) -> str:
    t = " ".join((text or "").split())
    if not t:
        return ""
    cut = t.split(". ")[0].strip()
    if cut and not cut.endswith((".", "!", "?")):
        cut += "."
    if len(cut) > max_len:
        cut = cut[: max_len - 1].rsplit(" ", 1)[0] + "…"
    return cut


def _mix_note(row: dict[str, str]) -> str | None:
    sku = (row.get("sku") or "").strip()
    bits: list[str] = []
    if sku == "NSWL":
        bits.append("Mix gently — do not shake.")
    if sku == "STM":
        bits.append("This is the liquid that can be mixed with iron.")
    elif sku in ("LIR", "MG"):
        bits.append("Can be mixed with Stimulizer, not with seaweed or humic.")
    elif _truthy(row.get("mix_with_iron")):
        bits.append("Can be mixed with iron.")
    if (row.get("tank_group") or "").strip() == "no_iron_mix":
        bits.append("Do not mix with iron in the same sprayer.")
    if sku in ("LIMEGr", "DOL"):
        bits.append("Wait 6 weeks before applying iron.")
    if sku in ("575", "721"):
        bits.append("Go gently on phosphorus-sensitive natives.")
    if sku in ("547", "846", "LIR", "MG", "LEN"):
        bits.append("May stain paths and clothes.")
    if sku in ("886", "892"):
        bits.append("Do not spread in heat over 30°C. Half rate in autumn and winter.")
    if _truthy(row.get("jar_test")) and sku not in ("NSWL",):
        bits.append("Jar test before mixing with other products.")
    if not bits:
        return None
    # Keep two tips max so the card stays readable.
    return " ".join(bits[:2])


@lru_cache(maxsize=1)
def _load_rate_fallback() -> dict[str, str]:
    if not _RATES_PATH.exists():
        return {}
    prefer = (
        "lawn_garden",
        "home_garden",
        "general",
        "lawn_drench",
        "home_garden_area",
        "soil_amendment",
    )
    by_sku: dict[str, list[tuple[str, str]]] = {}
    with _RATES_PATH.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sku = (row.get("sku") or "").strip()
            amount = " ".join((row.get("amount_text") or "").split())
            if sku and amount:
                by_sku.setdefault(sku, []).append(((row.get("use_case") or "").strip(), amount))
    out: dict[str, str] = {}
    for sku, rows in by_sku.items():
        ranked = sorted(rows, key=lambda r: prefer.index(r[0]) if r[0] in prefer else 99)
        out[sku] = ranked[0][1]
    return out


@lru_cache(maxsize=1)
def load_usage_guide(path: str | Path | None = None) -> dict[str, dict[str, str]]:
    p = Path(path) if path else _GUIDE_PATH
    if not p.exists():
        return {}
    fallback = _load_rate_fallback()
    out: dict[str, dict[str, str]] = {}
    with p.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            sku = (row.get("sku") or "").strip()
            if not sku:
                continue
            rate = _first_sentence(row.get("rate_text") or "", max_len=120)
            if not rate or rate.lower().startswith("varies"):
                alt = fallback.get(sku)
                rate = (alt + ".") if alt and not alt.endswith(".") else (alt or rate)
            out[sku] = {
                "apply_rate": rate or "",
                "apply_frequency": _first_sentence(row.get("frequency_text") or "", max_len=140) or "",
                "mix_note": _mix_note(row) or "",
                "min_dilution": (row.get("min_dilution") or "").strip(),
                "usage_flags": {key: _truthy(row.get(key)) for key in USAGE_KEYS},
            }
            if out[sku]["min_dilution"] and out[sku]["apply_rate"]:
                if out[sku]["min_dilution"] not in out[sku]["apply_rate"]:
                    out[sku]["apply_rate"] = f"{out[sku]['apply_rate']} Min dilution {out[sku]['min_dilution']}."
    return out


def tips_for(sku: str) -> dict[str, object]:
    row = load_usage_guide().get(sku) or {}
    flags = row.get("usage_flags") or {}
    return {
        "apply_rate": row.get("apply_rate") or None,
        "apply_frequency": row.get("apply_frequency") or None,
        "mix_note": row.get("mix_note") or None,
        "usage_flags": {k: bool(flags.get(k)) for k in USAGE_KEYS if flags.get(k)},
    }
