# src/game_theory/models.py
"""Payoff functions for the Policy Response Game.

The game models the strategic interaction between landlords and consumers
in a housing market, with government policy as a parameter that shifts
payoff matrices. Employer wage response is modeled as a sub-game that
feeds a wage multiplier into the consumer payoff.

All monetary values are in the same currency (CAD or USD) and normalized
to annual terms where applicable.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np

from src.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Strategy enumerations
# ---------------------------------------------------------------------------

class LandlordStrategy(str, Enum):
    """Landlord's available strategies."""
    AGGRESSIVE = "aggressive"       # maximize rent, accept higher vacancy
    MODERATE = "moderate"           # market-rate rent, balanced occupancy
    WITHHOLD = "withhold"           # reduce supply, wait for better conditions


class ConsumerStrategy(str, Enum):
    """Consumer's available strategies."""
    STAY = "stay"                   # remain in current housing, pay market rent
    MOVE = "move"                   # relocate, incur moving cost
    REDUCE = "reduce"               # reduce consumption basket, lower quality


LANDLORD_STRATEGIES = [
    LandlordStrategy.AGGRESSIVE,
    LandlordStrategy.MODERATE,
    LandlordStrategy.WITHHOLD,
]

CONSUMER_STRATEGIES = [
    ConsumerStrategy.STAY,
    ConsumerStrategy.MOVE,
    ConsumerStrategy.REDUCE,
]


# ---------------------------------------------------------------------------
# Policy configuration
# ---------------------------------------------------------------------------

@dataclass
class PolicyConfig:
    """Government policy levers that parameterize the game.

    Attributes:
        rent_cap_pct: Maximum annual rent increase (%), e.g. 3.0 = 3%.
        housing_subsidy: Monthly subsidy per household (local currency).
        min_wage_delta_pct: Minimum wage change (%), e.g. 10.0 = +10%.
        property_tax_delta_pp: Property tax change in percentage points.
        base_year: Reference year for calibrating baseline values.
    """

    rent_cap_pct: float = 3.0
    housing_subsidy: float = 500.0
    min_wage_delta_pct: float = 10.0
    property_tax_delta_pp: float = 0.0
    base_year: int = 2023

    def __post_init__(self):
        if self.rent_cap_pct < 0:
            raise ValueError("rent_cap_pct must be non-negative")
        if self.housing_subsidy < 0:
            raise ValueError("housing_subsidy must be non-negative")


@dataclass
class MarketCalibration:
    """Baseline market values used to calibrate payoff functions.

    These values should be sourced from the warehouse (Layer 2) for the
    selected region and year, so the game's baseline equilibrium matches
    observed conditions.
    """

    median_income: float = 75_000.0     # annual household income
    average_rent: float = 2_000.0       # monthly rent
    cpi: float = 150.0                  # consumer price index
    unemployment_rate: float = 6.0      # %
    currency: str = "CAD"

    @property
    def annual_rent(self) -> float:
        return self.average_rent * 12.0

    @property
    def rent_to_income(self) -> float:
        """Baseline rent-to-income ratio (%)."""
        if self.median_income == 0:
            return 0.0
        return (self.annual_rent / self.median_income) * 100.0


# ---------------------------------------------------------------------------
# Payoff engine
# ---------------------------------------------------------------------------

