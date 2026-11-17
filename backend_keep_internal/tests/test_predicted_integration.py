from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "outputs" / "predicted_flow" / "results"
PAYLOAD = ROOT / "outputs" / "frontend" / "predicted_demo_payload.json"


class PredictedIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (RESULT_DIR / "summary.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            cls.summary = {
                row["mode"]: row for row in csv.DictReader(handle)
            }

    def test_all_predicted_passengers_are_served(self) -> None:
        for row in self.summary.values():
            self.assertEqual(int(row["passengers_unserved"]), 0)
            self.assertGreater(int(row["passengers_served"]), 2500)

    def test_efficiency_improves_total_wait(self) -> None:
        self.assertLess(
            float(self.summary["efficiency"]["total_wait_passenger_min"]),
            float(self.summary["baseline"]["total_wait_passenger_min"]),
        )

    def test_fairness_improves_max_wait(self) -> None:
        self.assertLessEqual(
            float(self.summary["fairness"]["max_wait_min"]),
            float(self.summary["baseline"]["max_wait_min"]),
        )

    def test_frontend_payload_is_valid(self) -> None:
        payload = json.loads(PAYLOAD.read_text(encoding="utf-8"))
        self.assertEqual(payload["meta"]["scenario_id"], "predicted_2026_11_14")
        self.assertEqual(len(payload["results"]), 3)
        self.assertEqual(
            list(payload["results"][0]),
            ["mode", "summary", "route_results"],
        )
        self.assertNotIn("assignments", payload)
        self.assertNotIn("trips", payload)

        first_route = payload["results"][0]["route_results"][0]
        self.assertEqual(len(first_route["timetable"]), 40)
        self.assertEqual(
            set(first_route["timetable"][0]),
            {"trip_no", "departure_time", "load", "capacity", "load_rate"},
        )


if __name__ == "__main__":
    unittest.main()
