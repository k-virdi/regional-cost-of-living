# src/game_theory/solvers.py
"""Nash equilibrium solvers for the policy response game.

Wraps:
    - Nashpy: support enumeration, Lemke-Howson, vertex enumeration
    - PyGambit: logit quantal response equilibrium (LQRE), enumpoly

The public API is ``solve_game(A, B, method)`` which returns a list of
``Equilibrium`` dataclasses with strategy profiles and payoffs.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import nashpy as nash
import numpy as np

from src.utils.logger import get_logger

log = get_logger(__name__)


class SolverMethod(str, Enum):
    """Available equilibrium computation methods."""
    SUPPORT_ENUMERATION = "support_enumeration"
    LEMKE_HOWSON = "lemke_howson"
    VERTEX_ENUMERATION = "vertex_enumeration"
    LOGIT_QRE = "logit_qre"


@dataclass
class Equilibrium:
    """A single Nash equilibrium of the game.

    Attributes:
        row_strategy: Mixed strategy for the row player (landlord), sums to 1.
        col_strategy: Mixed strategy for the column player (consumer), sums to 1.
        row_payoff: Expected payoff for the row player at this equilibrium.
        col_payoff: Expected payoff for the column player at this equilibrium.
        method: The solver method that found this equilibrium.
        is_pure: True if both strategies are pure (probability 1 on one action).
    """

    row_strategy: np.ndarray
    col_strategy: np.ndarray
    row_payoff: float
    col_payoff: float
    method: str
    is_pure: bool

    def to_dict(self) -> dict:
        return {
            "row_strategy": self.row_strategy.tolist(),
            "col_strategy": self.col_strategy.tolist(),
            "row_payoff": round(self.row_payoff, 4),
            "col_payoff": round(self.col_payoff, 4),
            "method": self.method,
            "is_pure": self.is_pure,
        }


def _is_pure(strategy: np.ndarray, tol: float = 1e-6) -> bool:
    """Return True if the strategy is pure (one action with probability ~1)."""
    return bool(np.any(strategy >= 1.0 - tol))


def _equilibrium_from_arrays(
    row_strategy: np.ndarray,
    col_strategy: np.ndarray,
    A: np.ndarray,
    B: np.ndarray,
    method: str,
) -> Equilibrium:
    """Build an Equilibrium dataclass from strategy arrays."""
    row_strategy = np.asarray(row_strategy, dtype=float)
    col_strategy = np.asarray(col_strategy, dtype=float)

    row_payoff = float(row_strategy @ A @ col_strategy)
    col_payoff = float(row_strategy @ B @ col_strategy)

    return Equilibrium(
        row_strategy=row_strategy,
        col_strategy=col_strategy,
        row_payoff=row_payoff,
        col_payoff=col_payoff,
        method=method,
        is_pure=_is_pure(row_strategy) and _is_pure(col_strategy),
    )


def solve_support_enumeration(A: np.ndarray, B: np.ndarray) -> list[Equilibrium]:
    """Find all Nash equilibria via support enumeration.

    Works for nondegenerate 2-player games. Returns every equilibrium.
    """
    game = nash.Game(A, B)
    equilibria = []
    for row_s, col_s in game.support_enumeration():
        equilibria.append(
            _equilibrium_from_arrays(row_s, col_s, A, B, "support_enumeration")
        )
    log.info("support_enumeration_done", count=len(equilibria))
    return equilibria


def solve_lemke_howson(A: np.ndarray, B: np.ndarray) -> list[Equilibrium]:
    """Find Nash equilibria via the Lemke-Howson algorithm.

    Enumerates all possible starting labels. Not guaranteed to find every
    equilibrium, but efficient for large games.
    """
    game = nash.Game(A, B)
    equilibria = []
    seen = set()
    for row_s, col_s in game.lemke_howson_enumeration():
        key = (
            tuple(np.round(row_s, 6)),
            tuple(np.round(col_s, 6)),
        )
        if key in seen:
            continue
        seen.add(key)
        equilibria.append(
            _equilibrium_from_arrays(row_s, col_s, A, B, "lemke_howson")
        )
    log.info("lemke_howson_done", count=len(equilibria))
    return equilibria


def solve_vertex_enumeration(A: np.ndarray, B: np.ndarray) -> list[Equilibrium]:
    """Find Nash equilibria via best-response polytope vertex enumeration."""
    game = nash.Game(A, B)
    equilibria = []
    for row_s, col_s in game.vertex_enumeration():
        equilibria.append(
            _equilibrium_from_arrays(row_s, col_s, A, B, "vertex_enumeration")
        )
    log.info("vertex_enumeration_done", count=len(equilibria))
    return equilibria


def solve_logit_qre(
    A: np.ndarray,
    B: np.ndarray,
    lam: float = 10.0,
) -> list[Equilibrium]:
    """Find a logit quantal response equilibrium via PyGambit.

    The logit QRE generalizes Nash equilibrium by allowing bounded
    rationality. As lambda → infinity, the QRE approaches a Nash
    equilibrium. This implementation uses PyGambit's ``logit_solve``,
    which path-follows the principal branch of the LQRE correspondence
    to its limiting point.

    Args:
        A: Row player payoff matrix.
        B: Column player payoff matrix.
        lam: Not used directly (PyGambit follows the full branch);
             included for API consistency.

    Returns:
        A single-element list containing the limiting QRE (approximate Nash).
    """
    try:
        import pygambit as gbt
    except ImportError:
        log.warning("pygambit_not_installed", fallback="lemke_howson")
        return solve_lemke_howson(A, B)

    game = gbt.Game.from_arrays(A, B, title="Policy Response Game")
    result = gbt.nash.logit_solve(game)
    eq = result.equilibria[0]
    row_s = np.array([float(p) for p in eq[0]])
    col_s = np.array([float(p) for p in eq[1]])

    # Normalize (PyGambit returns unnormalized probabilities)
    row_s = row_s / row_s.sum() if row_s.sum() > 0 else row_s
    col_s = col_s / col_s.sum() if col_s.sum() > 0 else col_s

    equilibrium = _equilibrium_from_arrays(row_s, col_s, A, B, "logit_qre")
    log.info("logit_qre_done", row_payoff=equilibrium.row_payoff)
    return [equilibrium]


def solve_game(
    A: np.ndarray,
    B: np.ndarray,
    method: SolverMethod = SolverMethod.SUPPORT_ENUMERATION,
) -> list[Equilibrium]:
    """Unified entry point: solve a bimatrix game with the chosen method.

    Args:
        A: Row player payoff matrix.
        B: Column player payoff matrix.
        method: Which solver to use.

    Returns:
        List of Equilibrium objects. Empty if no equilibrium found.
    """
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)

    if A.shape != B.shape:
        raise ValueError(f"Payoff matrices must have the same shape: {A.shape} vs {B.shape}")

    dispatch = {
        SolverMethod.SUPPORT_ENUMERATION: solve_support_enumeration,
        SolverMethod.LEMKE_HOWSON: solve_lemke_howson,
        SolverMethod.VERTEX_ENUMERATION: solve_vertex_enumeration,
        SolverMethod.LOGIT_QRE: solve_logit_qre,
    }

    solver = dispatch.get(method)
    if solver is None:
        raise ValueError(f"Unknown solver method: {method}")

    try:
        return solver(A, B)
    except Exception as exc:
        log.error("solver_failed", method=method.value, error=str(exc))
        # Fallback to Lemke-Howson, which is the most robust
        if method != SolverMethod.LEMKE_HOWSON:
            log.info("falling_back_to_lemke_howson")
            return solve_lemke_howson(A, B)
        raise
