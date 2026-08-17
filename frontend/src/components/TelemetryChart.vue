<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { LineChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import type { TelemetryPoint } from '@/types'

echarts.use([GridComponent, TooltipComponent, LineChart, CanvasRenderer])
const props = defineProps<{ points: TelemetryPoint[] }>()
const target = ref<HTMLDivElement>()
let chart: echarts.ECharts | undefined

function draw() {
  if (!target.value) return
  chart ??= echarts.init(target.value)
  chart.setOption({
    animationDuration: 700,
    backgroundColor: 'transparent',
    grid: { left: 10, right: 12, top: 18, bottom: 10, containLabel: true },
    tooltip: {
      trigger: 'axis', backgroundColor: '#ffffff', borderColor: '#cbd8e3',
      extraCssText: 'box-shadow:0 6px 20px rgba(33,66,99,.12);border-radius:6px;',
      textStyle: { color: '#263b50', fontFamily: 'Noto Sans SC', fontSize: 11 },
    },
    xAxis: {
      type: 'category', boundaryGap: false,
      data: props.points.map((point) => new Date(point.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })),
      axisLabel: { color: '#718399', fontFamily: 'IBM Plex Mono', fontSize: 9 }, axisLine: { lineStyle: { color: '#d7e1ea' } },
    },
    yAxis: [
      { type: 'value', axisLabel: { color: '#718399', fontSize: 9 }, splitLine: { lineStyle: { color: '#e7edf3' } } },
      { type: 'value', axisLabel: { show: false }, splitLine: { show: false } },
    ],
    series: [
      {
        name: '油温 °C', type: 'line', smooth: 0.25, showSymbol: false,
        data: props.points.map((point) => point.oil_temperature_c),
        lineStyle: { color: '#1769aa', width: 2 }, areaStyle: { color: 'rgba(23,105,170,.08)' },
      },
      {
        name: '伺服负载 %', type: 'line', yAxisIndex: 1, smooth: 0.25, showSymbol: false,
        data: props.points.map((point) => point.servo_load_pct),
        lineStyle: { color: '#33a3b8', width: 1.7 }, areaStyle: { color: 'rgba(51,163,184,.05)' },
      },
    ],
  })
}

function resize() { chart?.resize() }
onMounted(() => { draw(); window.addEventListener('resize', resize) })
watch(() => props.points, draw, { deep: true })
onBeforeUnmount(() => { window.removeEventListener('resize', resize); chart?.dispose() })
</script>

<template><div ref="target" class="telemetry-chart" aria-label="设备遥测趋势图"></div></template>
