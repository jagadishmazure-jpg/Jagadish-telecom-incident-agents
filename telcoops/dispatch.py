"""Field-tech dispatch recommender (domain differentiator).

Ranks on-shift technicians for an incident. Required skill is a hard filter;
the score blends proximity (site distance map) and current load so the NOC
gets a ranked, explainable shortlist instead of paging the whole region.

score = 0.6 * proximity_score + 0.4 * (1 - current_load)
proximity_score = 1 / (1 + distance_km / 50)
"""

from __future__ import annotations

from dataclasses import dataclass

# Symmetric inter-site road distances (km). Missing pairs default to 120 km.
SITE_DISTANCE_KM: dict[tuple[str, str], float] = {
    ("SITE-NORTH", "SITE-EAST"): 60.0,
    ("SITE-NORTH", "SITE-WEST"): 90.0,
    ("SITE-NORTH", "SITE-SOUTH"): 140.0,
    ("SITE-EAST", "SITE-WEST"): 110.0,
    ("SITE-EAST", "SITE-SOUTH"): 100.0,
    ("SITE-WEST", "SITE-SOUTH"): 150.0,
}

DEFAULT_DISTANCE_KM = 120.0


def site_distance(a: str, b: str) -> float:
    if a == b:
        return 0.0
    return SITE_DISTANCE_KM.get((a, b),
           SITE_DISTANCE_KM.get((b, a), DEFAULT_DISTANCE_KM))


@dataclass
class DispatchRecommendation:
    tech_id: str
    name: str
    score: float
    distance_km: float
    load: float
    explanation: str


def recommend_techs(incident_site: str, required_skill: str,
                    techs: list[dict], top_n: int = 3
                    ) -> list[DispatchRecommendation]:
    """Rank eligible techs. Deterministic; ties broken by tech_id."""
    required = required_skill.strip().lower()
    eligible = [
        t for t in techs
        if t.get("on_shift") and required in
        {s.strip().lower() for s in t.get("skills", "").split(",")}
    ]
    ranked: list[DispatchRecommendation] = []
    for t in eligible:
        dist = site_distance(t["home_site"], incident_site)
        proximity = 1.0 / (1.0 + dist / 50.0)
        load = float(t.get("current_load", 0.0))
        score = 0.6 * proximity + 0.4 * (1.0 - load)
        ranked.append(DispatchRecommendation(
            tech_id=t["tech_id"], name=t["name"], score=round(score, 4),
            distance_km=dist, load=load,
            explanation=(f"has skill '{required_skill}'; {dist:.0f} km from "
                         f"{incident_site} (proximity {proximity:.2f}); "
                         f"current load {load:.0%}"),
        ))
    ranked.sort(key=lambda r: (-r.score, r.tech_id))
    return ranked[:top_n]
