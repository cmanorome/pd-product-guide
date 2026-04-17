from __future__ import annotations

import json
import sys

from pd_engine import recommend


def main() -> int:
    # You can pass a JSON file path, or run with the default payload below.
    if len(sys.argv) > 1:
        payload = json.loads(open(sys.argv[1], "r", encoding="utf-8").read())
    else:
        payload = {
            "recommendation_mode": "problems",
            "season": "autumn",
            "confidence": 0.45,
            "problems": {
                "yellowing": 0.8,
                "slow_growth": 0.6,
                "nutrient_lockout": 0.7,
                "patchy_lawn": 0.5,
                "compaction": 0.4,
            },
            "soils": {"alkaline": 0.7, "clay": 0.4},
        }

    rec = recommend(payload)

    pf = rec.primary_fertiliser
    print(json.dumps(
        {
            "intent": rec.intent,
            "season": rec.season,
            "primary": {"id": rec.primary.id, "name": rec.primary.name, "role_type": rec.primary.role_type.value},
            "primary_fertiliser": (
                None
                if pf is None
                else {"id": pf.id, "name": pf.name, "role_type": pf.role_type.value}
            ),
            "stack": [{"id": p.id, "name": p.name, "role_type": p.role_type.value} for p in rec.stack],
            "upgrade_path": [{"id": p.id, "name": p.name, "role_type": p.role_type.value} for p in rec.upgrade_path],
            "explanations": rec.explanations,
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

