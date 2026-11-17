from __future__ import annotations

import csv
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Route:
    route_id: str
    route_name: str
    origin: str
    destination: str
    capacity: int
    min_headway_min: int
    max_headway_min: int
    service_start_min: int
    service_end_min: int
    travel_min: int
    demand_share: float
    planned_trips: int
    source_id: str
    verification: str


@dataclass(frozen=True)
class DemandGroup:
    scenario_id: str
    demand_id: str
    route_id: str
    train_id: str
    arrival_min: int
    passengers: int
    source_id: str


@dataclass(frozen=True)
class Assignment:
    scenario_id: str
    mode: str
    route_id: str
    demand_id: str
    train_id: str
    arrival_min: int
    departure_min: int
    passengers: int
    wait_min: float


@dataclass(frozen=True)
class TripRecord:
    scenario_id: str
    mode: str
    route_id: str
    trip_no: int
    departure_min: int
    load: int
    capacity: int


@dataclass
class State:
    total_wait: float
    max_wait: float


@dataclass
class SimulationResult:
    assignments: list[Assignment]
    trips: list[TripRecord]
    summary: dict[str, float | int]


def parse_hhmm(value: str) -> int:
    hour, minute = value.strip().split(":")
    return int(hour) * 60 + int(minute)


def format_hhmm(total_minutes: int) -> str:
    total_minutes %= 24 * 60
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def load_routes(path: Path) -> list[Route]:
    routes: list[Route] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            routes.append(
                Route(
                    route_id=row["route_id"].strip(),
                    route_name=row["route_name"].strip(),
                    origin=row["origin"].strip(),
                    destination=row["destination"].strip(),
                    capacity=int(row["capacity"]),
                    min_headway_min=int(row["min_headway_min"]),
                    max_headway_min=int(row["max_headway_min"]),
                    service_start_min=parse_hhmm(row["service_start"]),
                    service_end_min=parse_hhmm(row["service_end"]),
                    travel_min=int(row["travel_min"]),
                    demand_share=float(row["demand_share"]),
                    planned_trips=int(row["planned_trips"]),
                    source_id=row["source_id"].strip(),
                    verification=row["verification"].strip(),
                )
            )
    return routes


def load_demand_groups(path: Path) -> list[DemandGroup]:
    groups: list[DemandGroup] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            groups.append(
                DemandGroup(
                    scenario_id=row["scenario_id"].strip(),
                    demand_id=row["demand_id"].strip(),
                    route_id=row["route_id"].strip(),
                    train_id=row["train_id"].strip(),
                    arrival_min=int(row["platform_arrival_min"]),
                    passengers=int(row["passengers"]),
                    source_id=row["source_id"].strip(),
                )
            )
    return groups


def build_baseline_departures(route: Route) -> list[int]:
    duration = route.service_end_min - route.service_start_min
    if route.planned_trips < 2:
        raise ValueError(f"{route.route_id}: planned_trips must be at least 2")
    departures = [
        route.service_start_min
        + round(index * duration / (route.planned_trips - 1))
        for index in range(route.planned_trips)
    ]
    return sorted(set(departures))


def _state_key(state: State, mode: str) -> tuple[float, float]:
    if mode == "efficiency":
        return state.total_wait, state.max_wait
    if mode == "fairness":
        return state.max_wait, state.total_wait
    raise ValueError(f"Unsupported optimization mode: {mode}")


