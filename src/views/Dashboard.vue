<template>
  <div class="dashboard-container" :style="backgroundStyle">
    <div class="overlay"></div> 

    <el-row :gutter="20" class="content-row">
      <el-col :span="7" class="left-panel">
        
        <el-card class="glass-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Setting /></el-icon>
              <span>预测调度数据概况</span>
              <span class="status-dot" :class="{ 'is-error': loadError }"></span>
            </div>
          </template>
          <div v-if="isLoading && !meta" class="state-box">
            <el-icon class="is-loading"><Cpu /></el-icon>
            <span>正在读取模型结果...</span>
          </div>

          <div v-else-if="loadError && !meta" class="state-box error-state">
            <span>{{ loadError }}</span>
            <el-button type="primary" @click="loadDispatchData">重新加载</el-button>
          </div>

          <template v-else-if="meta">
            <div class="meta-grid">
              <div class="meta-item">
                <span>预测日期</span>
                <strong>{{ meta.date }}</strong>
              </div>
              <div class="meta-item">
                <span>调度窗口</span>
                <strong>{{ meta.window }}</strong>
              </div>
              <div class="meta-item">
                <span>窗口内预测客流</span>
                <strong>{{ formatDecimal(meta.raw_predicted_passengers_in_window) }} 人</strong>
              </div>
              <div class="meta-item">
                <span>数据来源</span>
                <strong>{{ meta.source }}</strong>
              </div>
            </div>

            <el-alert
              :title="meta.note"
              type="warning"
              :closable="false"
              show-icon
              class="data-note"
            />

            <el-button
              class="refresh-btn"
              :loading="isLoading"
              @click="loadDispatchData"
            >
              刷新模型结果
            </el-button>
          </template>
        </el-card>

        <el-card class="glass-card scheme-card" shadow="hover" v-if="schemes.length">
          <template #header>
            <div class="card-header">
              <el-icon><DataLine /></el-icon>
              <span>调度方案对比</span>
            </div>
          </template>
          <el-radio-group v-model="selectedMode" class="mode-group" @change="applyMode">
            <el-radio
              v-for="scheme in schemes"
              :key="scheme.id"
              :value="scheme.id"
              border
              class="scheme-radio"
            >
              <div class="scheme-details">
                <strong>{{ scheme.name }}</strong>
                <span>{{ scheme.objective }}</span>
              </div>

              <div class="scheme-metrics">
                <div>
                  <span>总等待</span>
                  <strong>{{ formatInteger(scheme.summary.total_wait_passenger_min) }}</strong>
                  <small>人·分钟</small>
                </div>
                <div>
                  <span>最长等待</span>
                  <strong>{{ formatDecimal(scheme.summary.max_wait_min) }}</strong>
                  <small>分钟</small>
                </div>
              </div>

              <div class="scheme-subtext">
                班次 {{ scheme.summary.departures }} ·
                峰值满载率 {{ formatPercent(scheme.summary.peak_load_factor) }}
              </div>
            </el-radio>
          </el-radio-group>
        </el-card>

      </el-col>

      <el-col :span="17" class="right-panel">
        <template v-if="selectedScheme">
          <div class="kpi-grid">
            <div class="kpi-card">
              <span>服务乘客</span>
              <strong>{{ formatInteger(selectedScheme.summary.passengers_served) }}</strong>
              <small>人</small>
            </div>
            <div class="kpi-card">
              <span>总等待时间</span>
              <strong>{{ formatInteger(selectedScheme.summary.total_wait_passenger_min) }}</strong>
              <small>人·分钟</small>
            </div>
            <div class="kpi-card">
              <span>平均等待</span>
              <strong>{{ formatDecimal(selectedScheme.summary.avg_wait_min) }}</strong>
              <small>分钟</small>
            </div>
            <div class="kpi-card">
              <span>最长等待</span>
              <strong>{{ formatDecimal(selectedScheme.summary.max_wait_min) }}</strong>
              <small>分钟</small>
            </div>
            <div class="kpi-card">
              <span>线路 P90 等待最大值</span>
              <strong>{{ formatDecimal(selectedScheme.summary.p90_wait_min) }}</strong>
              <small>分钟</small>
            </div>
            <div class="kpi-card" :class="{ 'warning-card': selectedScheme.summary.passengers_unserved > 0 }">
              <span>未服务乘客</span>
              <strong>{{ formatInteger(selectedScheme.summary.passengers_unserved) }}</strong>
              <small>人</small>
            </div>
          </div>

          <el-row :gutter="20">
            <el-col :xs="24" :xl="12">
              <el-card class="glass-card map-card" shadow="hover" style="padding: 0; overflow: hidden; position: relative;">
                <template #header>
                  <div class="card-header">
                    <el-icon><Location /></el-icon>
                    <span>成都东站接驳路网示意</span>
                  </div>
                </template>
                <div class="map-legend">
                  <div class="legend-title">开题路网底图</div>
                  <div class="legend-item"><div class="color-line" style="background: #F56C6C;"></div><span>47路</span></div>
                  <div class="legend-item"><div class="color-line" style="background: #409EFF;"></div><span>50路</span></div>
                  <div class="legend-item"><div class="color-line" style="background: #67C23A;"></div><span>135路</span></div>
                </div>
                <div id="real-map" class="map-container"></div>
              </el-card>
            </el-col>
            <el-col :xs="24" :xl="12">
              <el-card class="glass-card chart-card" shadow="hover">
                <template #header>
                  <div class="card-header">
                    <el-icon><DataLine /></el-icon>
                    <span>分线路等待时间</span>
                  </div>
                </template>
                <div ref="metricChartRef" class="chart-container"></div>
              </el-card>
            </el-col>
          </el-row>

          <el-card class="glass-card table-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <el-icon><Tickets /></el-icon>
                <span>分线路指标</span>
              </div>
            </template>
            <el-table :data="selectedScheme.routeResults" row-key="route_id" class="dark-table" style="width: 100%;">
              <el-table-column type="expand">
                <template #default="{ row }">
                  <div class="trip-detail">
                    <div v-for="trip in row.timetable" :key="trip.trip_no" class="trip-chip">
                      <strong>{{ trip.departure_time }}</strong>
                      <span>{{ trip.load }}/{{ trip.capacity }} 人</span>
                      <el-progress :percentage="Math.round(trip.load_rate * 100)" :stroke-width="5" :show-text="false" :color="loadRateColor(trip.load_rate)" />
                      <small>{{ formatPercent(trip.load_rate) }}</small>
                    </div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="route_name" label="线路" min-width="150" />
              <el-table-column prop="capacity" label="容量" width="70" />
              <el-table-column label="服务时段" width="120"><template #default="{ row }">{{ row.service_start }}-{{ row.service_end }}</template></el-table-column>
              <el-table-column label="服务人数" width="100"><template #default="{ row }">{{ formatInteger(row.summary.passengers_served) }}</template></el-table-column>
              <el-table-column label="总等待" width="100"><template #default="{ row }">{{ formatInteger(row.summary.total_wait_passenger_min) }}</template></el-table-column>
              <el-table-column label="平均等待" width="100"><template #default="{ row }">{{ formatDecimal(row.summary.avg_wait_min) }} 分</template></el-table-column>
              <el-table-column label="最长等待" width="100"><template #default="{ row }">{{ formatDecimal(row.summary.max_wait_min) }} 分</template></el-table-column>
              <el-table-column label="P90" width="80"><template #default="{ row }">{{ formatDecimal(row.summary.p90_wait_min) }} 分</template></el-table-column>
              <el-table-column label="班次" width="70"><template #default="{ row }">{{ row.summary.departures }}</template></el-table-column>
              <el-table-column label="峰值满载率" width="110"><template #default="{ row }">{{ formatPercent(row.summary.peak_load_factor) }}</template></el-table-column>
            </el-table>
          </el-card>

          <el-card class="glass-card schedule-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <el-icon><Clock /></el-icon>
                <span>发车时刻与班次满载率</span>
              </div>
            </template>
            <div ref="scheduleChartRef" class="schedule-chart"></div>
          </el-card>
        </template>
        <el-card v-else class="glass-card empty-card" shadow="hover">
          <el-empty description="等待调度模型结果" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Clock, Cpu, DataLine, Location, Setting, Tickets } from '@element-plus/icons-vue'
