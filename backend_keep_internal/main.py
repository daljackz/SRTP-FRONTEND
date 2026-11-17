
# -*- coding: utf-8 -*-
"""
高铁枢纽接驳公交分钟级客流生成系统

列车数据：train_data.csv
列车字段：
date, train_no, arrival_time, capacity, is_terminal

天气数据：weather_data.csv
天气字段：
date, time, temperature, precipitation

功能：
1. 根据列车定员计算预计下车人数
2. 区分终到列车和非终到列车
3. 考虑凌晨下车修正系数
4. 考虑气温和降水量天气系数
5. 考虑公交换乘意愿系数
6. 根据步行时间概率分配分钟级公交客流
7. 保存1440条分钟级客流到SQLite数据库
8. 提供FastAPI接口

运行：
pip install fastapi uvicorn

检查数据：
python main.py --check-input

生成指定日期：
python main.py --date 2026-11-16

生成所有日期：
python main.py --generate-all

启动API：
uvicorn main:app --reload
"""

import argparse
import csv
import math
import sqlite3

from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from src.frontend_payload import build_predicted_dispatch_payload


# ============================================================
# 一、文件路径
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

TRAIN_FILE = BASE_DIR / "train_data.csv"
WEATHER_FILE = BASE_DIR / "weather_data.csv"
DB_FILE = BASE_DIR / "passenger_flow.db"


# ============================================================
# 二、模型参数
# ============================================================

# 1. 列车下车系数
K_TERMINAL = 0.80

# 终到列车下车系数
K_NON_TERMINAL = 0.15

# 非终到列车下车系数


# 2. 公交换乘意愿系数
K_BUS = 0.25


# 3. 凌晨下车修正系数
# 列车到站时间处于23:00至次日06:00时生效
K_EARLY_MORNING = 0.70


# 4. 气温分档系数
# 格式：(温度下界, 温度上界, 系数)
# 左闭右开区间

TEMPERATURE_BINS = [
    (None, 0.0, 0.80),
    (0.0, 10.0, 0.90),
    (10.0, 25.0, 1.00),
    (25.0, 32.0, 0.90),
    (32.0, None, 0.80),
]


# 5. 降水量分档系数
# 单位暂按 mm/h
#
# 0单独为一档
# 正降水量按照区间判断

PRECIPITATION_BINS = [
    (0.0, 0.0, 1.00),
    (0.0, 2.5, 0.95),
    (2.5, 10.0, 0.85),
    (10.0, 25.0, 0.70),
    (25.0, None, 0.50),
]


# 6. 步行时间分布参数
#
# ln(W) ~ N(mu, sigma²)
# W单位为分钟

LOGNORMAL_MU = math.log(20.0)

LOGNORMAL_SIGMA = 0.45

# 最大考虑720分钟
MAX_WALK_MINUTES = 720


# ============================================================
# 三、数据字段
# ============================================================

TRAIN_REQUIRED_COLUMNS = {
    "date",
    "train_no",
    "arrival_time",
    "capacity",
    "is_terminal"
}

WEATHER_REQUIRED_COLUMNS = {
    "date",
    "time",
    "temperature",
    "precipitation"
}


# ============================================================
# 四、读取CSV文件
# ============================================================

def read_csv_file(path: Path) -> list[dict[str, str]]:
    """
    读取CSV文件。

    支持：
    1. 逗号分隔
    2. 制表符分隔
    3. 分号分隔
    4. UTF-8 BOM
    """

    if not path.exists():
        raise FileNotFoundError(
            f"找不到数据文件：{path}"
        )

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        sample = f.read(4096)
        f.seek(0)

        try:
            dialect = csv.Sniffer().sniff(
                sample,
                delimiters=",\t;|"
            )
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(
            f,
            dialect=dialect
        )

        if not reader.fieldnames:
            raise ValueError(
                f"{path.name}没有表头"
            )

        reader.fieldnames = [
            str(x).strip().lower()
            for x in reader.fieldnames
        ]

        rows = []

        for raw in reader:

            row = {
                str(k).strip().lower(): (
                    v.strip() if isinstance(v, str) else v
                )
                for k, v in raw.items()
                if k is not None
            }

            rows.append(row)

        return rows


# ============================================================
# 五、日期、时间和数值转换
# ============================================================

def parse_date(value: Any) -> date:

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    s = str(value).strip()

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d"
    ]

    for fmt in formats:

        try:
            return datetime.strptime(
                s[:10],
                fmt
            ).date()

        except ValueError:
            continue

    raise ValueError(
        f"无法识别日期：{value}"
    )


