<template>
  <div class="dashboard-container" :style="backgroundStyle">
    <div class="overlay"></div> 

    <el-row :gutter="20" class="content-row">
      <el-col :span="7" class="left-panel">
        
        <el-card class="glass-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Setting /></el-icon>
              <span>实时调度环境模拟</span>
            </div>
          </template>
          <el-form :model="simParams" label-width="90px" size="default">
            <el-form-item label="天气情况">
              <el-select v-model="simParams.weather" placeholder="选择天气">
                <el-option label="晴天 (能见度高)" value="sunny" />
                <el-option label="雨天 (道路湿滑)" value="rainy" />
                <el-option label="多云 (气候适宜)" value="cloudy" />
              </el-select>
            </el-form-item>
            <el-form-item label="当前客流">
              <el-slider v-model="simParams.passengerFlow" :max="5000" :step="100" show-input />
            </el-form-item>
            <el-form-item label="时段特征">
              <el-select v-model="simParams.period" placeholder="选择时段">
                <el-option label="工作日 - 早高峰" value="morning_peak" />
                <el-option label="工作日 - 平峰" value="off_peak" />
                <el-option label="节假日 - 枢纽大客流" value="holiday" />
              </el-select>
            </el-form-item>
            <el-form-item label="突发路况">
              <el-select v-model="simParams.blockage" placeholder="线路拥堵情况">
                <el-option label="全线畅通" value="none" />
                <el-option label="天府快线重度拥堵" value="tianfu_block" />
                <el-option label="机场专线施工缓行" value="airport_block" />
              </el-select>
            </el-form-item>
            <el-button type="primary" class="run-btn" @click="generateSchemes" :loading="isCalculating">
              <el-icon style="margin-right: 5px;"><Cpu /></el-icon>
              运行调度优化算法
            </el-button>
          </el-form>
        </el-card>

        <el-card class="glass-card scheme-card" shadow="hover" v-if="schemes.length > 0">
          <template #header>
            <div class="card-header">
              <el-icon><DataLine /></el-icon>
              <span>智能调度方案决策</span>
            </div>
          </template>
          <el-radio-group v-model="selectedSchemeId" style="width: 100%;" @change="applyScheme">
            <el-space direction="vertical" style="width: 100%; align-items: stretch;">
              <el-radio 
                v-for="scheme in schemes" 
                :key="scheme.id" 
                :value="scheme.id" 
                border 
                class="scheme-radio"
                :class="{'is-active': selectedSchemeId === scheme.id}"
              >
                <div class="scheme-details">
                  <strong style="font-size: 15px;">{{ scheme.name }}</strong>
                  <span class="wait-time"><el-icon><Timer /></el-icon> 预测等待: {{ scheme.predictWaitTime }} min</span>
                </div>
                <div class="scheme-subtext">
                  发车间隔: <span class="highlight">{{ scheme.interval }}</span> | 
                  投入车辆: <span class="highlight">{{ scheme.totalBuses }}辆</span>
                </div>
              </el-radio>
            </el-space>
          </el-radio-group>
        </el-card>

      </el-col>

      <el-col :span="17" class="right-panel">
        <el-card class="glass-card map-card" shadow="hover" style="padding: 0; overflow: hidden;">
          <template #header>
            <div class="card-header">
              <el-icon><Location /></el-icon>
              <span>接驳线路真实地理追踪网 (高德GIS)</span>
              <span class="status-dot"></span>
            </div>
          </template>
          <div id="real-map" class="map-container"></div>
        </el-card>

        <el-card class="glass-card bar-card" shadow="hover">
          <div ref="barRef" class="bar-container"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, markRaw, nextTick } from 'vue'
import * as echarts from 'echarts'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Setting, DataLine, Location, Cpu, Timer } from '@element-plus/icons-vue'

// 修复 Vue/Vite 中 Leaflet 默认图标丢失的问题
import iconUrl from 'leaflet/dist/images/marker-icon.png'
import iconShadowUrl from 'leaflet/dist/images/marker-shadow.png'
const DefaultIcon = L.icon({
  iconUrl,
  shadowUrl: iconShadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
})
L.Marker.prototype.options.icon = DefaultIcon

// --- 状态管理 ---
const simParams = reactive({
  weather: 'sunny',
  passengerFlow: 1800,
  period: 'morning_peak',
  blockage: 'none'
})

const isCalculating = ref(false)
const schemes = ref([])
const selectedSchemeId = ref(null)

