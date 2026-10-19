<script setup lang="ts">
import { BarChart, LineChart, PieChart, SankeyChart, SunburstChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([CanvasRenderer, BarChart, LineChart, PieChart, SankeyChart, SunburstChart, GridComponent, LegendComponent, TooltipComponent])

// eslint-disable-next-line @typescript-eslint/no-explicit-any
defineProps<{ option: Record<string, any>; height?: string; label: string }>()
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const emit = defineEmits<{ pick: [data: any] }>()
</script>

<template>
  <div class="chart" role="img" :aria-label="label" :style="{ height: height ?? '320px' }">
    <VChart :option="option" autoresize @click="(p: any) => emit('pick', p)" />
  </div>
</template>

<style scoped>
.chart { width: 100%; }
</style>
