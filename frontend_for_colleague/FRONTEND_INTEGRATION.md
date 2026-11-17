# 前端接入说明

## 首选文件

静态展示直接读取 `predicted_demo_payload.json`，不需要读取 CSV 或数据库。

## 顶层结构

```text
meta
routes[]
results[]
```

`meta`：

- `scenario_id`：内部数据标识，只用于追溯数据，不直接显示在页面上。
- `date`：预测日期。
- `window`：调度时段。
- `source`：客流数据来源。
- `raw_predicted_passengers_in_window`：窗口内预测总客流。
- `note`：数据口径提醒。

`routes[]`：

- `route_id`：线路编号。
- `route_name`：线路名称。
- `origin`、`destination`：线路起点和终点。
- `capacity`：车辆容量。
- `service_start`、`service_end`：运营时段。
- `planned_trips`：班次数。
- `verification`：站点或线路核验状态。

`results[]`：

- `mode`：`baseline`、`efficiency`、`fairness`。
- `summary`：该方案总体指标。
- `route_results[]`：分线路指标、发车时刻和按班次聚合的满载率数据。

`route_results[]`：

- `route_id`、`route_name`：线路标识和名称。
- `capacity`：车辆容量。
- `summary`：该线路的服务人数、等待时间、班次数和满载率。
- `departures[]`：仅包含发车时间的时刻列表。
- `timetable[]`：由 `trips` 聚合后的班次数据，每项包含 `trip_no`、`departure_time`、`load`、`capacity`、`load_rate`，适合时刻表和满载率图。

`assignments` 是乘客与班次的后端明细，不下发到前端，也不在网页逐条展示。

## 模式名称

| mode | 页面显示名称 |
| --- | --- |
| `baseline` | 固定班次 |
| `efficiency` | 效率优先 |
| `fairness` | 公平优先 |

## 主要指标

- `passengers_served`：服务人数。
- `passengers_unserved`：未服务人数，当前应为 0。
- `total_wait_passenger_min`：总等待时间，单位为人·分钟。
- `avg_wait_min`：平均等待时间，单位为分钟。
- `max_wait_min`：最长等待时间，单位为分钟。
- `p90_wait_min`：90%分位等待时间，单位为分钟。
- `departures`：总班次数。
- `max_load`：单班最大载客量。
- `mean_load`：平均载客量。
- `peak_load_factor`：最大满载率，0 到 1。

## 页面接入建议

1. 页面初始化时读取 `routes`，生成线路选择器。
2. 读取 `results[].mode`，生成三种方案切换。
3. 选择方案后读取对应的 `summary`，展示总等待、平均等待和最长等待。
4. 从 `route_results[].timetable` 绘制发车时刻表和班次满载率图。
5. 用 `route_results[].summary` 展示各线路差异。
6. 页面不展示 `scenario_id`，也不请求或渲染 `assignments`。

## 动态接口约定

后端已提供：

```text
GET /api/dispatch/predicted
```

接口一次返回全部 `results`，前端通过 `mode` 在本地切换方案。

## 数据说明

当前客流预测系数为手工设定，四线路需求按均分处理。页面应标注为“预测情景结果”，不能标注为“实际调查结果”。
