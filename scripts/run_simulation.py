#!/usr/bin/env python3
# scripts/run_simulation.py
"""Run policy simulations from the command line.

Usage:
    python scripts/run_simulation.py --scenario "Tight Rent Control (2%)"
    python scripts/run_simulation.py --all --compare
    python scripts/run_simulation.py --rent-cap 5 --subsidy 1000 --output results.json
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.game_theory.models import MarketCalibration, PolicyConfig
from src.game_theory.scenarios import SCENARIOS, get_scenario
from src.game_theory.simulator import compare_scenarios, simulate_policy
from src.game_theory.solvers import SolverMethod
from src.utils.logger import configure_logging, get_logger

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Run policy simulations.")
    parser.add_argument("--scenario", help="Name of a pre-built scenario.")
    parser.add_argument("--all", action="store_true", help="Run all scenarios.")
    parser.add_argument("--compare", action="store_true", help="Rank scenarios.")
    parser.add_argument("--rent-cap", type=float, default=3.0)
    parser.add_argument("--subsidy", type=float, default=500.0)
    parser.add_argument("--min-wage", type=float, default=10.0)
    parser.add_argument("--prop-tax", type=float, default=0.0)
    parser.add_argument("--output", help="Write JSON results to this path.")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    configure_logging(args.log_level)
    log = get_logger("simulation")

    calibration = MarketCalibration()

    if args.all or args.compare:
        ranked = compare_scenarios(SCENARIOS, calibration, method=SolverMethod.LEMKE_HOWSON)
        log.info("scenario_ranking", count=len(ranked))
        for i, r in enumerate(ranked, 1):
            log.info(
                "scenario",
                rank=i,
                name=r["name"],
                composite=round(r["composite"], 3),
                rent_to_income=round(r["rent_to_income_pct"], 1),
            )
        if args.output:
            with open(args.output, "w") as fh:
                json.dump(
                    [
                        {
                            "name": r["name"],
                            "composite": r["composite"],
                            "rent_to_income_pct": r["rent_to_income_pct"],
                            "budget_balance": r["budget_balance"],
                        }
                        for r in ranked
                    ],
                    fh,
                    indent=2,
                )
            log.info("results_written", path=args.output)
        return

    if args.scenario:
        policy = get_scenario(args.scenario)
        if policy is None:
            log.error("scenario_not_found", name=args.scenario)
            sys.exit(1)
    else:
        policy = PolicyConfig(
            rent_cap_pct=args.rent_cap,
            housing_subsidy=args.subsidy,
            min_wage_delta_pct=args.min_wage,
            property_tax_delta_pp=args.prop_tax,
        )

    result = simulate_policy(policy, calibration, method=SolverMethod.LEMKE_HOWSON)
    log.info("simulation_result", **result.to_dict())

    if args.output:
        with open(args.output, "w") as fh:
            json.dump(result.to_dict(), fh, indent=2, default=str)
        log.info("results_written", path=args.output)


if __name__ == "__main__":
    main()
