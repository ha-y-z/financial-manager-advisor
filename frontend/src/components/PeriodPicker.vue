<script setup lang="ts">
import { period, periodLabel, setPeriod, shiftPeriod, type PeriodKind } from '../state'

const kinds: PeriodKind[] = ['month', 'quarter', 'year', 'custom']
</script>

<template>
  <div class="period row">
    <div class="kinds" role="group" aria-label="Period length">
      <button v-for="k in kinds" :key="k" :aria-pressed="period.kind === k" @click="setPeriod(k)">
        {{ k[0].toUpperCase() + k.slice(1) }}
      </button>
    </div>
    <template v-if="period.kind !== 'custom'">
      <button aria-label="Previous period" @click="shiftPeriod(-1)">‹</button>
      <span class="label">{{ periodLabel }}</span>
      <button aria-label="Next period" @click="shiftPeriod(1)">›</button>
    </template>
    <template v-else>
      <label class="row">From <input v-model="period.start" type="date" /></label>
      <label class="row">to <input v-model="period.end" type="date" /></label>
    </template>
  </div>
</template>

<style scoped>
.kinds { display: inline-flex; border: 1px solid var(--rule); border-radius: 6px; overflow: hidden; }
.kinds button { border: none; border-radius: 0; color: var(--ink-2); }
.kinds button[aria-pressed='true'] { background: var(--ink); color: var(--paper); }
.label { min-width: 9.5rem; text-align: center; font-weight: 600; }
</style>
