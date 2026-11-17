from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

from .model import (
    DemandGroup,
    Route,
    format_hhmm,
    load_demand_groups,
    load_routes,
    parse_hhmm,
    solve_scenario,
)


ROOT = Path(__file__).resolve().parents[1]
ROUTE_FILE = ROOT / "data" / "input" / "bus_routes.csv"
PREDICTED_DEMAND_FILE = (
    ROOT / "data" / "input" / "predicted_demand_2026-11-14.csv"
)
DB_FILE = ROOT / "passenger_flow.db"
TARGET_DATE = "2026-11-14"
SCENARIO_ID = "predicted_2026_11_14"
WINDOW_START = parse_hhmm("00:00")
WINDOW_END = parse_hhmm("09:00")
PLANNED_TRIPS = 40
MODES = ("baseline", "efficiency", "fairness")


def route_payload(route: Route) -> dict[str, object]:
    """Return route metadata that the frontend may display."""
    return {
        "route_id": route.route_id,
        "route_name": route.route_name,
        "origin": route.origin,
        "destination": route.destination,
        "capacity": route.capacity,
        "min_headway_min": route.min_headway_min,
        "max_headway_min": route.max_headway_min,
        "service_start": format_hhmm(route.service_start_min),
        "service_end": format_hhmm(route.service_end_min),
        "travel_min": route.travel_min,
        "demand_share": route.demand_share,
        "planned_trips": route.planned_trips,
        "source_id": route.source_id,
        "verification": route.verification,
    }


def _timetable_payload(result: dict[str, object], route_id: str) -> list[dict]:
    """Aggregate raw trip records into frontend-ready timetable rows."""
    trips = [
        trip
        for trip in result["trips"]
        if trip.route_id == route_id
    ]
    trips.sort(key=lambda trip: trip.departure_min)

    timetable = []
    for trip in trips:
        load_rate = (
            trip.load / trip.capacity
            if trip.capacity
            else 0.0
        )
        timetable.append(
            {
                "trip_no": trip.trip_no,
                "departure_time": format_hhmm(trip.departure_min),
                "load": trip.load,
                "capacity": trip.capacity,
                "load_rate": round(load_rate, 4),
            }
        )
    return timetable


def serialize_dispatch_result(result: dict[str, object]) -> dict[str, object]:
    """Keep only display-oriented results and never expose assignments."""
    route_results = []
    for route_result in result["route_results"]:
        route = route_result["route"]
        route_results.append(
            {
                "route_id": route.route_id,
                "route_name": route.route_name,
                "origin": route.origin,
                "destination": route.destination,
                "capacity": route.capacity,
                "service_start": format_hhmm(route.service_start_min),
                "service_end": format_hhmm(route.service_end_min),
                "planned_trips": route.planned_trips,
                "verification": route.verification,
                "summary": route_result["summary"],
                "departures": [
                    format_hhmm(departure)
                    for departure in route_result["departures"]
                ],
                "timetable": _timetable_payload(result, route.route_id),
            }
        )

    return {
        "mode": result["mode"],
        "summary": result["summary"],
        "route_results": route_results,
    }


def _raw_predicted_total() -> float:
    with sqlite3.connect(DB_FILE) as connection:
        rows = connection.execute(
            """
            SELECT time, bus_passengers
            FROM minute_passenger_flow
            WHERE date = ?
            ORDER BY time
            """,
            (TARGET_DATE,),
        ).fetchall()

    return sum(
        float(passengers)
        for time_text, passengers in rows
        if WINDOW_START <= parse_hhmm(time_text) <= WINDOW_END
    )


def load_predicted_inputs() -> tuple[list[Route], list[DemandGroup]]:
    routes = [
        replace(
            route,
            service_start_min=WINDOW_START,
            service_end_min=WINDOW_END,
            planned_trips=PLANNED_TRIPS,
        )
        for route in load_routes(ROUTE_FILE)
    ]
    groups = load_demand_groups(PREDICTED_DEMAND_FILE)
    return routes, groups


def build_predicted_dispatch_payload() -> dict[str, object]:
    """Build the complete display payload from the current predicted inputs."""
    routes, groups = load_predicted_inputs()
    results = [
        serialize_dispatch_result(
            solve_scenario(routes, groups, SCENARIO_ID, mode)
        )
        for mode in MODES
    ]

    return {
        "meta": {
            "scenario_id": SCENARIO_ID,
            "date": TARGET_DATE,
            "window": f"{format_hhmm(WINDOW_START)}-{format_hhmm(WINDOW_END)}",
            "source": "passenger_flow.db",
            "raw_predicted_passengers_in_window": round(
                _raw_predicted_total(), 6
            ),
            "note": "客流预测系数为手工设定，线路需求按均分假设；结果用于情景推演。",
        },
        "routes": [
            route_payload(route)
            for route in routes
        ],
        "results": results,
    }
