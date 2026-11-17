# 高铁枢纽接驳公交调度决策支持系统

当前版本完成第 2、3 项的核心闭环：数据表、情景生成、双目标调度、指标结果和前端演示数据。SUMO 未安装，本版不包含 SUMO 验证。

## 已有内容

- `data/input/`：线路、情景、列车和客流数据表。
- `data/metadata/`：数据来源与字段字典。
- `data/raw/`：成都东站周边 OSM 公交线路候选数据。
- `src/model.py`：固定班次、效率优先和公平优先的求解与客流仿真。
- `scripts/build_scenarios.py`：根据情景参数生成列车到站和线路需求。
- `scripts/run_experiments.py`：批量求解三个情景并输出结果。
- `outputs/results/`：汇总指标、分线路指标和各方案发车时刻表。
- `outputs/figures/`：总等待时间、最长等待时间和 K12 发车时刻图。
- `outputs/frontend/demo_payload.json`：供现有前端直接读取的演示数据。
- `main.py`：同学完成的分钟级客流生成与 FastAPI 服务。
- `train_data.csv`、`weather_data.csv`：客流预测模块的输入样例。
- `passenger_flow.db`：运行预测后生成的 SQLite 分钟客流数据库。

## 模型口径

三种方案使用相同的线路、容量和班次配额。固定班次采用均匀发车；效率优先最小化总等待时间；公平优先最小化最长等待时间，并以总等待时间作为第二排序目标。

研究时段为 18:00-23:00。候选发车时刻使用 1 分钟网格，约束为：

- 每条线路 40 个班次，与研究时段固定的发车配额一致。
- 相邻班次间隔在 5 到 20 分钟之间。
- 任一相邻班次区间内到达的客流不得超过车辆容量。
- 首班 18:00，末班 23:00。
- 车辆按先到先服务原则装载。

求解使用动态规划。目标一为 `sum(passengers * wait_min)`；目标二为 `max(wait_min)`。目标二相同时继续比较总等待时间。

## 运行

不需要第三方 Python 包。

```powershell
python scripts/build_scenarios.py
python scripts/run_experiments.py
python -m unittest discover -s tests -v
```

如果系统没有 `python` 命令，可使用项目所在环境已有的 Python 解释器执行上述命令。

客流预测模块需要 FastAPI 和 Uvicorn：

```powershell
pip install -r requirements.txt
python main.py --check-input
python main.py --date 2026-11-14
uvicorn main:app --reload
```

将预测数据库接入调度模型并生成最终结果：

```powershell
python scripts/run_predicted_experiment.py
python -m unittest discover -s tests -v
```

启动服务后可访问 `GET /api/dispatch/predicted`。接口只返回前端需要的
`mode`、`summary` 和 `route_results`；`route_results[].timetable` 是 `trips`
聚合后的班次数据。`assignments` 保留在后端，不进入网页响应。

最终答辩口径见 `outputs/predicted_flow/RESULT.md`，前端接入文件为
`outputs/frontend/predicted_demo_payload.json`。

## 当前结果

节假日高峰情景下：

- 固定班次：总等待时间 23521 人·分钟，最长等待时间 7 分钟。
- 效率优先：总等待时间 12260 人·分钟，最长等待时间 6 分钟。
- 公平优先：总等待时间 12341 人·分钟，最长等待时间 5 分钟。

这组结果体现了效率与公平的权衡：公平优先用 81 人·分钟的总等待时间增量，将最长等待时间从 6 分钟降到 5 分钟。

## 数据边界

成都东站站位和 K12 等线路关系来自 OpenStreetMap。列车到站密度、单车容量、发车间隔、步行时间和线路分担率目前均为情景假设，已在 `data/metadata/data_sources.csv` 中标为待校准。答辩中不得表述为已完成实地采集。

真实列车时刻表可按 `data/templates/train_timetable_template.csv` 整理后替换。正式使用前还需核实 K4、K6、K7 在成都东站的上客站点。

同学完成的客流预测模块目前有 31 条列车记录，覆盖 2026-11-14 的 00:06 至 08:10；天气数据覆盖 00:00 至 09:00。它可以用于生成分钟级总客流，但还不能直接覆盖全天调度。接入双目标模型前需要补齐全天列车与天气数据，并将总客流按线路分担率拆分为线路客流。

## 前端接入

现有前端可直接读取 `outputs/frontend/demo_payload.json`。文件包含情景列表、线路信息、三种方案的汇总指标、分线路指标和完整发车时刻。

## SUMO

本机未安装 SUMO，当前没有可运行的 SUMO 工程。第 4 项暂不纳入本次交付。