import { fetchPredictedDispatch } from '../api/dispatch.js'

// 引入你准备好的公交路线数据
import { line47Path, line50Path, line135Path } from '../data/busRoutes.js'

import iconUrl from 'leaflet/dist/images/marker-icon.png'
import iconShadowUrl from 'leaflet/dist/images/marker-shadow.png'
const DefaultIcon = L.icon({
  iconUrl,
  shadowUrl: iconShadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
})
L.Marker.prototype.options.icon = DefaultIcon

const MODE_META = {
  baseline: {
    name: '固定班次',
    objective: '统一间隔发车，作为效率与公平的对照基准',
  },
  efficiency: {
    name: '效率优先',
    objective: '最小化所有乘客的总等待时间',
  },
  fairness: {
    name: '公平优先',
    objective: '优先压低单条线路的最长等待时间',
  },
}

const dispatchData = ref(null)
const meta = computed(() => dispatchData.value?.meta || null)
const loadError = ref('')
const selectedMode = ref('')
const metricChartRef = ref(null)
const scheduleChartRef = ref(null)
let metricChart = null
let scheduleChart = null
let abortController = null

const isLoading = ref(false)
const schemes = computed(() => {
  if (!dispatchData.value?.results) return []
  return dispatchData.value.results.map((result) => ({
    id: result.mode,
    ...(MODE_META[result.mode] || { name: result.mode, objective: '' }),
    summary: result.summary,
    routeResults: result.route_results.map((routeResult) => ({
      ...routeResult,
      timetable: routeResult.timetable || [],
    })),
  }))
})

