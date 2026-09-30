# tests/test_game_theory.py
"""Tests for the Layer 4 game theory engine."""

import numpy as np
import pytest

from src.game_theory.models import (
    CONSUMER_STRATEGIES,
    LANDLORD_STRATEGIES,
    MarketCalibration,
    PayoffEngine,
    PolicyConfig,
)
from src.game_theory.solvers import (
    SolverMethod,
    solve_game,
    solve_support_enumeration,
)
from src.game_theory.welfare import (
    compute_welfare,
    egalitarian_welfare,
    nash_welfare,
    utilitarian_welfare,
)
from src.game_theory.simulator import simulate_policy, compare_scenarios
from src.game_theory.scenarios import SCENARIOS


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def test_payoff_matrices_have_correct_shape():
    engine = PayoffEngine(
        calibration=MarketCalibration(),
        policy=PolicyConfig(),
    )
    A, B = engine.build_game_matrices()
    assert A.shape == (3, 3)
    assert B.shape == (3, 3)


def test_payoffs_are_finite():
    engine = PayoffEngine(
        calibration=MarketCalibration(),
        policy=PolicyConfig(),
    )
    A, B = engine.build_game_matrices()
    assert np.all(np.isfinite(A))
    assert np.all(np.isfinite(B))


def test_rent_control_reduces_landlord_payoff():
    """Tighter rent control should not increase landlord payoffs."""
    calibration = MarketCalibration()
    tight = PayoffEngine(
        calibration=calibration,
        policy=PolicyConfig(rent_cap_pct=1.0),
    ).landlord_payoffs()
    loose = PayoffEngine(
        calibration=calibration,
        policy=PolicyConfig(rent_cap_pct=8.0),
    ).landlord_payoffs()
    assert tight.mean() <= loose.mean() + 1e-6


def test_subsidy_increases_consumer_payoff():
    """Higher subsidy should increase consumer payoffs."""
    calibration = MarketCalibration()
    low = PayoffEngine(
        calibration=calibration,
        policy=PolicyConfig(housing_subsidy=0.0),
    ).consumer_payoffs()
    high = PayoffEngine(
        calibration=calibration,
        policy=PolicyConfig(housing_subsidy=2000.0),
    ).consumer_payoffs()
    assert high.mean() >= low.mean() - 1e-6


# ---------------------------------------------------------------------------
# Solvers
# ---------------------------------------------------------------------------

def test_support_enumeration_finds_equilibrium():
    A = np.array([[3, 0], [5, 1]], dtype=float)
    B = np.array([[3, 5], [0, 1]], dtype=float)
    equilibria = solve_support_enumeration(A, B)
    assert len(equilibria) >= 1
    # Prisoner's dilemma has (Defect, Defect) as the unique equilibrium
    eq = equilibria[0]
    assert eq.is_pure


def test_solve_game_dispatch():
    A = np.array([[1, -1], [-1, 1]], dtype=float)
    B = -A
    eqs = solve_game(A, B, method=SolverMethod.LEMKE_HOWSON)
    assert len(eqs) >= 1
    for eq in eqs:
        assert np.isclose(eq.row_strategy.sum(), 1.0, atol=1e-6)
        assert np.isclose(eq.col_strategy.sum(), 1.0, atol=1e-6)


def test_solver_handles_shape_mismatch():
    A = np.array([[1, 2], [3, 4]], dtype=float)
    B = np.array([[1, 2, 3], [4, 5, 6]], dtype=float)
    with pytest.raises(ValueError):
        solve_game(A, B)


# ---------------------------------------------------------------------------
# Welfare
# ---------------------------------------------------------------------------

def test_utilitarian_is_sum():
    u = np.array([1.0, 2.0, 3.0])
    assert utilitarian_welfare(u) == pytest.approx(6.0)


def test_egalitarian_is_min():
    u = np.array([1.0, 2.0, 3.0])
    assert egalitarian_welfare(u) == pytest.approx(1.0)


def test_nash_is_product():
    u = np.array([1.0, 2.0, 3.0])
    assert nash_welfare(u) == pytest.approx(6.0)


def test_welfare_handles_negative_utilities():
    u = np.array([-1.0, 2.0, 3.0])
    result = compute_welfare(u)
    assert np.isfinite(result.nash)
    assert result.utilitarian == pytest.approx(4.0)
    assert result.egalitarian == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------

def test_simulate_policy_returns_result():
    result = simulate_policy(
        PolicyConfig(),
        MarketCalibration(),
        method=SolverMethod.LEMKE_HOWSON,
    )
    assert result.selected is not None
    assert result.welfare is not None
    assert result.policy_score is not None
    assert result.rent_to_income_pct >= 0


def test_compare_scenarios_returns_ranked():
    calibration = MarketCalibration()
    ranked = compare_scenarios(SCENARIOS[:3], calibration)
    assert len(ranked) == 3
    # Verify descending order by composite
    composites = [r["composite"] for r in ranked]
    assert composites == sorted(composites, reverse=True)
