# src/game_theory/scenarios.py
"""Pre-built policy scenarios for the dashboard and CLI.

Each scenario is a (name, PolicyConfig) tuple that can be passed directly
to ``compare_scenarios``.
"""

from src.game_theory.models import PolicyConfig

SCENARIOS: list[tuple[str, PolicyConfig]] = [
    (
        "Status Quo",
        PolicyConfig(
            rent_cap_pct=3.0,
            housing_subsidy=500.0,
            min_wage_delta_pct=10.0,
            property_tax_delta_pp=0.0,
        ),
    ),
    (
        "Tight Rent Control (2%)",
        PolicyConfig(
            rent_cap_pct=2.0,
            housing_subsidy=500.0,
            min_wage_delta_pct=10.0,
            property_tax_delta_pp=0.0,
        ),
    ),
    (
        "Loose Rent Control (7%)",
        PolicyConfig(
            rent_cap_pct=7.0,
            housing_subsidy=500.0,
            min_wage_delta_pct=10.0,
            property_tax_delta_pp=0.0,
        ),
    ),
    (
        "High Subsidy ($1,200)",
        PolicyConfig(
            rent_cap_pct=3.0,
            housing_subsidy=1200.0,
            min_wage_delta_pct=10.0,
            property_tax_delta_pp=0.0,
        ),
    ),
    (
        "Aggressive Wage Boost (+25%)",
        PolicyConfig(
            rent_cap_pct=3.0,
            housing_subsidy=500.0,
            min_wage_delta_pct=25.0,
            property_tax_delta_pp=0.0,
        ),
    ),
    (
        "Property Tax Cut (−2pp) + No Subsidy",
        PolicyConfig(
            rent_cap_pct=3.0,
            housing_subsidy=0.0,
            min_wage_delta_pct=10.0,
            property_tax_delta_pp=-2.0,
        ),
    ),
    (
        "Balanced Intervention",
        PolicyConfig(
            rent_cap_pct=4.0,
            housing_subsidy=800.0,
            min_wage_delta_pct=15.0,
            property_tax_delta_pp=1.0,
        ),
    ),
]


def get_scenario_names() -> list[str]:
    """Return the display names of all pre-built scenarios."""
    return [name for name, _ in SCENARIOS]


def get_scenario(name: str) -> PolicyConfig | None:
    """Return the PolicyConfig for a named scenario, or None if not found."""
    for n, config in SCENARIOS:
        if n == name:
            return config
    return None