const selectedScheme = computed(
  () => schemes.value.find((scheme) => scheme.id === selectedMode.value) || null,
)

const backgroundStyle = {
  backgroundImage: 'url(/tianfu_square_sunny.jpg), linear-gradient(to bottom, #1a2a6c, #b21f1f, #fdbb2d)',
  backgroundSize: 'cover',
  backgroundPosition: 'center',
}

let mapInstance = null
let routeLayers = L.layerGroup()

const formatInteger = (value) => Number(value || 0).toLocaleString('zh-CN', {
  maximumFractionDigits: 0,
})

const formatDecimal = (value, digits = 1) => Number(value || 0).toFixed(digits)

const formatPercent = (value) => `${(Number(value || 0) * 100).toFixed(1)}%`

const loadRateColor = (value) => {
  if (value >= 0.9) return '#ff4d4f'
  if (value >= 0.7) return '#faad14'
  return '#52c41a'
}

const locations = {
  hub: { name: '成都东站', coords: [30.628, 104.140] },
  dest47: { name: '九眼桥', coords: [30.643, 104.086] },
  dest50: { name: '火车南站', coords: [30.608, 104.066] },
  dest135: { name: '川师大', coords: [30.612, 104.108] }
}


const initLeafletMap = () => {
  if (mapInstance || !document.getElementById('real-map')) return
  mapInstance = L.map('real-map', {
    center: [30.620, 104.115],
    zoom: 13,
    zoomControl: false, 
    attributionControl: false
  })

  L.tileLayer('https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}', {
    subdomains: ['1', '2', '3', '4'],
    maxZoom: 19
  }).addTo(mapInstance)

  mapInstance.addLayer(routeLayers)

  const createMarker = (loc, isHub = false, color = '#00f2fe') => {
    const markerHtml = `
      <div style="background-color: ${color}; width: 14px; height: 14px; border-radius: 50%; box-shadow: 0 0 10px ${color}; border: 2px solid #fff;"></div>
      <div style="color: #fff; font-weight: bold; font-size: 13px; margin-top: 4px; text-shadow: 1px 1px 3px #000; width: 100px; text-align: center; margin-left: -43px;">${loc.name}</div>
    `
    L.marker(loc.coords, {
      icon: L.divIcon({ html: markerHtml, className: 'custom-leaflet-marker' })
    }).addTo(mapInstance)
  }

  // 为终点加上对应的线路颜色以供辨认
  createMarker(locations.hub, true, '#ffeb3b') // 黄色东站枢纽
  createMarker(locations.dest47, false, '#F56C6C') // 红色
  createMarker(locations.dest50, false, '#409EFF') // 蓝色
  createMarker(locations.dest135, false, '#67C23A') // 绿色

  drawRoutes()
}

