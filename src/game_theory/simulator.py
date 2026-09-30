# src/game_theory/simulator.py
"""Policy scenario simulator.

Orchestrates the full pipeline:
    1. Build payoff matrices from PolicyConfig + MarketCalibration
    2. Solve for Nash equilibria
    3. Compute welfare at the selected equilibrium
    4. Rank the scenario against a baseline
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.game_theory.models import (
    CONSUMER_STRATEGIES,
    LANDLORD_STRATEGIES,
    MarketCalibration,
    PayoffEngine,
    PolicyConfig,
)
from src.game_theory.solvers import (
    Equilibrium,
    SolverMethod,
    solve_game,
)
from src.game_theory.welfare import (
    PolicyScore,
    WelfareResult,
    compute_policy_score,
    compute_welfare,
    normalize_welfare,
)
from src.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class SimulationResult:
    """Complete output of a single policy simulation.

    Attributes:
        policy: The policy configuration that was simulated.
        calibration: The market calibration used.
        equilibria: All Nash equilibria found.
        selected: The equilibrium selected for welfare analysis
            (defaults to the one maximizing utilitarian welfare).
        welfare: Welfare result at the selected equilibrium.
        normalized_welfare: Welfare relative to the baseline.
        policy_score: Composite policy score.
        budget_balance: Government budget balance under this policy.
        rent_to_income_pct: Resulting rent-to-income ratio at equilibrium.
    """

    policy: PolicyConfig
    calibration: MarketCalibration
    equilibria: list[Equilibrium]
    selected: Optional[Equilibrium]
    welfare: Optional[WelfareResult]
    normalized_welfare: Optional[WelfareResult]
    policy_score: Optional[PolicyScore]
    budget_balance: float
    rent_to_income_pct: float

    def to_dict(self) -> dict:
        return {
            "policy": {
                "rent_cap_pct": self.policy.rent_cap_pct,
                "housing_subsidy": self.policy.housing_subsidy,
                "min_wage_delta_pct": self.policy.min_wage_delta_pct,
                "property_tax_delta_pp": self.policy.property_tax_delta_pp,
            },
            "equilibria": [eq.to_dict() for eq in self.equilibria],
            "selected": self.selected.to_dict() if self.selected else None,
            "welfare": self.welfare.to_dict() if self.welfare else None,
            "normalized_welfare": (
                self.normalized_welfare.to_dict() if self.normalized_welfare else None
            ),
            "policy_score": (
                self.policy_score.to_dict() if self.policy_score else None
            ),
            "budget_balance": round(self.budget_balance, 2),
            "rent_to_income_pct": round(self.rent_to_income_pct, 2),
        }


def _compute_budget_balance(
    policy: PolicyConfig,
    calibration: MarketCalibration,
    households: int = 1_000_000,
) -> float:
    """Estimate the government's annual budget balance under a policy.

    Subsidy cost is negative; property tax revenue change is positive or
    negative depending on the delta.
    """
    subsidy_cost = policy.housing_subsidy * 12.0 * households
    property_tax_delta = (
        policy.property_tax_delta_pp / 100.0
        * calibration.average_rent * 20.0  # property value proxy
        * households
    )
    return property_tax_delta - subsidy_cost


def _estimate_rent_to_income(
    policy: PolicyConfig,
    calibration: MarketCalibration,
    equilibrium: Optional[Equilibrium],
) -> float:
    """Estimate the resulting rent-to-income ratio at equilibrium.

    Uses the landlord's mixed strategy to compute expected rent, then
    divides by the consumer's wage-adjusted income.
    """
    base_rent = calibration.average_rent * 12.0
    income = calibration.median_income

    # Expected landlord aggressiveness from mixed strategy
    if equilibrium is not None:
        landlord_mix = equilibrium.row_strategy
        # Aggressive (index 0) → higher rent, Withhold (index 2) → supply effect
        rent_multiplier = (
            landlord_mix[0] * (1.0 + max(policy.rent_cap_pct / 100.0, 0.08))
            + landlord_mix[1] * (1.0 + max(policy.rent_cap_pct / 100.0, 0.04))
            + landlord_mix[2] * (1.0 + 0.15)
        )
    else:
        rent_multiplier = 1.0 + max(policy.rent_cap_pct / 100.0, 0.04)

    # Consumer income adjusts with min wage policy
    wage_multiplier = 1.0 + (policy.min_wage_delta_pct / 100.0 * 0.7)
    adjusted_income = income * wage_multiplier

    expected_rent = base_rent * rent_multiplier
    if adjusted_income <= 0:
        return 0.0
    return (expected_rent / adjusted_income) * 100.0


def simulate_policy(
    policy: PolicyConfig,
    calibration: MarketCalibration,
    method: SolverMethod = SolverMethod.SUPPORT_ENUMERATION,
    baseline: Optional[WelfareResult] = None,
    select_max_utilitarian: bool = True,
) -> SimulationResult:
    """Simulate a single policy configuration.

    Args:
        policy: Policy levers to simulate.
        calibration: Market calibration for the region and year.
        method: Nash solver method.
        baseline: Optional baseline welfare for normalization.
        select_max_utilitarian: If True, pick the equilibrium with the
            highest utilitarian welfare. If False, pick the first equilibrium.

    Returns:
        SimulationResult with equilibria, welfare, and budget balance.
    """
    engine = PayoffEngine(calibration=calibration, policy=policy)
    A, B = engine.build_game_matrices()

    equilibria = solve_game(A, B, method=method)
    if not equilibria:
        log.warning("no_equilibria_found", policy=policy.__dict__)
        return SimulationResult(
            policy=policy,
            calibration=calibration,
            equilibria=[],
            selected=None,
            welfare=None,
            normalized_welfare=None,
            policy_score=None,
            budget_balance=_compute_budget_balance(policy, calibration),
            rent_to_income_pct=_estimate_rent_to_income(policy, calibration, None),
        )

    # Select equilibrium
    if select_max_utilitarian:
        selected = max(
            equilibria,
            key=lambda eq: eq.row_payoff + eq.col_payoff,
        )
    else:
        selected = equilibria[0]

    # Welfare at equilibrium: utilities for landlord and consumer
    utilities = np.array([selected.row_payoff, selected.col_payoff])
    welfare = compute_welfare(utilities)

    normalized = normalize_welfare(welfare, baseline) if baseline else None

    budget = _compute_budget_balance(policy, calibration)
    policy_extremity = _policy_extremity(policy)
    score = compute_policy_score(
        welfare=welfare,
        budget_balance=budget,
        policy_extremity=policy_extremity,
    )

    result = SimulationResult(
        policy=policy,
        calibration=calibration,
        equilibria=equilibria,
        selected=selected,
        welfare=welfare,
        normalized_welfare=normalized,
        policy_score=score,
        budget_balance=budget,
        rent_to_income_pct=_estimate_rent_to_income(policy, calibration, selected),
    )
    log.info(
        "simulation_complete",
        equilibria=len(equilibria),
        selected_payoffs=(round(selected.row_payoff, 2), round(selected.col_payoff, 2)),
        rent_to_income=round(result.rent_to_income_pct, 2),
    )
    return result


def _policy_extremity(policy: PolicyConfig) -> float:
    """Return a 0-1 score of how far the policy is from the status quo.

    Status quo defaults:
        rent_cap = 3.0, subsidy = 500, min_wage_delta = 10, prop_tax_delta = 0
    """
    status_quo = {
        "rent_cap": 3.0,
        "subsidy": 500.0,
        "min_wage": 10.0,
        "prop_tax": 0.0,
    }
    ranges = {
        "rent_cap": 10.0,
        "subsidy": 2000.0,
        "min_wage": 30.0,
        "prop_tax": 5.0,
    }
    deviations = [
        abs(policy.rent_cap_pct - status_quo["rent_cap"]) / ranges["rent_cap"],
        abs(policy.housing_subsidy - status_quo["subsidy"]) / ranges["subsidy"],
        abs(policy.min_wage_delta_pct - status_quo["min_wage"]) / ranges["min_wage"],
        abs(policy.property_tax_delta_pp - status_quo["prop_tax"]) / ranges["prop_tax"],
    ]
    return float(min(np.mean(deviations), 1.0))


def compute_baseline_welfare(
    calibration: MarketCalibration,
    method: SolverMethod = SolverMethod.SUPPORT_ENUMERATION,
) -> WelfareResult:
    """Compute the status-quo welfare to use as a normalization baseline."""
    status_quo = PolicyConfig(
        rent_cap_pct=3.0,
        housing_subsidy=500.0,
        min_wage_delta_pct=10.0,
        property_tax_delta_pp=0.0,
    )
    result = simulate_policy(status_quo, calibration, method=method)
    if result.welfare is None:
        # Fallback: zero welfare
        return compute_welfare(np.zeros(2))
    return result.welfare


def compare_scenarios(
    scenarios: list[tuple[str, PolicyConfig]],
    calibration: MarketCalibration,
    method: SolverMethod = SolverMethod.SUPPORT_ENUMERATION,
) -> list[dict]:
    """Run multiple scenarios and return a ranked comparison.

    Args:
        scenarios: List of (name, PolicyConfig) tuples.
        calibration: Market calibration.
        method: Solver method.

    Returns:
        List of dicts with name, score, welfare, and rent-to-income,
        sorted by composite score descending.
    """
    baseline = compute_baseline_welfare(calibration, method=method)
    results = []

    for name, policy in scenarios:
        sim = simulate_policy(
            policy,
            calibration,
            method=method,
            baseline=baseline,
        )
        if sim.policy_score is None:
            continue
        results.append(
            {
                "name": name,
                "composite": sim.policy_score.composite,
                "utilitarian": sim.welfare.utilitarian if sim.welfare else 0,
                "egalitarian": sim.welfare.egalitarian if sim.welfare else 0,
                "nash": sim.welfare.nash if sim.welfare else 0,
                "budget_balance": sim.budget_balance,
                "rent_to_income_pct": sim.rent_to_income_pct,
                "policy": sim.policy,
                "result": sim,
            }
        )

    results.sort(key=lambda r: r["composite"], reverse=True)
    return results
