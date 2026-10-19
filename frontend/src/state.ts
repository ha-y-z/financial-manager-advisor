import { computed, reactive, ref } from 'vue'
import { api, type Category } from './api'

// --- reload signal: bump after any change so every view refetches ---
export const version = ref(0)
export const bump = () => version.value++

// --- global period ---
export type PeriodKind = 'month' | 'quarter' | 'year' | 'custom'
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const span = { month: 1, quarter: 3, year: 12 }

export const period = reactive({ kind: 'month' as PeriodKind, anchor: new Date(), start: '', end: '' })

export function setPeriod(kind: PeriodKind, anchor = period.anchor) {
  period.kind = kind
  period.anchor = anchor
  if (kind === 'custom') return
  const m = kind === 'month' ? anchor.getMonth() : kind === 'quarter' ? anchor.getMonth() - (anchor.getMonth() % 3) : 0
  const first = new Date(anchor.getFullYear(), m, 1)
  period.start = iso(first)
  period.end = iso(new Date(first.getFullYear(), first.getMonth() + span[kind], 0))
}

export function shiftPeriod(dir: 1 | -1) {
  if (period.kind === 'custom') return
  const a = new Date(period.anchor.getFullYear(), period.anchor.getMonth() + dir * span[period.kind], 1)
  setPeriod(period.kind, a)
}

export const periodLabel = computed(() => {
  const a = period.anchor
  if (period.kind === 'month') return a.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })
  if (period.kind === 'quarter') return `Q${Math.floor(a.getMonth() / 3) + 1} ${a.getFullYear()}`
  if (period.kind === 'year') return String(a.getFullYear())
  return `${fmtDate(period.start)} – ${fmtDate(period.end)}`
})

setPeriod('month')

/** Open on the latest month with data when the selected period ends before it is reached (e.g. after an import). */
export async function jumpToLatest() {
  const { latest } = await api.get<{ latest: string | null }>('/meta')
  if (latest && period.kind !== 'custom' && latest < period.start) setPeriod(period.kind, new Date(latest + 'T00:00'))
}

// --- categories (shared by every select) ---
export const categories = ref<Category[]>([])
export const loadCategories = async () => (categories.value = await api.get<Category[]>('/categories'))

// --- formatting ---
const eurFmt = new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' })
const eur0Fmt = new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 })
export const eur = (n: number) => eurFmt.format(n)
export const eur0 = (n: number) => eur0Fmt.format(n)
export const fmtDate = (s: string) => (s ? new Date(s + 'T00:00').toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '')
export const todayIso = () => iso(new Date())

export const esc = (s: string) =>
  s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)