// 🌟 核心修改：移除动画，改用带颜色的普通线
const drawRoutes = () => {
  if (!mapInstance) return
  routeLayers.clearLayers() 

  L.polyline(line47Path, { color: '#F56C6C', weight: 5, opacity: 0.85 }).addTo(routeLayers)
  L.polyline(line50Path, { color: '#409EFF', weight: 5, opacity: 0.85 }).addTo(routeLayers)
  L.polyline(line135Path, { color: '#67C23A', weight: 5, opacity: 0.85 }).addTo(routeLayers)
}

const updateMetricChart = () => {
  if (!metricChart || !selectedScheme.value) return
  const routeResults = selectedScheme.value.routeResults

  metricChart.setOption({
    color: ['#4facfe', '#ffd666', '#b37feb'],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: 'rgba(79, 172, 254, 0.5)',
      textStyle: { color: '#fff' },
    },
    legend: { top: 0, textStyle: { color: '#dbeafe' } },
    grid: { left: '3%', right: '4%', bottom: '8%', top: '18%', containLabel: true },
    xAxis: {
      type: 'category',
      data: routeResults.map((item) => item.route_name),
      axisLabel: { color: '#e5eaf3', interval: 0 },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.25)' } },
    },
    yAxis: {
      type: 'value',
      name: '分钟',
      nameTextStyle: { color: '#a1b0c9' },
      axisLabel: { color: '#a1b0c9' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
    },
    series: [
      { name: '平均等待', type: 'bar', barMaxWidth: 24, data: routeResults.map((item) => item.summary.avg_wait_min) },
      { name: '最长等待', type: 'bar', barMaxWidth: 24, data: routeResults.map((item) => item.summary.max_wait_min) },
      { name: 'P90等待', type: 'line', symbolSize: 8, data: routeResults.map((item) => item.summary.p90_wait_min) },
    ],
  }, true)
}

const updateScheduleChart = () => {
  if (!scheduleChart || !selectedScheme.value) return
  const routeResults = selectedScheme.value.routeResults
  const maxTrips = Math.max(...routeResults.map((item) => item.timetable.length), 0)

  const points = routeResults.flatMap((routeResult, routeIndex) =>
    routeResult.timetable.map((trip) => ({
      value: [
        trip.trip_no - 1,
        routeIndex,
        trip.load_rate,
        trip.load,
        trip.capacity,
        trip.departure_time,
        routeResult.route_name,
      ],
    })),
  )

  scheduleChart.setOption({
    tooltip: {
      formatter: (params) => {
        const [, , , load, capacity, departureTime, routeName] = params.value
        return [
          `<strong>${routeName}</strong>`,
          `发车：${departureTime}`,
          `载客：${load} / ${capacity} 人`,
          `满载率：${formatPercent(params.value[2])}`,
        ].join('<br/>')
      },
      backgroundColor: 'rgba(15, 23, 42, 0.96)',
      borderColor: 'rgba(79, 172, 254, 0.5)',
      textStyle: { color: '#fff' },
    },
    grid: { left: '4%', right: '5%', bottom: '15%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: Array.from({ length: maxTrips }, (_, index) => index + 1),
      name: '班次序号',
      nameTextStyle: { color: '#a1b0c9' },
      axisLabel: { color: '#a1b0c9', interval: Math.max(Math.floor(maxTrips / 10) - 1, 0) },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.25)' } },
      splitLine: { show: true, lineStyle: { color: 'rgba(255,255,255,0.04)' } },
    },
    yAxis: {
      type: 'category',
      data: routeResults.map((item) => item.route_name),
      axisLabel: { color: '#e5eaf3' },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.25)' } },
    },
    visualMap: {
      min: 0, max: 1, dimension: 2, orient: 'horizontal', left: 'center', bottom: 0,
      text: ['高满载', '低满载'],
      textStyle: { color: '#a1b0c9' },
      inRange: { color: ['#237804', '#52c41a', '#faad14', '#ff4d4f'] },
    },
    series: [{
      name: '班次满载率',
      type: 'scatter',
      data: points,
      symbolSize: (value) => 8 + Number(value[2] || 0) * 14,
      emphasis: { scale: 1.3 },
    }],
  }, true)
}

const updateCharts = () => {
  updateMetricChart()
  updateScheduleChart()
}

const applyMode = (mode) => {
  selectedMode.value = mode
  nextTick(updateCharts)
}

