<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { api, type Holding, type SnapshotDetail, type SnapshotSummary } from '../api'
import Chart from '../components/Chart.vue'
import { bump, esc, eur, eur0, fmtDate, version } from '../state'
import { baseOption, tokens } from '../theme'

const snapshots = ref<SnapshotSummary[]>([])
const selected = ref<number | null>(null)
const snap = ref<SnapshotDetail | null>(null)
const filter = ref<{ label: string; isins: string[] } | null>(null)
const tagDraft = reactive<Record<string, string>>({})
const error = ref('')
const tagNames = ref<string[]>([])

watch(version, async () => {
  ;[snapshots.value, tagNames.value] = await Promise.all([api.get<SnapshotSummary[]>('/portfolio/snapshots'), api.get<string[]>('/tags')])
  if (!snapshots.value.some((s) => s.id === selected.value)) selected.value = snapshots.value.at(-1)?.id ?? null
  else loadSnap()
}, { immediate: true })
watch(selected, () => { filter.value = null; loadSnap() })

async function loadSnap() {
  snap.value = selected.value == null ? null : await api.get<SnapshotDetail>(`/portfolio/snapshots/${selected.value}`)
  for (const h of snap.value?.holdings ?? []) tagDraft[h.isin] = h.tags.join(', ')
}

async function saveTags(h: Holding) {
  const names = (tagDraft[h.isin] ?? '').split(',').map((s) => s.trim()).filter(Boolean)
  try { await api.put(`/holdings/${h.isin}/tags`, names); error.value = ''; bump() } catch (e) { error.value = (e as Error).message }
}

// Holdings slices: largest 7 keep their hue, the rest fold into "Other" (never a 9th generated hue)
const holdingSlices = computed(() => {
  const hs = snap.value?.holdings ?? []
  const main = hs.slice(0, hs.length > 8 ? 7 : 8)
  const rest = hs.slice(main.length)
  const slices = main.map((h) => ({ name: h.name, value: h.value, isins: [h.isin], holdings: [h] }))
  if (rest.length) slices.push({ name: `Other (${rest.length})`, value: rest.reduce((s, h) => s + h.value, 0), isins: rest.map((h) => h.isin), holdings: rest })
  return slices
})

const share = (v: number) => (snap.value?.total ? `${((v / snap.value.total) * 100).toFixed(1)} %` : '')

function pieOption(slices: { name: string; value: number; isins: string[] }[], byIsinColor: boolean) {
  const t = tokens()
  const holdings = snap.value?.holdings ?? []
  return {
    ...baseOption(t),
    tooltip: {
      ...baseOption(t).tooltip,
      formatter: (p: { name: string; value: number; data: { isins: string[] } }) => {
        const members = holdings.filter((h) => p.data.isins.includes(h.isin))
        const top = members.slice(0, 3).map((h) => `<li>${esc(h.name)} <span>${eur(h.value)}</span></li>`).join('')
        return `<div class="tip"><b>${esc(p.name)}</b><div class="tip-sum">${eur(p.value)}</div>
          <div class="tip-count">${share(p.value)} of the Portfolio, ${members.length} Holding${members.length === 1 ? '' : 's'}</div>
          ${members.length > 1 ? `<ol>${top}</ol>` : ''}</div>`
      },
    },
    series: [{
      type: 'pie', radius: ['44%', '78%'], center: ['50%', '50%'], padAngle: 1,
      itemStyle: { borderColor: t.paper, borderWidth: 2, borderRadius: 3 },
      label: { color: t.ink2, fontFamily: t.font, formatter: (p: { name: string; percent: number }) => `${p.name.length > 22 ? p.name.slice(0, 21) + '…' : p.name}\n${Math.round(p.percent)} %`, fontSize: 11 },
      labelLine: { lineStyle: { color: t.rule } },
      data: slices.map((s, i) => ({ ...s, itemStyle: { color: s.name === 'Untagged' || s.name.startsWith('Other (') || (!byIsinColor && i >= 8) ? t.neutral : t.series[i] } })),
    }],
  }
}
const holdingPie = computed(() => pieOption(holdingSlices.value, true))
const tagPie = computed(() => pieOption(snap.value?.by_tag.slice(0, 8) ?? [], false))
const multiTagged = computed(() => (snap.value?.holdings ?? []).some((h) => h.tags.length > 1))

