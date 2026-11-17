from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.model import (  # noqa: E402
    Route,
    format_hhmm,
    load_demand_groups,
    load_routes,
    solve_scenario,
)


INPUT_DIR = ROOT / "data" / "input"
OUTPUT_DIR = ROOT / "outputs"
RESULT_DIR = OUTPUT_DIR / "results"
FIGURE_DIR = OUTPUT_DIR / "figures"
FRONTEND_DIR = OUTPUT_DIR / "frontend"
MODES = ("baseline", "efficiency", "fairness")


def load_scenario_names() -> dict[str, str]:
    names: dict[str, str] = {}
    with (INPUT_DIR / "scenario_profiles.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        for row in csv.DictReader(handle):
            names[row["scenario_id"]] = row["scenario_name"]
    return names


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def route_payload(route: Route) -> dict[str, object]:
    return {
        "route_id": route.route_id,
        "route_name": route.route_name,
        "origin": route.origin,
        "destination": route.destination,
        "capacity": route.capacity,
        "service_start": format_hhmm(route.service_start_min),
        "service_end": format_hhmm(route.service_end_min),
        "planned_trips": route.planned_trips,
        "verification": route.verification,
    }


def create_grouped_bar_svg(
    path: Path,
    title: str,
    scenario_names: dict[str, str],
    values: dict[str, dict[str, float]],
    y_label: str,
) -> None:
    width, height = 960, 520
    left, right, top, bottom = 90, 35, 70, 100
    plot_width = width - left - right
    plot_height = height - top - bottom
    scenarios = list(scenario_names)
    max_value = max(
        values[scenario_id][mode]
        for scenario_id in scenarios
        for mode in MODES
    )
    max_value = max(max_value, 1.0)
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
    group_width = plot_width / len(scenarios)
    bar_width = group_width * 0.18
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        f'<text x="{left}" y="34" font-family="Arial, Microsoft YaHei, sans-serif" '
        f'font-size="22" font-weight="700" fill="#111827">{escape(title)}</text>',
        f'<text x="22" y="{top + plot_height / 2}" transform="rotate(-90 22 '
        f'{top + plot_height / 2})" font-family="Arial, Microsoft YaHei, sans-serif" '
        f'font-size="13" fill="#374151">{escape(y_label)}</text>',
    ]
    for tick in range(6):
        value = max_value * tick / 5
        y = top + plot_height - plot_height * tick / 5
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" '
            f'y2="{y:.1f}" stroke="#E5E7EB" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-family="Arial, Microsoft YaHei, sans-serif" font-size="11" '
            f'fill="#4B5563">{value:.0f}</text>'
        )
    for group_index, scenario_id in enumerate(scenarios):
        group_center = left + group_width * (group_index + 0.5)
        start_x = group_center - bar_width * 1.5 - 8
        for mode_index, mode in enumerate(MODES):
            value = values[scenario_id][mode]
            bar_height = plot_height * value / max_value
            x = start_x + mode_index * (bar_width + 8)
            y = top + plot_height - bar_height
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" '
                f'height="{bar_height:.1f}" fill="{colors[mode]}"/>'
            )
            parts.append(
                f'<text x="{x + bar_width / 2:.1f}" y="{y - 6:.1f}" '
                f'text-anchor="middle" font-family="Arial, Microsoft YaHei, sans-serif" '
                f'font-size="10" fill="#111827">{value:.1f}</text>'
            )
        parts.append(
            f'<text x="{group_center:.1f}" y="{top + plot_height + 28}" '
            f'text-anchor="middle" font-family="Arial, Microsoft YaHei, sans-serif" '
            f'font-size="13" fill="#111827">{escape(scenario_names[scenario_id])}</text>'
        )
    legend_x = left
    for mode in MODES:
        parts.append(
            f'<rect x="{legend_x}" y="{height - 42}" width="14" height="14" '
            f'fill="{colors[mode]}"/>'
        )
        parts.append(
            f'<text x="{legend_x + 20}" y="{height - 31}" '
            f'font-family="Arial, Microsoft YaHei, sans-serif" font-size="12" '
            f'fill="#374151">{escape(labels[mode])}</text>'
        )
        legend_x += 135
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def create_schedule_svg(path: Path, results: dict[tuple[str, str], dict]) -> None:
    scenario_id = "holiday_peak"
    route_id = "K12"
    width, height = 1120, 460
    left, right, top = 150, 40, 75
    lane_height = 95
    plot_width = width - left - right
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        '<text x="40" y="36" font-family="Arial, Microsoft YaHei, sans-serif" '
        'font-size="22" font-weight="700" fill="#111827">'
        "节假日高峰 K12 发车时刻对比</text>",
    ]
    labels = {
        "baseline": "固定班次",
        "efficiency": "效率优先",
        "fairness": "公平优先",
    }
    colors = {
        "baseline": "#8C8C8C",
        "efficiency": "#1F6F8B",
        "fairness": "#D97706",
    }
    start_min, end_min = 18 * 60, 23 * 60
    for mode_index, mode in enumerate(MODES):
        y = top + mode_index * lane_height
        parts.append(
            f'<text x="32" y="{y + 24}" font-family="Arial, Microsoft YaHei, sans-serif" '
            f'font-size="14" fill="#111827">{escape(labels[mode])}</text>'
        )
        parts.append(
            f'<line x1="{left}" y1="{y + 20}" x2="{width - right}" '
            f'y2="{y + 20}" stroke="#D1D5DB" stroke-width="2"/>'
        )
        result = results[(scenario_id, mode)]
        route_result = next(
            item for item in result["route_results"] if item["route"].route_id == route_id
        )
        for departure in route_result["departures"]:
            x = left + plot_width * (departure - start_min) / (end_min - start_min)
            parts.append(
                f'<line x1="{x:.1f}" y1="{y + 6}" x2="{x:.1f}" y2="{y + 34}" '
                f'stroke="{colors[mode]}" stroke-width="2"/>'
            )
    for hour in range(18, 24):
        x = left + plot_width * (hour * 60 - start_min) / (end_min - start_min)
        parts.append(
            f'<line x1="{x:.1f}" y1="{top - 5}" x2="{x:.1f}" '
            f'y2="{top + lane_height * 3 - 45}" stroke="#F3F4F6" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{top + lane_height * 3}" text-anchor="middle" '
            f'font-family="Arial, Microsoft YaHei, sans-serif" font-size="11" '
            f'fill="#4B5563">{hour:02d}:00</text>'
        )
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> None:
    routes = load_routes(INPUT_DIR / "bus_routes.csv")
    demand_groups = load_demand_groups(INPUT_DIR / "demand_groups.csv")
    scenario_names = load_scenario_names()
    results: dict[tuple[str, str], dict] = {}
    summary_rows: list[dict[str, object]] = []
    route_summary_rows: list[dict[str, object]] = []

    for scenario_id, scenario_name in scenario_names.items():
        for mode in MODES:
            result = solve_scenario(routes, demand_groups, scenario_id, mode)
            results[(scenario_id, mode)] = result
            summary = result["summary"]
            summary_rows.append(
                {
                    "scenario_id": scenario_id,
                    "scenario_name": scenario_name,
                    "mode": mode,
                    **summary,
                }
            )
            departure_rows = []
            for route_result in result["route_results"]:
                route = route_result["route"]
                for departure in route_result["departures"]:
                    departure_rows.append(
                        {
                            "scenario_id": scenario_id,
                            "mode": mode,
                            "route_id": route.route_id,
                            "departure_min": departure,
                            "departure_time": format_hhmm(departure),
                        }
                    )
                route_summary_rows.append(
                    {
                        "scenario_id": scenario_id,
                        "mode": mode,
                        "route_id": route.route_id,
                        **route_result["summary"],
                    }
                )
            write_csv(
                RESULT_DIR / f"departures_{scenario_id}_{mode}.csv",
                departure_rows,
            )

    write_csv(RESULT_DIR / "summary.csv", summary_rows)
    write_csv(RESULT_DIR / "route_summary.csv", route_summary_rows)

    total_wait_values = {
        scenario_id: {
            mode: float(results[(scenario_id, mode)]["summary"]["total_wait_passenger_min"])
            for mode in MODES
        }
        for scenario_id in scenario_names
    }
    max_wait_values = {
        scenario_id: {
            mode: float(results[(scenario_id, mode)]["summary"]["max_wait_min"])
            for mode in MODES
        }
        for scenario_id in scenario_names
    }
    create_grouped_bar_svg(
        FIGURE_DIR / "total_wait_by_scenario.svg",
        "各情景总等待时间对比",
        scenario_names,
        total_wait_values,
        "人·分钟",
    )
    create_grouped_bar_svg(
        FIGURE_DIR / "max_wait_by_scenario.svg",
        "各情景最长等待时间对比",
        scenario_names,
        max_wait_values,
        "分钟",
    )
    create_schedule_svg(FIGURE_DIR / "holiday_peak_k12_schedule.svg", results)

    payload = {
        "meta": {
            "project": "高铁枢纽接驳公交调度决策支持系统",
            "scenario_note": "训练与展示数据为公开地图数据加情景假设，待运营数据校准",
            "objective_note": "三种方案使用相同线路和班次配额",
            "generated_at": "2026-11-16",
        },
        "scenarios": [
            {"scenario_id": scenario_id, "scenario_name": name}
            for scenario_id, name in scenario_names.items()
        ],
        "routes": [route_payload(route) for route in routes],
        "results": [],
    }
    for scenario_id, scenario_name in scenario_names.items():
        for mode in MODES:
            result = results[(scenario_id, mode)]
            payload["results"].append(
                {
                    "scenario_id": scenario_id,
                    "scenario_name": scenario_name,
                    "mode": mode,
                    "summary": result["summary"],
                    "route_results": [
                        {
                            "route_id": route_result["route"].route_id,
                            "route_name": route_result["route"].route_name,
                            "summary": route_result["summary"],
                            "departures": [
                                format_hhmm(departure)
                                for departure in route_result["departures"]
                            ],
                        }
                        for route_result in result["route_results"]
                    ],
                }
            )
    FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
    (FRONTEND_DIR / "demo_payload.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote {len(summary_rows)} scenario-mode summaries")
    print(f"Frontend payload: {FRONTEND_DIR / 'demo_payload.json'}")


if __name__ == "__main__":
    main()