const loadDispatchData = async () => {
  if (abortController) abortController.abort()
  abortController = new AbortController()
  isLoading.value = true
  loadError.value = ''

  try {
    const data = await fetchPredictedDispatch(abortController.signal)
    dispatchData.value = data
    selectedMode.value = (data.results || []).some((item) => item.mode === 'efficiency')
      ? 'efficiency'
      : data.results?.[0]?.mode || ''
    await nextTick()
    if (!metricChart && metricChartRef.value) {
      metricChart = markRaw(echarts.init(metricChartRef.value))
    }
    if (!scheduleChart && scheduleChartRef.value) {
      scheduleChart = markRaw(echarts.init(scheduleChartRef.value))
    }
    if (!mapInstance) initLeafletMap()
    updateCharts()
  } catch (error) {
    if (error.name !== 'AbortError') loadError.value = error.message || '无法获取调度结果'
  } finally {
    isLoading.value = false
  }
}

const handleResize = () => {
  metricChart?.resize()
  scheduleChart?.resize()
  mapInstance?.invalidateSize()
}

onMounted(async () => {
  await nextTick()
  window.addEventListener('resize', handleResize)
  await loadDispatchData()
})

onBeforeUnmount(() => {
  abortController?.abort()
  window.removeEventListener('resize', handleResize)
  metricChart?.dispose()
  scheduleChart?.dispose()
  mapInstance?.remove()
})
</script>

<style scoped>
.dashboard-container {
  position: relative;
  min-height: calc(100vh - 60px);
  padding: 20px;
  box-sizing: border-box;
}

.overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(10, 15, 30, 0.7);
  z-index: 0;
}

.content-row {
  position: relative;
  z-index: 1;
  height: 100%;
}

.glass-card {
  background: rgba(20, 25, 40, 0.75) !important;
  border: 1px solid rgba(100, 150, 255, 0.25);
  backdrop-filter: blur(12px);
  color: white;
  border-radius: 12px;
}

:deep(.el-card__header) {
  border-bottom: 1px solid rgba(100, 150, 255, 0.2);
  padding: 12px 20px;
}
:deep(.el-card__body) {
  padding: 15px;
}
:deep(.el-form-item__label) { color: #a1b0c9; font-weight: bold; }
:deep(.el-radio.is-bordered) {
  border-color: rgba(100, 150, 255, 0.3);
  background: rgba(0, 0, 0, 0.3);
  margin-bottom: 15px;
  height: auto;
  padding: 15px;
  border-radius: 8px;
}
:deep(.el-radio.is-bordered.is-checked) {
  border-color: #4facfe;
  background: rgba(79, 172, 254, 0.15);
  box-shadow: inset 0 0 10px rgba(79, 172, 254, 0.2);
}
:deep(.el-radio__label) { color: white !important; width: 100%; display: block; }

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: bold;
  color: #e5eaf3;
  letter-spacing: 1px;
}

