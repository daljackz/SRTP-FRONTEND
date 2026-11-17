from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input"


def parse_hhmm(value: str) -> int:
    hour, minute = value.strip().split(":")
    return int(hour) * 60 + int(minute)


def format_hhmm(total_minutes: int) -> str:
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def load_routes() -> list[dict[str, str]]:
    with (INPUT_DIR / "bus_routes.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        return list(csv.DictReader(handle))


def load_profiles() -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    with (INPUT_DIR / "scenario_profiles.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        for row in csv.DictReader(handle):
            grouped[row["scenario_id"]].append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: parse_hhmm(row["period_start"]))
    return grouped


def allocate_passengers(
    total: int,
    routes: list[dict[str, str]],
    rotation: int,
) -> dict[str, int]:
    shares = [float(route["demand_share"]) for route in routes]
    raw = [total * share for share in shares]
    allocated = [math.floor(value) for value in raw]
    remainder = total - sum(allocated)
    ranking = sorted(
        range(len(routes)),
        key=lambda index: (
            -(raw[index] - allocated[index]),
            (index - rotation) % len(routes),
        ),
    )
    for index in ranking[:remainder]:
        allocated[index] += 1
    return {
        route["route_id"]: allocated[index]
        for index, route in enumerate(routes)
    }


def build() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    routes = load_routes()
    profiles = load_profiles()
    train_rows: list[dict[str, object]] = []
    demand_rows: list[dict[str, object]] = []

    for scenario_id, segments in profiles.items():
        train_index = 0
        for segment in segments:
            start = parse_hhmm(segment["period_start"])
            end = parse_hhmm(segment["period_end"])
            trains_per_hour = float(segment["trains_per_hour"])
            spacing = max(1, round(60 / trains_per_hour))
            base_alighters = float(segment["avg_alighters_per_train"])
            base_walk = int(float(segment["walk_min"]))
            multiplier = float(segment["demand_multiplier"])
            source_id = segment["source_id"]

            arrival = start
            while arrival < end:
                train_index += 1
                variation = 0.94 + ((train_index * 7) % 13) / 100
                alighters = max(1, round(base_alighters * multiplier * variation))
                walk_min = max(
                    3,
                    base_walk + ((train_index * 5) % 5) - 2,
                )
                platform_arrival = arrival + walk_min
                train_id = f"{scenario_id.upper()}-{train_index:03d}"
                train_rows.append(
                    {
                        "scenario_id": scenario_id,
                        "train_id": train_id,
                        "scheduled_arrival": format_hhmm(arrival),
                        "scheduled_arrival_min": arrival,
                        "estimated_alighters": alighters,
                        "walk_min": walk_min,
                        "platform_arrival": format_hhmm(platform_arrival),
                        "platform_arrival_min": platform_arrival,
                        "source_id": source_id,
                    }
                )
                allocation = allocate_passengers(alighters, routes, train_index)
                for route in routes:
                    route_id = route["route_id"]
                    passengers = allocation[route_id]
                    if passengers <= 0:
                        continue
                    demand_rows.append(
                        {
                            "scenario_id": scenario_id,
                            "demand_id": f"{train_id}-{route_id}",
                            "route_id": route_id,
                            "train_id": train_id,
                            "platform_arrival_min": platform_arrival,
                            "platform_arrival": format_hhmm(platform_arrival),
                            "passengers": passengers,
                            "walk_min": walk_min,
                            "source_id": source_id,
                        }
                    )
                arrival += spacing

    service_start = 18 * 60
    service_end = 23 * 60
    train_rows = [
        row
        for row in train_rows
        if service_start <= int(row["platform_arrival_min"]) <= service_end
    ]
    valid_train_ids = {str(row["train_id"]) for row in train_rows}
    demand_rows = [
        row for row in demand_rows if str(row["train_id"]) in valid_train_ids
    ]
    return train_rows, demand_rows


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    trains, demands = build()
    write_rows(INPUT_DIR / "train_arrivals.csv", trains)
    write_rows(INPUT_DIR / "demand_groups.csv", demands)
    print(f"Generated {len(trains)} train records and {len(demands)} demand groups")


if __name__ == "__main__":
    main()