def parse_time(value: Any) -> time:

    if isinstance(value, datetime):
        return value.time()

    if isinstance(value, time):
        return value

    # Excel时间小数形式的兼容处理
    if isinstance(value, (int, float)):

        if 0 <= float(value) < 1:

            total_seconds = round(
                float(value) * 24 * 60 * 60
            )

            total_seconds %= 86400

            h, rem = divmod(
                total_seconds,
                3600
            )

            m, s = divmod(rem, 60)

            return time(h, m, s)

    s = str(value).strip()

    formats = [
        "%H:%M",
        "%H:%M:%S"
    ]

    for fmt in formats:

        try:
            return datetime.strptime(
                s,
                fmt
            ).time()

        except ValueError:
            continue

    raise ValueError(
        f"无法识别时间：{value}"
    )


def parse_number(
    value: Any,
    field_name: str
) -> float:

    if value is None or str(value).strip() == "":
        raise ValueError(
            f"{field_name}不能为空"
        )

    result = float(value)

    if not math.isfinite(result):
        raise ValueError(
            f"{field_name}必须是有限数值"
        )

    return result


# ============================================================
# 六、读取列车数据
# ============================================================

def load_trains() -> list[dict[str, Any]]:

    raw_rows = read_csv_file(TRAIN_FILE)

    if not raw_rows:
        raise ValueError(
            "列车数据为空"
        )

    missing = (
        TRAIN_REQUIRED_COLUMNS
        - set(raw_rows[0].keys())
    )

    if missing:
        raise ValueError(
            f"列车数据缺少字段：{sorted(missing)}"
        )

    trains = []
    errors = []

    for line_no, row in enumerate(
        raw_rows,
        start=2
    ):

        try:

            d = parse_date(row["date"])

            tm = parse_time(
                row["arrival_time"]
            )

            capacity = parse_number(
                row["capacity"],
                "capacity"
            )

            terminal = int(
                float(row["is_terminal"])
            )

            if capacity < 0:
                raise ValueError(
                    "列车定员不能小于0"
                )

            if terminal not in (0, 1):
                raise ValueError(
                    "is_terminal只能为0或1"
                )

            arrival = datetime.combine(
                d,
                tm
            ).replace(
                second=0,
                microsecond=0
            )

            trains.append({
                "date": d,
                "train_no": str(row["train_no"]),
                "arrival": arrival,
                "capacity": capacity,
                "is_terminal": terminal
            })

        except Exception as exc:

            errors.append(
                f"第{line_no}行：{exc}"
            )

    if errors:

        raise ValueError(
            "列车数据存在错误：\n"
            + "\n".join(errors[:20])
        )

    return trains


# ============================================================
# 七、读取天气数据
# ============================================================

def load_weather() -> dict:

    raw_rows = read_csv_file(WEATHER_FILE)

    if not raw_rows:
        raise ValueError(
            "天气数据为空"
        )

    missing = (
        WEATHER_REQUIRED_COLUMNS
        - set(raw_rows[0].keys())
    )

    if missing:

        raise ValueError(
            f"天气数据缺少字段：{sorted(missing)}；"
            "需要date、time、temperature、precipitation"
        )

    weather = {}

    errors = []

    for line_no, row in enumerate(
        raw_rows,
        start=2
    ):

        try:

            d = parse_date(
                row["date"]
            )

            tm = parse_time(
                row["time"]
            )

            temperature = parse_number(
                row["temperature"],
                "temperature"
            )

            precipitation = parse_number(
                row["precipitation"],
                "precipitation"
            )

            if precipitation < 0:
                raise ValueError(
                    "降水量不能小于0"
                )

            # 按日期和小时建立索引
            key = (
                d,
                tm.hour
            )

            if key in weather:

                raise ValueError(
                    f"{d} {tm.hour:02d}:00天气数据重复"
                )

            weather[key] = {
                "temperature": temperature,
                "precipitation": precipitation
            }

        except Exception as exc:

            errors.append(
                f"第{line_no}行：{exc}"
            )

    if errors:

        raise ValueError(
            "天气数据存在错误：\n"
            + "\n".join(errors[:20])
        )

    return weather


# ============================================================
# 八、天气系数计算
# ============================================================