.run-btn {
  width: 100%;
  height: 42px;
  font-size: 16px;
  font-weight: bold;
  background: linear-gradient(90deg, #00c6fb 0%, #005bea 100%);
  border: none;
  border-radius: 8px;
}
.run-btn:hover {
  opacity: 0.9;
  box-shadow: 0 0 15px rgba(0, 91, 234, 0.5);
}

.scheme-card { margin-top: 20px; }
.scheme-details {
  margin-bottom: 10px;
}

.metrics-container {
  display: flex;
  justify-content: space-between;
  background: rgba(255,255,255,0.05);
  padding: 10px;
  border-radius: 6px;
  margin-bottom: 10px;
}
.metric-item { display: flex; flex-direction: column; }
.metric-label { font-size: 12px; color: #a1b0c9; margin-bottom: 4px; }
.metric-value { font-size: 18px; font-weight: bold; }
.efficiency { color: #52c41a; }
.fairness { color: #ffeb3b; }

.scheme-subtext { font-size: 13px; color: #a1b0c9; margin-top: 5px;}
.highlight { color: #4facfe; font-weight: bold; }

.right-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.map-card { flex: 1; }

.map-container { 
  width: 100%; 
  height: 400px;
  background-color: transparent !important; 
}

/* 🌟 新增：地图图例的悬浮样式 */
.map-legend {
  position: absolute;
  bottom: 20px;
  left: 20px;
  background: rgba(20, 25, 40, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(8px);
  padding: 12px 15px;
  border-radius: 8px;
  z-index: 1000; /* 确保悬浮在地图上方 */
  pointer-events: none;
}
.legend-title {
  font-size: 13px;
  font-weight: bold;
  color: #fff;
  margin-bottom: 8px;
  border-bottom: 1px solid rgba(255,255,255,0.2);
  padding-bottom: 4px;
}
.legend-item {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
  font-size: 12px;
  color: #e5eaf3;
}
.color-line {
  width: 20px;
  height: 4px;
  margin-right: 8px;
  border-radius: 2px;
}
.color-line.dashed {
  background: transparent !important;
  border-bottom: 2px dashed #fff;
}
.blocked-tag {
  margin-left: 8px;
  background: #ff4d4f;
  color: white;
  padding: 1px 4px;
  border-radius: 4px;
  font-size: 10px;
}

/* CSS 滤镜高德暗黑地图 */
:deep(.leaflet-tile-pane) {
  filter: invert(90%) hue-rotate(180deg) brightness(85%) contrast(120%);
  transition: filter 0.5s;
}

.bar-card { height: 280px; }
.bar-container { width: 100%; height: 100%; }

.status-dot {
  width: 8px;
  height: 8px;
  background-color: #52c41a;
  border-radius: 50%;
  margin-left: auto;
  box-shadow: 0 0 8px #52c41a;
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.4; }
  100% { opacity: 1; }
}

.left-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.mode-group {
  width: 100%;
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.meta-item {
  min-height: 62px;
  padding: 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.05);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.meta-item span {
  color: #a1b0c9;
  font-size: 12px;
}

.meta-item strong {
  color: #e5eaf3;
  font-size: 14px;
  word-break: break-word;
}

.data-note {
  margin-top: 12px;
}

.refresh-btn {
  width: 100%;
  margin-top: 12px;
}

.state-box {
  min-height: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  color: #a1b0c9;
}

.error-state {
  color: #ffb4b4;
  text-align: center;
}

.scheme-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.scheme-details strong {
  font-size: 15px;
}

.scheme-details span {
  color: #a1b0c9;
  font-size: 12px;
  line-height: 1.5;
}

.scheme-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.05);
}

.scheme-metrics > div {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: baseline;
}

.scheme-metrics span {
  color: #a1b0c9;
  font-size: 12px;
}

.scheme-metrics strong {
  color: #4facfe;
  font-size: 18px;
}

.scheme-metrics small {
  grid-column: 1 / -1;
  color: #7f8da8;
  font-size: 11px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}

.kpi-card {
  padding: 14px;
  border-radius: 12px;
  background: rgba(20, 25, 40, 0.78);
  border: 1px solid rgba(100, 150, 255, 0.25);
  backdrop-filter: blur(10px);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.kpi-card span { color: #a1b0c9; font-size: 12px; }
.kpi-card strong { color: #fff; font-size: 22px; }
.kpi-card small { color: #7f8da8; }
.kpi-card.warning-card { border-color: rgba(255, 77, 79, 0.65); }

.map-card,
.chart-card {
  height: 100%;
}

.chart-container {
  width: 100%;
  height: 400px;
}

.table-card,
.schedule-card {
  width: 100%;
}

.dark-table {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(79, 172, 254, 0.08);
  --el-table-row-hover-bg-color: rgba(79, 172, 254, 0.1);
  --el-table-border-color: rgba(255, 255, 255, 0.08);
  --el-table-text-color: #e5eaf3;
  --el-table-header-text-color: #a1b0c9;
}

.dark-table :deep(.el-table__expanded-cell) {
  background: rgba(0, 0, 0, 0.16) !important;
}

.trip-detail {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
  padding: 8px;
}

.trip-chip {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 6px;
  padding: 7px 8px;
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.05);
}

.trip-chip strong {
  color: #4facfe;
  font-size: 12px;
}

.trip-chip span,
.trip-chip small {
  color: #a1b0c9;
  font-size: 11px;
}

.trip-chip :deep(.el-progress) {
  grid-column: 1 / -1;
}

.schedule-chart {
  width: 100%;
  height: 360px;
}

.empty-card {
  min-height: 420px;
}

@media (max-width: 1400px) {
  .kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (max-width: 760px) {
  .kpi-grid, .meta-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

/* 删除了之前的流光动画样式 */
</style>
