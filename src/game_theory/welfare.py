# src/game_theory/welfare.py
"""Social welfare functions for evaluating policy outcomes.

Implements the three classical welfare orderings:
    - Utilitarian: maximize sum of utilities (efficiency)
    - Egalitarian (Rawlsian): maximize the minimum utility (fairness)
    - Nash: maximize the product of utilities (proportional fairness)

Also provides a composite ``PolicyScore`` that combines welfare, budget
balance, and political feasibility into a single ranking metric.
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np


class WelfareFunction(str, Enum):
    UTILITARIAN = "utilitarian"
    EGALITARIAN = "egalitarian"
    NASH = "nash"


@dataclass
class WelfareResult:
    """Container for welfare computation results."""

    utilitarian: float
    egalitarian: float
    nash: float
    utilities: np.ndarray

    def to_dict(self) -> dict:
        return {
            "utilitarian": round(self.utilitarian, 4),
            "egalitarian": round(self.egalitarian, 4),
            "nash": round(self.nash, 4),
            "utilities": [round(float(u), 4) for u in self.utilities],
        }


# ---------------------------------------------------------------------------
# Individual welfare functions
# ---------------------------------------------------------------------------

def utilitarian_welfare(utilities: np.ndarray) -> float:
    """Sum of utilities. The classic efficiency criterion.

    W(u) = sum_i u_i
    """
    return float(np.sum(utilities))


def egalitarian_welfare(utilities: np.ndarray) -> float:
    """Minimum utility (Rawlsian maximin).

    W(u) = min_i u_i

    A negative minimum is allowed; this reflects that the worst-off
    agent may be worse off than the status quo.
    """
    return float(np.min(utilities))


def nash_welfare(utilities: np.ndarray, epsilon: float = 1e-6) -> float:
    """Product of utilities (Nash social welfare).

    W(u) = prod_i u_i

    Since utilities can be negative, we shift by the minimum negative
    value to keep the product defined. If all utilities are non-negative,
    the product is computed directly.
    """
    u = np.asarray(utilities, dtype=float)
    if np.any(u < 0):
        # Shift so all values are positive, preserving ordinality
        shift = abs(np.min(u)) + 1.0
        u = u + shift
    u = np.maximum(u, epsilon)
    return float(np.prod(u))


def compute_welfare(utilities: np.ndarray) -> WelfareResult:
    """Compute all three welfare functions for a utility vector."""
    utilities = np.asarray(utilities, dtype=float)
    return WelfareResult(
        utilitarian=utilitarian_welfare(utilities),
        egalitarian=egalitarian_welfare(utilities),
        nash=nash_welfare(utilities),
        utilities=utilities,
    )


def normalize_welfare(result: WelfareResult, baseline: WelfareResult) -> WelfareResult:
    """Express welfare relative to a baseline (e.g., status quo).

    A value of 1.0 means "same as baseline"; > 1.0 means improvement.
    """
    def _ratio(new: float, base: float) -> float:
        if abs(base) < 1e-9:
            return 1.0
        return new / base

    return WelfareResult(
        utilitarian=_ratio(result.utilitarian, baseline.utilitarian),
        egalitarian=_ratio(result.egalitarian, baseline.egalitarian),
        nash=_ratio(result.nash, baseline.nash),
        utilities=result.utilities,
    )


# ---------------------------------------------------------------------------
# Composite policy score
# ---------------------------------------------------------------------------

@dataclass
class PolicyScore:
    """Composite score for ranking policy scenarios.

    Attributes:
        welfare: WelfareResult from the equilibrium.
        budget_balance: Government budget balance (positive = surplus).
        political_feasibility: 0-1 score based on how far policy is from
            the status quo (extreme policies are less feasible).
        composite: Weighted combination of the above.
    """

    welfare: WelfareResult
    budget_balance: float
    political_feasibility: float
    composite: float

    def to_dict(self) -> dict:
        return {
            "welfare": self.welfare.to_dict(),
            "budget_balance": round(self.budget_balance, 2),
            "political_feasibility": round(self.political_feasibility, 3),
            "composite": round(self.composite, 4),
        }


def compute_policy_score(
    welfare: WelfareResult,
    budget_balance: float,
    policy_extremity: float,
    weights: dict[str, float] | None = None,
) -> PolicyScore:
    """Combine welfare, budget, and feasibility into a single score.

    Args:
        welfare: Computed welfare result.
        budget_balance: Government surplus/deficit in currency units.
        policy_extremity: 0 = status quo, 1 = maximally extreme.
        weights: Optional override for component weights.

    Returns:
        PolicyScore with a composite value for ranking.
    """
    if weights is None:
        weights = {
            "utilitarian": 0.35,
            "egalitarian": 0.25,
            "nash": 0.15,
            "budget": 0.15,
            "feasibility": 0.10,
        }

    # Normalize components to comparable scales
    welfare_component = (
        weights["utilitarian"] * welfare.utilitarian
        + weights["egalitarian"] * welfare.egalitarian
        + weights["nash"] * welfare.nash
    )

    # Budget: positive balance is good; scale by 1e6 to normalize
    budget_component = weights["budget"] * (budget_balance / 1e6)

    # Feasibility: lower extremity is better (status quo is maximally feasible)
    feasibility_component = weights["feasibility"] * (1.0 - policy_extremity)

    composite = welfare_component + budget_component + feasibility_component

    return PolicyScore(
        welfare=welfare,
        budget_balance=budget_balance,
        political_feasibility=1.0 - policy_extremity,
        composite=composite,
    )