@dataclass
class PayoffEngine:
    """Computes payoff matrices for the landlord-consumer game.

    The engine translates policy parameters and market calibration into
    a 3x3 bimatrix game. All payoffs are in "utility units" normalized so
    that the baseline equilibrium matches observed market conditions.

    Attributes:
        calibration: Baseline market values.
        policy: Government policy configuration.
        maintenance_cost_per_unit: Annual maintenance cost per housing unit.
        vacancy_cost_per_unit: Annual cost of a vacant unit (lost rent + carrying).
        moving_cost: One-time cost of relocating (annualized).
        quality_loss: Utility penalty from reducing consumption.
        employer_wage_response: Fraction of min wage increase passed to wages (0-1).
        landlord_supply_elasticity: How much supply withholding raises rents.
    """

    calibration: MarketCalibration
    policy: PolicyConfig
    maintenance_cost_per_unit: float = 8_000.0
    vacancy_cost_per_unit: float = 12_000.0
    moving_cost: float = 5_000.0
    quality_loss: float = 3_000.0
    employer_wage_response: float = 0.7
    landlord_supply_elasticity: float = 0.15

    # ----- Landlord payoff -------------------------------------------------

    def landlord_payoffs(self) -> np.ndarray:
        """Compute the landlord payoff matrix (3x3, rows = landlord strategies).

        Returns:
            Array of shape (3, 3) where entry [i, j] is the landlord's
            payoff when playing strategy i against consumer strategy j.
        """
        base_rent = self.calibration.average_rent
        annual_rent = base_rent * 12.0
        income = self.calibration.median_income

        # Effective rent ceiling from policy
        rent_cap = self.policy.rent_cap_pct / 100.0
        # Aggressive strategy targets rent growth above inflation; capped by policy
        aggressive_rent = annual_rent * (1.0 + max(rent_cap, 0.08))
        moderate_rent = annual_rent * (1.0 + max(rent_cap, 0.04))
        withhold_rent = annual_rent * (1.0 + self.landlord_supply_elasticity)

        # Occupancy assumptions per strategy
        occ_aggressive = 0.85   # higher rent → more vacancy
        occ_moderate = 0.95     # market rate → high occupancy
        occ_withhold = 0.70     # reduced supply → intentional vacancy

        # Maintenance cost scales with units offered
        units_aggressive = 1.0
        units_moderate = 1.0
        units_withhold = 0.75   # withholding reduces offered units

        # Property tax: base rate 1.2% of property value, plus policy delta
        base_prop_tax_rate = 0.012
        prop_tax_rate = base_prop_tax_rate + (self.policy.property_tax_delta_pp / 100.0)
        prop_tax_rate = max(prop_tax_rate, 0.0)

        # Property value proxy: 20x annual rent (cap rate ~5%)
        property_value = annual_rent * 20.0

        # Consumer strategy effect on landlord revenue:
        # - Stay: full rent
        # - Move: landlord loses tenant for a period (half-year vacancy)
        # - Reduce: consumer negotiates or reduces quality, small rent reduction
        consumer_effects = {
            ConsumerStrategy.STAY: 1.0,
            ConsumerStrategy.MOVE: 0.5,     # half-year vacancy
            ConsumerStrategy.REDUCE: 0.9,   # 10% effective reduction
        }

        strategies = [
            (aggressive_rent, occ_aggressive, units_aggressive),
            (moderate_rent, occ_moderate, units_moderate),
            (withhold_rent, occ_withhold, units_withhold),
        ]

        matrix = np.zeros((3, 3))
        for i, (rent, occ, units) in enumerate(strategies):
            for j, consumer_strat in enumerate(CONSUMER_STRATEGIES):
                effective_rent = rent * consumer_effects[consumer_strat]
                revenue = effective_rent * occ * units
                maintenance = self.maintenance_cost_per_unit * units
                vacancy_loss = self.vacancy_cost_per_unit * (1.0 - occ) * units
                property_tax = prop_tax_rate * property_value * units
                payoff = revenue - maintenance - vacancy_loss - property_tax
                matrix[i, j] = payoff

        # Normalize to utility units (divide by income so payoffs are comparable)
        matrix = matrix / max(income, 1.0) * 100.0
        log.debug("landlord_payoffs_computed", shape=matrix.shape)
        return matrix

    # ----- Consumer payoff -------------------------------------------------

    def consumer_payoffs(self) -> np.ndarray:
        """Compute the consumer payoff matrix (3x3, rows = consumer strategies).

        Returns:
            Array of shape (3, 3) where entry [i, j] is the consumer's
            payoff when playing strategy i against landlord strategy j.
        """
        income = self.calibration.median_income
        base_rent = self.calibration.average_rent
        annual_rent = base_rent * 12.0

        # Wage response: employer passes a fraction of min wage increase to wages
        wage_multiplier = 1.0 + (
            self.policy.min_wage_delta_pct / 100.0 * self.employer_wage_response
        )
        effective_income = income * wage_multiplier

        # Housing subsidy (annualized)
        subsidy_annual = self.policy.housing_subsidy * 12.0

        # Non-housing consumption basket (CPI-scaled)
        non_housing = effective_income * 0.45  # ~45% of income on non-housing

        # Landlord strategy effect on consumer rent:
        # - Aggressive: consumer pays high rent
        # - Moderate: consumer pays market rent
        # - Withhold: supply shortage → consumer pays above-market (shadow rent)
        landlord_effects = {
            LandlordStrategy.AGGRESSIVE: 1.0 + max(self.policy.rent_cap_pct / 100.0, 0.08),
            LandlordStrategy.MODERATE: 1.0 + max(self.policy.rent_cap_pct / 100.0, 0.04),
            LandlordStrategy.WITHHOLD: 1.0 + self.landlord_supply_elasticity,
        }

        matrix = np.zeros((3, 3))
        for i, consumer_strat in enumerate(CONSUMER_STRATEGIES):
            for j, landlord_strat in enumerate(LANDLORD_STRATEGIES):
                rent_annual = annual_rent * landlord_effects[landlord_strat]

                if consumer_strat == ConsumerStrategy.STAY:
                    housing_cost = rent_annual
                    moving_penalty = 0.0
                    quality_penalty = 0.0
                elif consumer_strat == ConsumerStrategy.MOVE:
                    housing_cost = rent_annual * 0.85   # slightly cheaper market
                    moving_penalty = self.moving_cost
                    quality_penalty = 0.0
                else:  # REDUCE
                    housing_cost = rent_annual * 0.80
                    moving_penalty = 0.0
                    quality_penalty = self.quality_loss

                utility = (
                    effective_income
                    + subsidy_annual
                    - housing_cost
                    - non_housing
                    - moving_penalty
                    - quality_penalty
                )
                matrix[i, j] = utility

        # Normalize to utility units
        matrix = matrix / max(income, 1.0) * 100.0
        log.debug("consumer_payoffs_computed", shape=matrix.shape)
        return matrix

    # ----- Employer sub-game -----------------------------------------------

    def employer_payoff(
        self,
        wage_adjustment_pct: float,
        consumer_retention: float,
    ) -> float:
        """Compute employer payoff for a given wage adjustment.

        Args:
            wage_adjustment_pct: Employer's wage increase (%), e.g. 5.0 = +5%.
            consumer_retention: Fraction of workers retained (0-1).

        Returns:
            Employer payoff in normalized utility units.
        """
        income = self.calibration.median_income
        labor_cost = income * (1.0 + wage_adjustment_pct / 100.0)
        turnover_cost = 15_000.0 * (1.0 - consumer_retention)
        revenue = income * 2.5  # revenue per worker (simplified)
        payoff = revenue - labor_cost - turnover_cost
        return payoff / max(income, 1.0) * 100.0

    # ----- Combined game ---------------------------------------------------

    def build_game_matrices(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (landlord_payoffs, consumer_payoffs) matrices for the bimatrix game.

        Both matrices have shape (3, 3):
            rows    = landlord strategies (AGGRESSIVE, MODERATE, WITHHOLD)
            columns = consumer strategies (STAY, MOVE, REDUCE)
        """
        return self.landlord_payoffs(), self.consumer_payoffs()