// --- 动态背景 ---
const backgroundStyle = computed(() => {
  const bgMap = {
    sunny: 'url(public/tianfu_square_sunny.jpg), linear-gradient(to bottom, #4facfe 0%, #00f2fe 100%)',
    rainy: 'url(public/wuhouci_rainy.jpeg), linear-gradient(to bottom, #434343 0%, #000000 100%)',
    cloudy: 'url(public/xipu_shuniu_cloudy.jpg), linear-gradient(to bottom, #8e9eab 0%, #eef2f3 100%)'
  }
  return {
    backgroundImage: bgMap[simParams.weather],
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    transition: 'background-image 1s ease-in-out'
  }
})

// --- ECharts 和 Leaflet 实例 ---
const barRef = ref(null)
let barChart = null
let mapInstance = null
let routeLayers = L.layerGroup() // 管理路线的图层组

// 真实地理坐标设定 (成都)
const locations = {
  hub: { name: '犀浦枢纽', coords: [30.760, 103.968] },
  dest1: { name: '九里校区', coords: [30.697, 104.053] },
  dest2: { name: '天府广场', coords: [30.659, 104.065] },
  dest3: { name: '双流机场', coords: [30.579, 103.947] }
}

const initCharts = () => {
  if (barRef.value) {
    barChart = markRaw(echarts.init(barRef.value))
    updateBarChart()
  }
  initLeafletMap()

  window.addEventListener('resize', () => {
    if (barChart) barChart.resize()
    if (mapInstance) mapInstance.invalidateSize()
  })
}

const initLeafletMap = () => {
  // 视角居中于成都，缩放层级 11
  mapInstance = L.map('real-map', {
    center: [30.680, 104.000],
    zoom: 11,
    zoomControl: false, 
    attributionControl: false
  })

  // 引入公开的高德地图瓦片 (速度快，全中文)
  L.tileLayer('https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}', {
    subdomains: ['1', '2', '3', '4'],
    maxZoom: 19
  }).addTo(mapInstance)

  mapInstance.addLayer(routeLayers)

  // 绘制固定的站点 Marker
  const createMarker = (loc, isHub = false) => {
    const color = isHub ? '#ffeb3b' : '#00f2fe'
    const markerHtml = `
      <div style="background-color: ${color}; width: 14px; height: 14px; border-radius: 50%; box-shadow: 0 0 10px ${color}; border: 2px solid #fff;"></div>
      <div style="color: #fff; font-weight: bold; font-size: 13px; margin-top: 4px; text-shadow: 1px 1px 3px #000; width: 60px; text-align: center; margin-left: -23px;">${loc.name}</div>
    `
    L.marker(loc.coords, {
      icon: L.divIcon({ html: markerHtml, className: 'custom-leaflet-marker' })
    }).addTo(mapInstance)
  }

  createMarker(locations.hub, true)
  createMarker(locations.dest1)
  createMarker(locations.dest2)
  createMarker(locations.dest3)

  drawRoutes()
}

// 绘制/更新 Leaflet 路网
const drawRoutes = () => {
  if (!mapInstance) return
  routeLayers.clearLayers() 

  const isTianfuBlocked = simParams.blockage === 'tianfu_block'
  const isAirportBlocked = simParams.blockage === 'airport_block'

  const drawLine = (start, end, status) => {
    let color = '#4facfe' 
    let className = 'flow-line-normal' 

    if (status === 'blocked_red') {
      color = '#ff4d4f' 
      className = 'flow-line-slow' 
    } else if (status === 'blocked_orange') {
      color = '#faad14' 
      className = 'flow-line-slow' 
    }

    // 底线
    L.polyline([start, end], {
      color: color,
      weight: 4,
      opacity: 0.3
    }).addTo(routeLayers)

    // 上层流光线
    L.polyline([start, end], {
      color: color,
      weight: 3,
      opacity: 0.9,
      className: className 
    }).addTo(routeLayers)
  }

  drawLine(locations.hub.coords, locations.dest1.coords, 'normal')
  drawLine(locations.hub.coords, locations.dest2.coords, isTianfuBlocked ? 'blocked_red' : 'normal')
  drawLine(locations.hub.coords, locations.dest3.coords, isAirportBlocked ? 'blocked_orange' : 'normal')
}

