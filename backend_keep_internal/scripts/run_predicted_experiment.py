from __future__ import annotations

import csv
import json
import math
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.model import (  # noqa: E402
    DemandGroup,
    Route,
    format_hhmm,
    load_routes,
    parse_hhmm,
    solve_scenario,
)
from src.frontend_payload import (  # noqa: E402
    route_payload as serialize_route,
    serialize_dispatch_result,
)


DB_FILE = ROOT / "passenger_flow.db"
ROUTE_FILE = ROOT / "data" / "input" / "bus_routes.csv"
DEMAND_FILE = ROOT / "data" / "input" / "predicted_demand_2026-11-14.csv"
OUTPUT_DIR = ROOT / "outputs" / "predicted_flow"
RESULT_DIR = OUTPUT_DIR / "results"
FIGURE_DIR = OUTPUT_DIR / "figures"
FRONTEND_DIR = ROOT / "outputs" / "frontend"

SCENARIO_ID = "predicted_2026_11_14"
TARGET_DATE = "2026-11-14"
WINDOW_START = parse_hhmm("00:00")
WINDOW_END = parse_hhmm("09:00")
PLANNED_TRIPS = 40
MODES = ("baseline", "efficiency", "fairness")


def load_minute_flow() -> list[tuple[int, float]]:
    with sqlite3.connect(DB_FILE) as connection:
        records = connection.execute(
            """
            SELECT time, bus_passengers
            FROM minute_passenger_flow
            WHERE date = ?
            ORDER BY time
            """,
            (TARGET_DATE,),
        ).fetchall()
    if not records:
        raise ValueError(
            f"{DB_FILE} 中没有 {TARGET_DATE} 的预测客流，请先运行 main.py"
        )
    result = []
    for time_text, passengers in records:
        minute = parse_hhmm(time_text)
        if WINDOW_START <= minute <= WINDOW_END:
            result.append((minute, max(0.0, float(passengers))))
    return result


def round_minute_flow(records: list[tuple[int, float]]) -> list[tuple[int, int]]:
    floors = [
        (minute, passengers, math.floor(passengers))
        for minute, passengers in records
    ]
    target = round(sum(passengers for _, passengers in records))
    remainder = target - sum(item[2] for item in floors)
    ranking = sorted(
        floors,
        key=lambda item: (-(item[1] - item[2]), item[0]),
    )
    add_one = {item[0] for item in ranking[:remainder]}
    return [
        (minute, rounded + (1 if minute in add_one else 0))
        for minute, _, rounded in floors
        if rounded + (1 if minute in add_one else 0) > 0
    ]


def allocate_to_routes(
    passengers: int,
    routes: list[Route],
    minute: int,
) -> list[tuple[Route, int]]:
    raw = [passengers * route.demand_share for route in routes]
    allocated = [math.floor(value) for value in raw]
    remainder = passengers - sum(allocated)
    ranking = sorted(
        range(len(routes)),
        key=lambda index: (
            -(raw[index] - allocated[index]),
            (index - minute) % len(routes),
        ),
    )
    for index in ranking[:remainder]:
        allocated[index] += 1
    return [
        (route, allocated[index])
        for index, route in enumerate(routes)
        if allocated[index] > 0
    ]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_demand_and_groups(
    routes: list[Route],
) -> tuple[list[DemandGroup], list[dict[str, object]], float]:
    raw_flow = load_minute_flow()
    rounded_flow = round_minute_flow(raw_flow)
    demand_rows: list[dict[str, object]] = []
    groups: list[DemandGroup] = []
    for minute, passengers in rounded_flow:
        for route, route_passengers in allocate_to_routes(
            passengers, routes, minute
        ):
            demand_id = f"{SCENARIO_ID}-{minute:04d}-{route.route_id}"
            demand_rows.append(
                {
                    "scenario_id": SCENARIO_ID,
                    "demand_id": demand_id,
                    "route_id": route.route_id,
                    "train_id": f"PRED-{format_hhmm(minute)}",
                    "platform_arrival_min": minute,
                    "platform_arrival": format_hhmm(minute),
                    "passengers": route_passengers,
                    "source_id": "PRED-DB",
                }
            )
            groups.append(
                DemandGroup(
                    scenario_id=SCENARIO_ID,
                    demand_id=demand_id,
                    route_id=route.route_id,
                    train_id=f"PRED-{format_hhmm(minute)}",
                    arrival_min=minute,
                    passengers=route_passengers,
                    source_id="PRED-DB",
                )
            )
    write_csv(DEMAND_FILE, demand_rows)
    return groups, demand_rows, sum(item[1] for item in raw_flow)