def get_temperature_coefficient(
    temperature: float
) -> float:

    for lower, upper, coefficient in TEMPERATURE_BINS:

        lower_ok = (
            lower is None
            or temperature >= lower
        )

        upper_ok = (
            upper is None
            or temperature < upper
        )

        if lower_ok and upper_ok:

            return coefficient

    raise ValueError(
        f"温度{temperature}℃没有对应的分档"
    )


def get_precipitation_coefficient(
    precipitation: float
) -> float:

    # 无降水
    if precipitation == 0:

        return 1.00

    for lower, upper, coefficient in PRECIPITATION_BINS[1:]:

        lower_ok = precipitation >= lower

        upper_ok = (
            upper is None
            or precipitation < upper
        )

        if lower_ok and upper_ok:

            return coefficient

    raise ValueError(
        f"降水量{precipitation}没有对应的分档"
    )


def get_weather_coefficient(
    weather_row: dict
):

    temperature = weather_row[
        "temperature"
    ]

    precipitation = weather_row[
        "precipitation"
    ]

    temperature_rate = (
        get_temperature_coefficient(
            temperature
        )
    )

    precipitation_rate = (
        get_precipitation_coefficient(
            precipitation
        )
    )

    weather_rate = (
        temperature_rate
        * precipitation_rate
    )

    return (
        temperature_rate,
        precipitation_rate,
        weather_rate
    )


# ============================================================
# 九、步行时间对数正态分布
# ============================================================

def normal_cdf(z: float) -> float:

    return 0.5 * (
        1.0
        + math.erf(
            z / math.sqrt(2.0)
        )
    )


def lognormal_cdf(
    minutes: float
) -> float:

    if minutes <= 0:
        return 0.0

    z = (
        math.log(minutes)
        - LOGNORMAL_MU
    ) / LOGNORMAL_SIGMA

    return normal_cdf(z)


# ============================================================
# 十、参数检查
# ============================================================

def validate_parameters():

    parameters = {
        "K_TERMINAL": K_TERMINAL,
        "K_NON_TERMINAL": K_NON_TERMINAL,
        "K_BUS": K_BUS,
        "K_EARLY_MORNING": K_EARLY_MORNING
    }

    for name, value in parameters.items():

        if not 0 <= value <= 1:

            raise ValueError(
                f"{name}必须在0到1之间"
            )

    if LOGNORMAL_SIGMA <= 0:

        raise ValueError(
            "LOGNORMAL_SIGMA必须大于0"
        )

    if MAX_WALK_MINUTES < 1:

        raise ValueError(
            "MAX_WALK_MINUTES必须大于等于1"
        )


# ============================================================
# 十一、创建SQLite数据库
# ============================================================

