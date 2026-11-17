from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.model import load_demand_groups, load_routes, solve_scenario


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.routes = load_routes(ROOT / "data" / "input" / "bus_routes.csv")
        cls.demands = load_demand_groups(
            ROOT / "data" / "input" / "demand_groups.csv"
        )
        cls.results = {}
        for scenario_id in ("normal", "holiday_peak", "bad_weather"):
            for mode in ("baseline", "efficiency", "fairness"):
                cls.results[(scenario_id, mode)] = solve_scenario(
                    cls.routes, cls.demands, scenario_id, mode
                )

    def test_all_passengers_are_served(self) -> None:
        for result in self.results.values():
            self.assertEqual(result["summary"]["passengers_unserved"], 0)

    def test_trip_budget_and_headway_constraints(self) -> None:
        for (scenario_id, mode), result in self.results.items():
            for route_result in result["route_results"]:
                route = route_result["route"]
                departures = route_result["departures"]
                self.assertEqual(len(departures), route.planned_trips)
                self.assertEqual(departures[0], route.service_start_min)
                self.assertEqual(departures[-1], route.service_end_min)
                gaps = [
                    right - left
                    for left, right in zip(departures, departures[1:])
                ]
                self.assertGreaterEqual(min(gaps), route.min_headway_min)
                self.assertLessEqual(max(gaps), route.max_headway_min)

    def test_efficiency_reduces_total_wait(self) -> None:
        for scenario_id in ("normal", "holiday_peak", "bad_weather"):
            baseline = self.results[(scenario_id, "baseline")]["summary"]
            efficiency = self.results[(scenario_id, "efficiency")]["summary"]
            self.assertLessEqual(
                efficiency["total_wait_passenger_min"],
                baseline["total_wait_passenger_min"],
            )

    def test_fairness_reduces_max_wait(self) -> None:
        for scenario_id in ("normal", "holiday_peak", "bad_weather"):
            baseline = self.results[(scenario_id, "baseline")]["summary"]
            fairness = self.results[(scenario_id, "fairness")]["summary"]
            self.assertLessEqual(
                fairness["max_wait_min"],
                baseline["max_wait_min"],
            )

    def test_holiday_tradeoff_is_visible(self) -> None:
        efficiency = self.results[("holiday_peak", "efficiency")]["summary"]
        fairness = self.results[("holiday_peak", "fairness")]["summary"]
        self.assertLessEqual(
            efficiency["total_wait_passenger_min"],
            fairness["total_wait_passenger_min"],
        )
        self.assertLessEqual(
            fairness["max_wait_min"],
            efficiency["max_wait_min"],
        )


if __name__ == "__main__":
    unittest.main()
