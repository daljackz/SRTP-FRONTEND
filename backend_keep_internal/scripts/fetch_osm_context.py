from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path


OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def build_query(lat: float, lon: float, radius_m: int) -> str:
    return f"""
[out:json][timeout:120];
(
  node(around:{radius_m},{lat},{lon})["highway"="bus_stop"];
  relation(around:{radius_m},{lat},{lon})["route"="bus"];
  way(around:{max(300, radius_m // 2)},{lat},{lon})["highway"];
);
out body;
>;
out skel qt;
""".strip()


def fetch(query: str) -> dict:
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    request = urllib.request.Request(
        OVERPASS_URL,
        data=body,
        headers={"User-Agent": "srtp-chengdu-east-data/1.0"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch bus stops, bus route relations and roads near a station."
    )
    parser.add_argument("--lat", type=float, default=30.63114)
    parser.add_argument("--lon", type=float, default=104.13889)
    parser.add_argument("--radius", type=int, default=1200)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/osm_chengdu_east_context.json"),
    )
    args = parser.parse_args()
    payload = fetch(build_query(args.lat, args.lon, args.radius))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(payload.get('elements', []))} OSM elements to {args.output}")


if __name__ == "__main__":
    main()