def init_db():

    with sqlite3.connect(DB_FILE) as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS minute_passenger_flow (
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                train_capacity REAL NOT NULL DEFAULT 0,
                bus_passengers REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (date, time)
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_flow_date
            ON minute_passenger_flow(date)
        """)

        conn.commit()


# ============================================================
# 十二、生成某一天的分钟级客流
# ============================================================

def generate_one_day(
    target_date: date,
    trains: list,
    weather: dict
):

    validate_parameters()

    trains_on_target_date = [
        x for x in trains
        if x["date"] == target_date
    ]

    if not trains_on_target_date:

        available_dates = sorted({
            x["date"].isoformat()
            for x in trains
        })

        raise ValueError(
            f"列车数据中没有{target_date}的记录。"
            f"当前可用日期：{available_dates}"
        )

    day_start = datetime.combine(
        target_date,
        time(0, 0)
    )

    day_end = day_start + timedelta(days=1)

    # 每分钟列车定员总和
    capacity_by_minute = [
        0.0
    ] * 1440

    # 每分钟预计公交乘客人数
    bus_by_minute = [
        0.0
    ] * 1440

    total_expected_bus = 0.0

    unallocated_tail = 0.0

    weather_factors_used = defaultdict(int)

    for train in trains:

        arrival = train["arrival"]

        # --------------------------------
        # 1. 记录列车到站分钟的定员人数
        # --------------------------------

        if day_start <= arrival < day_end:

            idx = (
                arrival.hour * 60
                + arrival.minute
            )

            capacity_by_minute[idx] += (
                train["capacity"]
            )

        # --------------------------------
        # 2. 判断列车是否影响目标日期
        # --------------------------------

        if arrival >= day_end:
            continue

        if (
            arrival + timedelta(
                minutes=MAX_WALK_MINUTES
            )
            <= day_start
        ):
            continue

        # --------------------------------
        # 3. 匹配列车到站小时的天气
        # --------------------------------

        weather_key = (
            train["date"],
            arrival.hour
        )

        if weather_key not in weather:

            raise ValueError(
                f"天气数据缺失：列车{train['train_no']}，"
                f"到站时间{arrival.strftime('%Y-%m-%d %H:%M')}。"
                f"请检查weather_data.csv中是否有"
                f"{train['date']} {arrival.hour:02d}:00的数据。"
            )

        weather_row = weather[
            weather_key
        ]

        (
            temperature_rate,
            precipitation_rate,
            weather_rate
        ) = get_weather_coefficient(
            weather_row
        )

        # --------------------------------
        # 4. 计算终到或非终到下车系数
        # --------------------------------

        if train["is_terminal"] == 1:

            terminal_rate = K_TERMINAL

        else:

            terminal_rate = K_NON_TERMINAL

        # --------------------------------
        # 5. 判断是否属于凌晨时段
        # --------------------------------

        clock = arrival.time()

        is_early_morning = (
            clock >= time(23, 0)
            or clock < time(6, 0)
        )

        if is_early_morning:

            time_rate = K_EARLY_MORNING

        else:

            time_rate = 1.0

        # --------------------------------
        # 6. 计算预计下车人数
        # --------------------------------

        alighting_estimate = (
            train["capacity"]
            * terminal_rate
            * time_rate
        )

        # --------------------------------
        # 7. 计算预计公交乘客人数
        # --------------------------------

        expected_bus = (
            alighting_estimate
            * K_BUS
            * weather_rate
        )

        total_expected_bus += expected_bus

        weather_factors_used[
            f"气温系数{temperature_rate:.2f}_"
            f"降水系数{precipitation_rate:.2f}"
        ] += 1

        if expected_bus <= 0:
            continue

        # --------------------------------
        # 8. 按步行时间概率分配到每分钟
        # --------------------------------

        for j in range(
            MAX_WALK_MINUTES
        ):

            passenger_arrival = (
                arrival
                + timedelta(minutes=j)
            )

            # 只记录目标日期的数据
            if passenger_arrival < day_start:
                continue

            if passenger_arrival >= day_end:
                break

            probability = (
                lognormal_cdf(j + 1)
                - lognormal_cdf(j)
            )

            if probability > 0:

                idx = (
                    passenger_arrival.hour * 60
                    + passenger_arrival.minute
                )

                bus_by_minute[idx] += (
                    expected_bus
                    * probability
                )

        # --------------------------------
        # 9. 计算超过最大步行时间的尾部人数
        # --------------------------------

        tail_probability = max(
            0.0,
            1.0 - lognormal_cdf(
                MAX_WALK_MINUTES
            )
        )

        if (
            day_start - timedelta(days=1)
            <= arrival < day_end
        ):

            unallocated_tail += (
                expected_bus
                * tail_probability
            )

    # ========================================================
    # 十三、生成1440条数据
    # ========================================================

    rows = []

    for minute in range(1440):

        hh, mm = divmod(
            minute,
            60
        )

        rows.append((
            target_date.isoformat(),
            f"{hh:02d}:{mm:02d}",
            round(
                capacity_by_minute[minute],
                6
            ),
            round(
                bus_by_minute[minute],
                6
            )
        ))

    # ========================================================
    # 十四、写入数据库
    # ========================================================

    init_db()

    with sqlite3.connect(DB_FILE) as conn:

        conn.execute(
            """
            DELETE FROM minute_passenger_flow
            WHERE date = ?
            """,
            (target_date.isoformat(),)
        )

        conn.executemany(
            """
            INSERT INTO minute_passenger_flow
            (date, time, train_capacity, bus_passengers)
            VALUES (?, ?, ?, ?)
            """,
            rows
        )

        conn.commit()

    return {
        "date": target_date.isoformat(),

        "rows_written": len(rows),

        "total_train_capacity": round(
            sum(capacity_by_minute),
            6
        ),

        "total_expected_bus_passengers": round(
            total_expected_bus,
            6
        ),

        "total_bus_passengers_allocated_today": round(
            sum(bus_by_minute),
            6
        ),

        "estimated_unallocated_tail_passengers": round(
            unallocated_tail,
            6
        ),

        "weather_train_count_by_coefficient": dict(
            weather_factors_used
        ),

        "max_walk_minutes": MAX_WALK_MINUTES
    }


# ============================================================
# 十五、生成列车数据中的全部日期
# ============================================================

def generate_all_days():

    trains = load_trains()

    weather = load_weather()

    dates = sorted({
        x["date"]
        for x in trains
    })

    results = []

    for d in dates:

        result = generate_one_day(
            d,
            trains,
            weather
        )

        results.append(result)

        print(result)

    return results


# ============================================================
# 十六、FastAPI接口
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    init_db()

    yield


app = FastAPI(
    title="高铁枢纽接驳公交分钟级客流API",
    description="根据列车定员、下车系数、凌晨系数、天气系数和步行时间分布生成分钟级客流",
    version="3.0.0",
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"]
)


@app.get("/")
def root():

    return {
        "message": "高铁枢纽接驳公交分钟级客流API正在运行",
        "docs": "/docs"
    }


@app.get("/health")
def health():

    return {
        "status": "ok"
    }


@app.get("/api/dates")
def get_dates():

    init_db()

    with sqlite3.connect(DB_FILE) as conn:

        dates = [
            r[0]
            for r in conn.execute(
                """
                SELECT DISTINCT date
                FROM minute_passenger_flow
                ORDER BY date
                """
            ).fetchall()
        ]

    return {
        "dates": dates
    }


@app.get("/api/passenger-flow")
def get_passenger_flow(
    target_date: str = Query(
        ...,
        alias="date"
    )
):

    try:

        parsed = parse_date(
            target_date
        )

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="日期格式应为YYYY-MM-DD"
        )

    init_db()

    with sqlite3.connect(DB_FILE) as conn:

        conn.row_factory = sqlite3.Row

        records = conn.execute(
            """
            SELECT date, time, train_capacity, bus_passengers
            FROM minute_passenger_flow
            WHERE date = ?
            ORDER BY time
            """,
            (parsed.isoformat(),)
        ).fetchall()

    if not records:

        raise HTTPException(
            status_code=404,
            detail="数据库中没有该日期的数据，请先生成客流"
        )

    return {
        "date": parsed.isoformat(),
        "count": len(records),
        "data": [
            dict(r)
            for r in records
        ]
    }


@app.post("/api/generate")
def api_generate(
    target_date: str = Query(
        ...,
        alias="date"
    )
):

    try:

        parsed = parse_date(
            target_date
        )

        trains = load_trains()

        weather = load_weather()

        result = generate_one_day(
            parsed,
            trains,
            weather
        )

        return {
            "message": "生成成功",
            **result
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"生成失败：{exc}"
        )


@app.get("/api/dispatch/predicted")
def get_predicted_dispatch():
    """Return mode, summary and route results for the frontend."""
    try:
        return build_predicted_dispatch_payload()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"调度结果生成失败：{exc}"
        )


# ============================================================
# 十七、命令行运行
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="高铁接驳公交分钟级客流生成系统"
    )

    parser.add_argument(
        "--date",
        type=str,
        help="生成指定日期，例如2026-11-16"
    )

    parser.add_argument(
        "--generate-all",
        action="store_true",
        help="生成所有日期"
    )

    parser.add_argument(
        "--check-input",
        action="store_true",
        help="检查列车和天气数据"
    )

    args = parser.parse_args()

    if args.check_input:

        trains = load_trains()

        weather = load_weather()

        print("\n========== 数据检查结果 ==========")

        print(
            "列车数据文件：",
            TRAIN_FILE
        )

        print(
            "列车记录数量：",
            len(trains)
        )

        print(
            "列车数据日期：",
            sorted({
                x["date"].isoformat()
                for x in trains
            })
        )

        print(
            "天气数据文件：",
            WEATHER_FILE
        )

        print(
            "天气记录数量：",
            len(weather)
        )

        print(
            "天气数据日期：",
            sorted({
                k[0].isoformat()
                for k in weather
            })
        )

        print("\n天气小时记录：")

        for d in sorted({
            k[0]
            for k in weather
        }):

            hours = sorted(
                k[1]
                for k in weather
                if k[0] == d
            )

            print(
                d,
                hours
            )

        print("\n数据检查完成。")

    elif args.generate_all:

        generate_all_days()

    elif args.date:

        target = parse_date(
            args.date
        )

        trains = load_trains()

        weather = load_weather()

        result = generate_one_day(
            target,
            trains,
            weather
        )

        print("\n========== 客流生成结果 ==========")

        print(result)

    else:

        parser.print_help()


if __name__ == "__main__":

    main()
