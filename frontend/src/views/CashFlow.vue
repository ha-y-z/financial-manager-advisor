<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { api, qs, type Analytics, type CatNode, type Filter, type Info, type TxFilters } from '../api'
import Chart from '../components/Chart.vue'
import PeriodPicker from '../components/PeriodPicker.vue'
import TransactionTable from '../components/TransactionTable.vue'
import { eur, eur0, period, periodLabel, version } from '../state'
import { baseOption, categoryColor, infoTooltip, tokens } from '../theme'

const data = ref<Analytics | null>(null)
const error = ref('')
const sunFlow = ref<'Expense' | 'Income'>('Expense')

async function load() {
  if (!period.start || !period.end) return
  try {
    data.value = await api.get<Analytics>('/analytics' + qs({ start: period.start, end: period.end }))
    error.value = ''
  } catch (e) { error.value = (e as Error).message }
}
watch([() => period.start, () => period.end, version], load, { immediate: true })

// --- the Transaction list beneath the charts; chart clicks set its filters ---
const blank = (): TxFilters => ({ q: '', flow: '', category_id: null, counterparty_id: null, uncategorized: false, start: undefined, end: undefined })
const filters = reactive<TxFilters>(blank())
const chartFilter = ref<string | null>(null)
function pick(label: string, f?: Filter | null) {
  if (!f) return
  Object.assign(filters, blank(), f)
  chartFilter.value = label
  document.getElementById('transactions')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
function clearFilter() { Object.assign(filters, blank()); chartFilter.value = null }
watch(() => [period.start, period.end], clearFilter)

// --- headline sentence ---
const headline = computed(() => {
  const t = data.value?.totals
  if (!t) return null
  const kept = t.income - t.expense - t.invested
  return { ...t, kept, rate: t.income > 0 ? Math.round(((t.income - t.expense) / t.income) * 100) : null }
})
const hasData = computed(() => !!data.value && data.value.sankey.links.length > 0)

// --- Sankey ---
const nodeColor = (name: string, f: Filter | null | undefined, t: ReturnType<typeof tokens>, incomeKeys: Set<string>) => {
  if (name === 'budget') return t.ink
  if (name === 'saved') return t.saved
  if (name === 'reserves') return t.reserves
  if (name === 'investments' || name === 'from_investments') return t.invest
  if (incomeKeys.has(name)) return t.income
  return f?.category_id ? categoryColor(f.category_id, t) : t.neutral
}
const sankeyOption = computed(() => {
  const t = tokens()
  const s = data.value?.sankey
  if (!s) return {}
  const incomeKeys = new Set<string>()
  const walk = (n: CatNode) => { incomeKeys.add(n.key); n.children.forEach(walk) }
  data.value!.sunburst.Income.forEach(walk)
  return {
    ...baseOption(t),
    tooltip: {
      ...baseOption(t).tooltip,
      formatter: (p: { dataType: string; data: { label?: string; info?: Info; value: number; source?: string; target?: string } ; value: number }) => {
        const d = p.data
        if (p.dataType === 'edge') {
          const label = (n: string) => s.nodes.find((x) => x.name === n)?.label ?? n
          return infoTooltip(`${label(d.source!)} → ${label(d.target!)}`, d.info, d.info ? '' : `<div class="tip-sum">${eur(p.value)}</div>`)
        }
        return infoTooltip(d.label ?? '', d.info, d.info ? '' : `<div class="tip-sum">${eur(p.value)}</div>`)
      },
    },
    series: [{
      type: 'sankey', left: 4, right: 200, top: 8, bottom: 8, nodeWidth: 10, nodeGap: 12, nodeAlign: 'justify',
      draggable: false, emphasis: { focus: 'adjacency' },
      data: s.nodes.map((n) => ({ ...n, itemStyle: { color: nodeColor(n.name, n.filter, t, incomeKeys), borderWidth: 0 } })),
      links: s.links,
      lineStyle: { color: 'gradient', opacity: 0.28, curveness: 0.5 },
      label: {
        color: t.ink, fontFamily: t.font, fontSize: 13,
        formatter: (p: { data: { label: string }; value: number }) => `{n|${p.data.label}}  {v|${eur0(p.value)}}`,
        rich: { n: { color: t.ink, fontWeight: 500 }, v: { color: t.ink3 } },
      },
    }],
  }
})

// --- monthly Income vs Expense, savings rate as its own small panel (one axis per chart) ---
const monthlyOption = computed(() => {
  const t = tokens()
  const m = data.value?.monthly ?? []
  const months = m.map((x) => new Date(x.month + '-01T00:00').toLocaleDateString('en-GB', { month: 'short', year: '2-digit' }))
  const axisLine = { lineStyle: { color: t.rule } }
  return {
    ...baseOption(t),
    legend: { top: 0, left: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10, textStyle: { color: t.ink2 } },
    tooltip: {
      ...baseOption(t).tooltip, trigger: 'axis', axisPointer: { type: 'shadow', shadowStyle: { color: t.rule, opacity: 0.35 } },
      formatter: (ps: { dataIndex: number }[]) => {
        const x = m[ps[0].dataIndex]
        return `<b>${months[ps[0].dataIndex]}</b><br>Income ${eur(x.income)}<br>Expense ${eur(x.expense)}<br>Saved ${x.rate == null ? '–' : Math.round(x.rate * 100) + ' %'}`
      },
    },
    grid: [{ left: 56, right: 8, top: 36, height: '52%' }, { left: 56, right: 8, bottom: 24, height: '18%' }],
    xAxis: [
      { type: 'category', data: months, gridIndex: 0, axisLine, axisTick: { show: false }, axisLabel: { show: false } },
      { type: 'category', data: months, gridIndex: 1, axisLine, axisTick: { show: false }, axisLabel: { color: t.ink3 } },
    ],
    yAxis: [
      { gridIndex: 0, splitLine: { lineStyle: { color: t.rule, opacity: 0.6 } }, axisLabel: { color: t.ink3, formatter: (v: number) => eur0(v) } },
      { gridIndex: 1, name: 'Savings rate', nameTextStyle: { color: t.ink3, align: 'left' }, splitNumber: 2,
        splitLine: { lineStyle: { color: t.rule, opacity: 0.6 } }, axisLabel: { color: t.ink3, formatter: (v: number) => `${Math.round(v * 100)} %` } },
    ],
    series: [
      { name: 'Income', type: 'bar', data: m.map((x) => x.income), itemStyle: { color: t.income, borderRadius: [4, 4, 0, 0] }, barGap: '12%', barMaxWidth: 28 },
      { name: 'Expense', type: 'bar', data: m.map((x) => x.expense), itemStyle: { color: t.expense, borderRadius: [4, 4, 0, 0] }, barMaxWidth: 28 },
      { name: 'Savings rate', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: m.map((x) => x.rate), lineStyle: { width: 2, color: t.ink }, itemStyle: { color: t.ink }, symbolSize: 8, connectNulls: false },
    ],
  }
})
function pickMonth(p: { seriesName: string; dataIndex: number }) {
  const m = data.value?.monthly[p.dataIndex]
  if (!m || p.seriesName === 'Savings rate') return
  const [y, mo] = m.month.split('-').map(Number)
  const end = new Date(y, mo, 0).getDate()
  pick(`${p.seriesName}, ${m.month}`, { flow: p.seriesName as 'Income' | 'Expense', start: `${m.month}-01`, end: `${m.month}-${end}` })
}

// --- sunburst ---
const sunburstOption = computed(() => {
  const t = tokens()
  const nodes = data.value?.sunburst[sunFlow.value] ?? []
  const toData = (n: CatNode, color?: string): object => {
    const c = color ?? (n.filter.category_id ? categoryColor(n.filter.category_id, t) : t.neutral)
    return { name: n.name, value: n.value, info: n.info, filter: n.filter, itemStyle: { color: c },
             children: n.children.map((k) => toData(k, c)) }
  }
  return {
    ...baseOption(t),
    tooltip: { ...baseOption(t).tooltip, formatter: (p: { name: string; data: { info: Info } }) => infoTooltip(p.name, p.data.info) },
    series: [{
      type: 'sunburst', radius: ['16%', '96%'], sort: undefined, nodeClick: false,
      data: nodes.map((n) => toData(n)),
      itemStyle: { borderColor: t.paper, borderWidth: 2 },
      levels: [{}, { label: { rotate: 'radial', color: '#fff', fontSize: 11, minAngle: 24 } },
               { itemStyle: { opacity: 0.62 }, label: { color: t.ink, fontSize: 11, minAngle: 14, rotate: 'radial' } }],
      emphasis: { focus: 'ancestor' },
    }],
  }
})

const topMax = computed(() => Math.max(1, ...(data.value?.top ?? []).map((x) => x.info.sum)))
</script>

<template>
  <div>
    <header class="top row">
      <PeriodPicker />
    </header>

    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <section class="hero">
      <h1 v-if="headline && hasData" class="sentence">
        In {{ periodLabel }} you earned <span class="amt inc">{{ eur0(headline.income) }}</span>,
        spent <span class="amt exp">{{ eur0(headline.expense) }}</span>
        and invested <span class="amt inv">{{ eur0(headline.invested) }}</span>.
        <template v-if="headline.kept >= 0">You kept <span class="amt sav">{{ eur0(headline.kept) }}</span><template v-if="headline.rate != null">, a savings rate of {{ headline.rate }} %</template>.</template>
        <template v-else>That is <span class="amt res">{{ eur0(-headline.kept) }}</span> more than came in.</template>
      </h1>
      <div v-else-if="data" class="empty">
        <h1 class="sentence">Nothing recorded for {{ periodLabel }}.</h1>
        <p class="muted">Import a Trade Republic CSV export with the button on the left, or pick another period.</p>
      </div>
      <Chart v-if="hasData" :option="sankeyOption" height="460px" label="Money flow from Income through your budget to spending, investments and savings"
             @pick="(p) => pick(p.data.label ?? `${p.data.source} → ${p.data.target}`, p.data.filter)" />
    </section>

    <section v-if="hasData" class="block grid2">
      <div>
        <header><h2>Income and spending by month</h2></header>
        <Chart :option="monthlyOption" height="340px" label="Monthly Income and Expense with savings rate" @pick="pickMonth" />
      </div>
      <div>
        <header class="row" style="justify-content: space-between">
          <h2>Where it went</h2>
          <div class="seg" role="group" aria-label="Flow Type">
            <button :aria-pressed="sunFlow === 'Expense'" @click="sunFlow = 'Expense'">Spending</button>
            <button :aria-pressed="sunFlow === 'Income'" @click="sunFlow = 'Income'">Income</button>
          </div>
        </header>
        <Chart :option="sunburstOption" height="340px" :label="`${sunFlow} by Category`" @pick="(p) => pick(p.name, p.data.filter)" />
      </div>
    </section>

    <section v-if="data?.top.length" class="block">
      <header><h2>Top Counterparties by spending</h2></header>
      <ol class="top-list">
        <li v-for="c in data.top" :key="c.name">
          <button class="top-row" @click="pick(c.name, c.filter)">
            <span class="name">{{ c.name }}</span>
            <span class="bar"><span :style="{ width: (c.info.sum / topMax) * 100 + '%' }"></span></span>
            <span class="num">{{ eur(c.info.sum) }}</span>
            <span class="muted cnt">{{ c.info.count }}×</span>
          </button>
        </li>
      </ol>
    </section>

    <section id="transactions" class="block">
      <header>
        <h2>Transactions</h2>
        <div v-if="chartFilter" class="chip row">
          Showing <strong>{{ chartFilter }}</strong>
          <button @click="clearFilter">Clear filter</button>
        </div>
      </header>
      <TransactionTable :filters="filters" :period="{ start: period.start, end: period.end }" allow-add
                        :empty="`No Transactions in ${periodLabel}.`" />
    </section>
  </div>
</template>

<style scoped>
.top { justify-content: space-between; margin-bottom: 1.5rem; }
.hero { padding-bottom: 1.5rem; }
.sentence { font-size: clamp(1.4rem, 2.6vw, 2.15rem); font-weight: 500; line-height: 1.3; max-width: 34em; margin-bottom: 1.25rem; letter-spacing: -0.015em; }
.amt { font-weight: 650; white-space: nowrap; text-decoration: underline; text-decoration-thickness: 4px; text-underline-offset: 6px; }
.amt.inc { text-decoration-color: var(--income); }
.amt.exp { text-decoration-color: var(--expense); }
.amt.inv { text-decoration-color: var(--invest); }
.amt.sav { text-decoration-color: var(--saved); }
.amt.res { text-decoration-color: var(--reserves); }
.empty { padding: 2rem 0; }
.grid2 { display: grid; grid-template-columns: 3fr 2fr; gap: 2rem; }
.grid2 header { margin-bottom: 0.5rem; min-height: 2rem; }
.seg { display: inline-flex; border: 1px solid var(--rule); border-radius: 6px; overflow: hidden; }
.seg button { border: none; border-radius: 0; color: var(--ink-2); padding: 0.2rem 0.6rem; }
.seg button[aria-pressed='true'] { background: var(--ink); color: var(--paper); }
.top-list { list-style: none; margin: 0; padding: 0; columns: 2 22rem; column-gap: 2.5rem; }
.top-row { width: 100%; display: grid; grid-template-columns: minmax(6rem, 11rem) 1fr auto 2.5rem; gap: 0.75rem; align-items: center;
  border: none; border-radius: 4px; padding: 0.35rem 0.25rem; text-align: left; break-inside: avoid; }
.top-row:hover { background: var(--paper-2); }
.name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar { height: 8px; background: var(--paper-2); border-radius: 4px; overflow: hidden; }
.bar span { display: block; height: 100%; background: var(--expense); border-radius: 0 4px 4px 0; }
.cnt { text-align: right; font-size: 0.85rem; }
.chip { background: var(--paper-2); border-radius: 999px; padding: 0.2rem 0.3rem 0.2rem 0.9rem; }
.chip button { border-radius: 999px; }
@media (max-width: 960px) { .grid2 { grid-template-columns: 1fr; } }
</style>
