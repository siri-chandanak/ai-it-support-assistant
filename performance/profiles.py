from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PerformanceProfile:
    name: str
    users: int
    spawn_rate: int
    duration: str
    purpose: str


SMOKE = PerformanceProfile(
    name="smoke",
    users=5,
    spawn_rate=1,
    duration="1m",
    purpose=("Validate performance-test configuration and endpoint availability."),
)


BASELINE = PerformanceProfile(
    name="baseline",
    users=25,
    spawn_rate=5,
    duration="5m",
    purpose=("Generate repeatable performance measurements for comparison."),
)


SOAK = PerformanceProfile(
    name="soak",
    users=25,
    spawn_rate=5,
    duration="1h",
    purpose=("Detect memory growth, connection leaks, cache growth, and latency degradation."),
)


PROFILES = {
    SMOKE.name: SMOKE,
    BASELINE.name: BASELINE,
    SOAK.name: SOAK,
}


def get_profile(
    name: str,
) -> PerformanceProfile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        available = ", ".join(sorted(PROFILES))

        raise ValueError(
            f"Unknown performance profile: {name}. Available profiles: {available}"
        ) from exc