const lineOption = computed(() => {
  const t = tokens()
  return {
    ...baseOption(t),
    tooltip: { ...baseOption(t).tooltip, trigger: 'axis', valueFormatter: (v: number) => eur(v) },
    grid: { left: 64, right: 16, top: 16, bottom: 28 },
    xAxis: { type: 'time', axisLine: { lineStyle: { color: t.rule } }, axisLabel: { color: t.ink3 } },
    yAxis: { scale: true, splitLine: { lineStyle: { color: t.rule, opacity: 0.6 } }, axisLabel: { color: t.ink3, formatter: (v: number) => eur0(v) } },
    series: [{ type: 'line', name: 'Portfolio value', data: snapshots.value.map((s) => [s.date, s.total]), symbolSize: 8,
               lineStyle: { width: 2, color: t.invest }, itemStyle: { color: t.invest } }],
  }
})

const shown = computed(() => (snap.value?.holdings ?? []).filter((h) => !filter.value || filter.value.isins.includes(h.isin)))
function pickSlice(p: { name: string; data: { isins: string[] } }) {
  filter.value = { label: p.name, isins: p.data.isins }
}
</script>

<template>
  <div>
    <header class="head">
      <div>
        <h1 class="total" v-if="snap">{{ eur(snap.total) }}</h1>
        <p class="muted" v-if="snap">Portfolio value on {{ fmtDate(snap.date) }}, {{ snap.holdings.length }} Holdings</p>
      </div>
      <label v-if="snapshots.length" class="row">Snapshot
        <select v-model="selected">
          <option v-for="s in [...snapshots].reverse()" :key="s.id" :value="s.id">{{ fmtDate(s.date) }}</option>
        </select>
      </label>
    </header>

    <div v-if="!snapshots.length" class="empty">
      <h2>No Portfolio yet</h2>
      <p class="muted">Import a Trade Republic Portfolio Statement PDF with the button on the left. Only the Holdings and the date are kept; the PDF is discarded.</p>
    </div>

    <template v-else-if="snap">
      <section class="block grid2">
        <div>
          <header><h2>By Holding</h2></header>
          <Chart :option="holdingPie" height="320px" label="Portfolio by Holding" @pick="pickSlice" />
        </div>
        <div>
          <header><h2>By Tag</h2></header>
          <Chart :option="tagPie" height="320px" label="Portfolio by Tag" @pick="pickSlice" />
          <p v-if="multiTagged" class="muted note">Holdings with several Tags count in each of them.</p>
        </div>
      </section>

      <section v-if="snapshots.length > 1" class="block">
        <header><h2>Value over time</h2></header>
        <Chart :option="lineOption" height="240px" label="Total Portfolio value across Snapshots" />
      </section>

      <section class="block">
        <header>
          <h2>Holdings</h2>
          <div v-if="filter" class="chip row">Showing <strong>{{ filter.label }}</strong> <button @click="filter = null">Clear filter</button></div>
        </header>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <table>
          <thead><tr><th>Holding</th><th class="num">Quantity</th><th class="num">Price</th><th class="num">Value</th><th class="num">Share</th><th>Tags</th></tr></thead>
          <tbody>
            <tr v-for="h in shown" :key="h.isin">
              <td>{{ h.name }}<div class="muted small">{{ h.isin }}</div></td>
              <td class="num">{{ h.quantity.toLocaleString('de-DE', { maximumFractionDigits: 6 }) }}</td>
              <td class="num">{{ eur(h.price) }}</td>
              <td class="num">{{ eur(h.value) }}</td>
              <td class="num muted">{{ share(h.value) }}</td>
              <td>
                <form class="row" @submit.prevent="saveTags(h)">
                  <input v-model="tagDraft[h.isin]" placeholder="e.g. ETF, Tech" :aria-label="`Tags for ${h.name}`" list="tag-names" />
                  <button v-if="tagDraft[h.isin] !== h.tags.join(', ')" type="submit">Save</button>
                </form>
              </td>
            </tr>
          </tbody>
        </table>
        <datalist id="tag-names"><option v-for="n in tagNames" :key="n" :value="n" /></datalist>
        <p class="muted small hint">Separate Tags with commas. Tags belong to the ISIN, so they carry over to every Snapshot.</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.25rem; }
.total { font-size: clamp(2rem, 4vw, 3rem); font-weight: 600; letter-spacing: -0.02em; line-height: 1.1; }
.empty { padding: 2rem 0; max-width: 40em; }
.empty p { margin-top: 0.5rem; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; }
.note { font-size: 0.85rem; }
.small { font-size: 0.85rem; }
.hint { margin-top: 0.5rem; }
td input { width: 12rem; }
.chip { background: var(--paper-2); border-radius: 999px; padding: 0.2rem 0.3rem 0.2rem 0.9rem; }
.chip button { border-radius: 999px; }
@media (max-width: 860px) { .grid2 { grid-template-columns: 1fr; } }
</style>