def optimize_departures(
    route: Route,
    groups: Iterable[DemandGroup],
    mode: str,
) -> list[int]:
    """Solve the fixed-trip-budget schedule problem with dynamic programming."""
    demand_by_minute: dict[int, int] = {}
    for group in groups:
        if route.service_start_min <= group.arrival_min <= route.service_end_min:
            demand_by_minute[group.arrival_min] = (
                demand_by_minute.get(group.arrival_min, 0) + group.passengers
            )

    if demand_by_minute.get(route.service_start_min, 0) > route.capacity:
        raise ValueError(f"{route.route_id}: demand at service start exceeds capacity")

    times = list(range(route.service_start_min, route.service_end_min + 1))
    count = len(times)
    trip_count = route.planned_trips
    passengers_at = [demand_by_minute.get(time, 0) for time in times]

    prefix_passengers = [0] * (count + 1)
    prefix_weighted_arrival = [0] * (count + 1)
    for index, passengers in enumerate(passengers_at):
        prefix_passengers[index + 1] = prefix_passengers[index] + passengers
        prefix_weighted_arrival[index + 1] = (
            prefix_weighted_arrival[index] + passengers * times[index]
        )

    next_demand = [count] * (count + 1)
    next_index = count
    for index in range(count - 1, -1, -1):
        if passengers_at[index] > 0:
            next_index = index
        next_demand[index] = next_index

    start_state = State(total_wait=0.0, max_wait=0.0)
    previous: dict[int, State] = {0: start_state}
    parents: list[dict[int, int]] = [{0: -1}]

    for trips_used in range(2, trip_count + 1):
        current: dict[int, State] = {}
        current_parents: dict[int, int] = {}
        remaining_after = trip_count - trips_used
        for current_index in range(1, count):
            best_state: State | None = None
            best_previous_index = -1
            max_reach = times[current_index] + remaining_after * route.max_headway_min
            min_reach = times[current_index] + remaining_after * route.min_headway_min
            if max_reach < route.service_end_min or min_reach > route.service_end_min:
                continue

            for previous_index, previous_state in previous.items():
                gap = times[current_index] - times[previous_index]
                if gap < route.min_headway_min:
                    continue
                if gap > route.max_headway_min:
                    continue
                passengers = (
                    prefix_passengers[current_index + 1]
                    - prefix_passengers[previous_index + 1]
                )
                if passengers > route.capacity:
                    continue
                weighted_arrival = (
                    prefix_weighted_arrival[current_index + 1]
                    - prefix_weighted_arrival[previous_index + 1]
                )
                edge_total_wait = (
                    times[current_index] * passengers - weighted_arrival
                )
                first_demand_index = next_demand[previous_index + 1]
                if first_demand_index <= current_index:
                    edge_max_wait = (
                        times[current_index] - times[first_demand_index]
                    )
                else:
                    edge_max_wait = 0
                candidate = State(
                    total_wait=previous_state.total_wait + edge_total_wait,
                    max_wait=max(previous_state.max_wait, edge_max_wait),
                )
                if best_state is None or _state_key(
                    candidate, mode
                ) < _state_key(best_state, mode):
                    best_state = candidate
                    best_previous_index = previous_index
            if best_state is not None:
                current[current_index] = best_state
                current_parents[current_index] = best_previous_index
        previous = current
        parents.append(current_parents)

    final_index = count - 1
    if final_index not in previous:
        raise ValueError(
            f"{route.route_id}: no feasible schedule for {trip_count} trips"
        )

    selected_indices = [final_index]
    index = final_index
    for trips_used in range(trip_count, 1, -1):
        index = parents[trips_used - 1][index]
        selected_indices.append(index)
    selected_indices.reverse()
    return [times[index] for index in selected_indices]


def simulate_route(
    route: Route,
    groups: Iterable[DemandGroup],
    departures: list[int],
    scenario_id: str,
    mode: str,
) -> SimulationResult:
    ordered_groups = sorted(
        (
            group
            for group in groups
            if route.service_start_min <= group.arrival_min <= route.service_end_min
        ),
        key=lambda group: group.arrival_min,
    )
    queue: deque[list[DemandGroup | int]] = deque()
    group_index = 0
    assignments: list[Assignment] = []
    trips: list[TripRecord] = []

    for trip_no, departure_min in enumerate(sorted(departures), start=1):
        while (
            group_index < len(ordered_groups)
            and ordered_groups[group_index].arrival_min <= departure_min
        ):
            group = ordered_groups[group_index]
            queue.append([group, group.passengers])
            group_index += 1

        remaining_capacity = route.capacity
        while queue and remaining_capacity > 0:
            group, remaining_passengers = queue[0]
            assert isinstance(group, DemandGroup)
            assert isinstance(remaining_passengers, int)
            boarded = min(remaining_passengers, remaining_capacity)
            wait_min = departure_min - group.arrival_min
            assignments.append(
                Assignment(
                    scenario_id=scenario_id,
                    mode=mode,
                    route_id=route.route_id,
                    demand_id=group.demand_id,
                    train_id=group.train_id,
                    arrival_min=group.arrival_min,
                    departure_min=departure_min,
                    passengers=boarded,
                    wait_min=wait_min,
                )
            )
            remaining_capacity -= boarded
            remaining_passengers -= boarded
            if remaining_passengers == 0:
                queue.popleft()
            else:
                queue[0][1] = remaining_passengers
                break

        load = route.capacity - remaining_capacity
        trips.append(
            TripRecord(
                scenario_id=scenario_id,
                mode=mode,
                route_id=route.route_id,
                trip_no=trip_no,
                departure_min=departure_min,
                load=load,
                capacity=route.capacity,
            )
        )

    unserved_passengers = sum(
        int(remaining) for _, remaining in queue
    )
    served_passengers = sum(item.passengers for item in assignments)
    total_wait = sum(item.passengers * item.wait_min for item in assignments)
    max_wait = max((item.wait_min for item in assignments), default=0.0)
    p90_wait = weighted_quantile(assignments, 0.90)
    max_load = max((trip.load for trip in trips), default=0)
    mean_load = (
        sum(trip.load for trip in trips) / len(trips) if trips else 0.0
    )
    peak_load_factor = max(
        (trip.load / trip.capacity for trip in trips), default=0.0
    )
    summary: dict[str, float | int] = {
        "passengers_served": served_passengers,
        "passengers_unserved": unserved_passengers,
        "total_wait_passenger_min": float(total_wait),
        "avg_wait_min": (
            float(total_wait) / served_passengers if served_passengers else 0.0
        ),
        "max_wait_min": float(max_wait),
        "p90_wait_min": float(p90_wait),
        "departures": len(trips),
        "max_load": max_load,
        "mean_load": mean_load,
        "peak_load_factor": peak_load_factor,
    }
    return SimulationResult(assignments=assignments, trips=trips, summary=summary)