def write_bar_svg(path: Path, title: str, values: dict[str, float], suffix: str) -> None:
    width, height = 760, 420
    left, right, top, bottom = 100, 50, 70, 90
    plot_width = width - left - right
    plot_height = height - top - bottom
    max_value = max(values.values()) or 1.0
    colors = {
        "baseline": "#8C8C8C",
        "efficiency": "#1F6F8B",
        "fairness": "#D97706",
    }
    labels = {
        "baseline": "固定班次",
        "efficiency": "效率优先",
        "fairness": "公平优先",
    }
    bar_width = plot_width / (len(values) * 1.7)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        f'<text x="{left}" y="38" font-family="Arial, Microsoft YaHei, sans-serif" '
        f'font-size="21" font-weight="700" fill="#111827">{escape(title)}</text>',
    ]
    for tick in range(6):
        y = top + plot_height - plot_height * tick / 5
        value = max_value * tick / 5
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" '
            f'y2="{y:.1f}" stroke="#E5E7EB" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-family="Arial, Microsoft YaHei, sans-serif" font-size="11" '
            f'fill="#4B5563">{value:.0f}</text>'
        )
    spacing = plot_width / len(values)
    for index, mode in enumerate(MODES):
        x = left + spacing * (index + 0.5) - bar_width / 2
        value = values[mode]
        bar_height = plot_height * value / max_value
        y = top + plot_height - bar_height
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" '
            f'height="{bar_height:.1f}" fill="{colors[mode]}"/>'
        )
        parts.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{y - 7:.1f}" '
            f'text-anchor="middle" font-family="Arial, Microsoft YaHei, sans-serif" '
            f'font-size="12" font-weight="700" fill="#111827">{value:.1f}</text>'
        )
        parts.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{top + plot_height + 28}" '
            f'text-anchor="middle" font-family="Arial, Microsoft YaHei, sans-serif" '
            f'font-size="13" fill="#111827">{escape(labels[mode])}</text>'
        )
    parts.append(
        f'<text x="24" y="{top + plot_height / 2}" transform="rotate(-90 24 '
        f'{top + plot_height / 2})" font-family="Arial, Microsoft YaHei, sans-serif" '
        f'font-size="12" fill="#374151">{escape(suffix)}</text>'
    )
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def write_demand_profile_svg(
    path: Path,
    records: list[tuple[int, float]],
) -> None:
    width, height = 1100, 440
    left, right, top, bottom = 90, 40, 70, 75
    plot_width = width - left - right
    plot_height = height - top - bottom
    max_value = max(value for _, value in records) or 1.0
    points = []
    for minute, value in records:
        x = left + plot_width * (minute - WINDOW_START) / (WINDOW_END - WINDOW_START)
        y = top + plot_height - plot_height * value / max_value
        points.append(f"{x:.1f},{y:.1f}")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        '<text x="40" y="38" font-family="Arial, Microsoft YaHei, sans-serif" '
        'font-size="21" font-weight="700" fill="#111827">'
        "2026-11-14 预测分钟客流</text>",
        f'<polyline points="{" ".join(points)}" fill="none" stroke="#1F6F8B" '
        'stroke-width="2.5"/>',
    ]
    for hour in range(0, 10):
        x = left + plot_width * (hour * 60 - WINDOW_START) / (
            WINDOW_END - WINDOW_START
        )
        parts.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_height}" '
            'stroke="#F3F4F6" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{top + plot_height + 24}" text-anchor="middle" '
            f'font-family="Arial, Microsoft YaHei, sans-serif" font-size="11" '
            f'fill="#4B5563">{hour:02d}:00</text>'
        )
    parts.append(
        f'<text x="{left - 12}" y="{top + 4}" text-anchor="end" '
        f'font-family="Arial, Microsoft YaHei, sans-serif" font-size="11" '
        f'fill="#4B5563">{max_value:.1f}</text>'
    )
    parts.append(
        f'<text x="{left - 12}" y="{top + plot_height + 4}" text-anchor="end" '
        f'font-family="Arial, Microsoft YaHei, sans-serif" font-size="11" '
        f'fill="#4B5563">0</text>'
    )
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    base_routes = load_routes(ROUTE_FILE)
    routes = [
        replace(
            route,
            service_start_min=WINDOW_START,
            service_end_min=WINDOW_END,
            planned_trips=PLANNED_TRIPS,
        )
        for route in base_routes
    ]
    groups, demand_rows, raw_total = write_demand_and_groups(routes)
    results = {
        mode: solve_scenario(routes, groups, SCENARIO_ID, mode)
        for mode in MODES
    }

    summary_rows = []
    for mode in MODES:
        summary = results[mode]["summary"]
        summary_rows.append(
            {
                "scenario_id": SCENARIO_ID,
                "date": TARGET_DATE,
                "mode": mode,
                **summary,
            }
        )
        departure_rows = []
        for route_result in results[mode]["route_results"]:
            for departure in route_result["departures"]:
                departure_rows.append(
                    {
                        "scenario_id": SCENARIO_ID,
                        "mode": mode,
                        "route_id": route_result["route"].route_id,
                        "departure_min": departure,
                        "departure_time": format_hhmm(departure),
                    }
                )
        write_csv(
            RESULT_DIR / f"departures_{mode}.csv",
            departure_rows,
        )
    write_csv(RESULT_DIR / "summary.csv", summary_rows)

    raw_flow = load_minute_flow()
    write_bar_svg(
        FIGURE_DIR / "total_wait.svg",
        "预测客流下的总等待时间",
        {
            mode: float(results[mode]["summary"]["total_wait_passenger_min"])
            for mode in MODES
        },
        "人·分钟",
    )
    write_bar_svg(
        FIGURE_DIR / "max_wait.svg",
        "预测客流下的最长等待时间",
        {
            mode: float(results[mode]["summary"]["max_wait_min"])
            for mode in MODES
        },
        "分钟",
    )
    write_demand_profile_svg(FIGURE_DIR / "minute_demand.svg", raw_flow)

    payload = {
        "meta": {
            "scenario_id": SCENARIO_ID,
            "date": TARGET_DATE,
            "window": f"{format_hhmm(WINDOW_START)}-{format_hhmm(WINDOW_END)}",
            "source": "passenger_flow.db",
            "raw_predicted_passengers_in_window": raw_total,
            "note": "客流预测系数仍为手工设定，线路拆分为均分假设",
        },
        "routes": [serialize_route(route) for route in routes],
        "routes": [serialize_route(route) for route in routes],
        "results": [
            serialize_dispatch_result(results[mode])
            for mode in MODES
        ],
    }
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
    (FRONTEND_DIR / "predicted_demo_payload.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(RESULT_DIR / "normalized_route_demand.csv", demand_rows)

    print(f"Predicted passengers in window: {raw_total:.2f}")
    for row in summary_rows:
        print(
            row["mode"],
            "total_wait=",
            round(float(row["total_wait_passenger_min"]), 2),
            "max_wait=",
            row["max_wait_min"],
            "unserved=",
            row["passengers_unserved"],
        )


if __name__ == "__main__":
    main()