// 更新下方运力柱状图
const updateBarChart = (scheme = null) => {
  if (!barChart) return

  const lineData = scheme ? scheme.lineDetails : [
    { name: '九里校区专线', buses: 6 },
    { name: '天府广场快线', buses: 10 },
    { name: '双流机场专线', buses: 4 }
  ]

  const barOption = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '8%', bottom: '5%', top: '15%', containLabel: true },
    xAxis: {
      type: 'value',
      axisLabel: { color: '#e5eaf3' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
    },
    yAxis: {
      type: 'category',
      data: lineData.map(d => d.name),
      axisLabel: { color: '#fff', fontSize: 13, fontWeight: 'bold' }
    },
    series: [{
      name: '投入运力(辆)',
      type: 'bar',
      barWidth: '35%',
      data: lineData.map(d => d.buses),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#36D1DC' },
          { offset: 1, color: '#5B86E5' }
        ]),
        borderRadius: [0, 8, 8, 0]
      },
      label: { show: true, position: 'right', color: '#fff', formatter: '{c} 辆' }
    }]
  }
  barChart.setOption(barOption)
}

// --- 算法模拟逻辑 ---
const generateSchemes = () => {
  isCalculating.value = true
  
  setTimeout(() => {
    const base = simParams.passengerFlow / 1000
    const tianfuPenalty = simParams.blockage === 'tianfu_block' ? 0.6 : 1
    const airportPenalty = simParams.blockage === 'airport_block' ? 0.7 : 1

    schemes.value = [
      {
        id: 'opt1',
        name: '时间最优方案 (动态规划 DP)',
        predictWaitTime: (4.5 + base * 1.2).toFixed(1),
        interval: '5分钟/班',
        totalBuses: Math.floor(18 + base * 3),
        lineDetails: [
          { name: '九里校区专线', buses: Math.floor(6 + base) },
          { name: '天府广场快线', buses: Math.floor((10 + base * 1.5) * tianfuPenalty) },
          { name: '双流机场专线', buses: Math.floor((4 + base) * airportPenalty) }
        ]
      },
      {
        id: 'opt2',
        name: '能效均衡方案 (贪心启发式)',
        predictWaitTime: (8.2 + base * 1.5).toFixed(1),
        interval: '10分钟/班',
        totalBuses: Math.floor(12 + base * 1.5),
        lineDetails: [
          { name: '九里校区专线', buses: Math.floor(4 + base*0.5) },
          { name: '天府广场快线', buses: Math.floor((6 + base) * tianfuPenalty) },
          { name: '双流机场专线', buses: Math.floor((3 + base*0.5) * airportPenalty) }
        ]
      }
    ]
    
    selectedSchemeId.value = schemes.value[0].id
    applyScheme(selectedSchemeId.value)
    isCalculating.value = false
  }, 1000)
}

const applyScheme = (id) => {
  const scheme = schemes.value.find(s => s.id === id)
  if (scheme) {
    updateBarChart(scheme)
    drawRoutes() 
  }
}

onMounted(() => {
  nextTick(() => {
    initCharts()
  })
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
  background: rgba(10, 15, 30, 0.65);
  z-index: 0;
}

.content-row {
  position: relative;
  z-index: 1;
  height: 100%;
}

.glass-card {
  background: rgba(20, 25, 40, 0.7) !important;
  border: 1px solid rgba(100, 150, 255, 0.2);
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
  background: rgba(0, 0, 0, 0.2);
  margin-bottom: 12px;
  height: auto;
  padding: 12px;
  border-radius: 8px;
}
:deep(.el-radio.is-bordered.is-active) {
  border-color: #4facfe;
  background: rgba(79, 172, 254, 0.15);
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
  height: 40px;
  font-size: 15px;
  font-weight: bold;
  background: linear-gradient(90deg, #00c6fb 0%, #005bea 100%);
  border: none;
}
.run-btn:hover {
  opacity: 0.9;
  box-shadow: 0 0 15px rgba(0, 91, 234, 0.5);
}

.scheme-card { margin-top: 20px; }
.scheme-details {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.wait-time { color: #ffeb3b; font-weight: bold; font-size: 14px; }
.scheme-subtext { font-size: 13px; color: #a1b0c9; }
.highlight { color: #4facfe; font-weight: bold; }

.right-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.map-card { flex: 1; }

.map-container { 
  width: 100%; 
  height: 420px; 
  background-color: transparent !important; 
}

/* 高能黑科技：用 CSS 滤镜将明亮的高德瓦片反相，呈现暗黑科幻风格 */
:deep(.leaflet-tile-pane) {
  filter: invert(90%) hue-rotate(180deg) brightness(85%) contrast(120%);
  transition: filter 0.5s;
}

.bar-card { height: 260px; }
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

/* 路线动画 */
:deep(.flow-line-normal) {
  stroke-dasharray: 10 20;
  animation: dash 1s linear infinite;
}
:deep(.flow-line-slow) {
  stroke-dasharray: 5 30;
  animation: dash 3s linear infinite; 
}
@keyframes dash {
  from { stroke-dashoffset: 30; }
  to { stroke-dashoffset: 0; }
}
</style>