def weighted_quantile(assignments: list[Assignment], quantile: float) -> float:
    if not assignments:
        return 0.0
    ordered = sorted(assignments, key=lambda item: item.wait_min)
    total_weight = sum(item.passengers for item in ordered)
    threshold = total_weight * quantile
    cumulative = 0
    for item in ordered:
        cumulative += item.passengers
        if cumulative >= threshold:
            return float(item.wait_min)
    return float(ordered[-1].wait_min)


def solve_scenario(
    routes: Iterable[Route],
    groups: Iterable[DemandGroup],
    scenario_id: str,
    mode: str,
) -> dict[str, object]:
    all_groups = list(groups)
    route_results: list[dict[str, object]] = []
    all_assignments: list[Assignment] = []
    all_trips: list[TripRecord] = []

    for route in routes:
        route_groups = [
            group
            for group in all_groups
            if group.scenario_id == scenario_id and group.route_id == route.route_id
        ]
        if mode == "baseline":
            departures = build_baseline_departures(route)
        elif mode in {"efficiency", "fairness"}:
            departures = optimize_departures(route, route_groups, mode)
        else:
            raise ValueError(f"Unsupported mode: {mode}")
        simulation = simulate_route(
            route=route,
            groups=route_groups,
            departures=departures,
            scenario_id=scenario_id,
            mode=mode,
        )
        all_assignments.extend(simulation.assignments)
        all_trips.extend(simulation.trips)
        route_results.append(
            {
                "route": route,
                "departures": departures,
                "summary": simulation.summary,
            }
        )

    total_passengers = sum(
        int(result["summary"]["passengers_served"]) for result in route_results
    )
    total_wait = sum(
        float(result["summary"]["total_wait_passenger_min"])
        for result in route_results
    )
    summary: dict[str, float | int] = {
        "passengers_served": total_passengers,
        "passengers_unserved": sum(
            int(result["summary"]["passengers_unserved"])
            for result in route_results
        ),
        "total_wait_passenger_min": total_wait,
        "avg_wait_min": total_wait / total_passengers if total_passengers else 0.0,
        "max_wait_min": max(
            float(result["summary"]["max_wait_min"]) for result in route_results
        ),
        "p90_wait_min": max(
            float(result["summary"]["p90_wait_min"]) for result in route_results
        ),
        "departures": sum(
            int(result["summary"]["departures"]) for result in route_results
        ),
        "max_load": max(
            int(result["summary"]["max_load"]) for result in route_results
        ),
        "mean_load": (
            sum(float(result["summary"]["mean_load"]) for result in route_results)
            / len(route_results)
            if route_results
            else 0.0
        ),
        "peak_load_factor": max(
            float(result["summary"]["peak_load_factor"])
            for result in route_results
        ),
    }
    return {
        "scenario_id": scenario_id,
        "mode": mode,
        "summary": summary,
        "route_results": route_results,
        "assignments": all_assignments,
        "trips": all_trips,
    }
