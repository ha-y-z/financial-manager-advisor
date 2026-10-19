<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { api, qs, type Counterparty, type Flow, type Tx, type TxFilters } from '../api'
import { bump, eur, fmtDate, todayIso, version } from '../state'
import CategorySelect from './CategorySelect.vue'

const props = withDefaults(defineProps<{
  filters: TxFilters
  period?: { start: string; end: string }
  mode?: 'normal' | 'review' | 'excluded'
  controls?: boolean
  allowAdd?: boolean
  empty?: string
}>(), { mode: 'normal', controls: true, allowAdd: false, empty: 'No Transactions match.' })

const rows = ref<Tx[]>([])
const limit = ref(100)
const error = ref('')
const counterparties = ref<Counterparty[]>([])
const flows: Flow[] = ['Income', 'Expense', 'Investment Flow', 'Internal Transfer']

const query = computed(() => ({
  ...props.filters,
  start: props.filters.start || props.period?.start,
  end: props.filters.end || props.period?.end,
  uncategorized: props.mode === 'review' || props.filters.uncategorized,
  excluded: props.mode === 'excluded',
}))

async function load() {
  try {
    rows.value = await api.get<Tx[]>('/transactions' + qs(query.value))
    error.value = ''
  } catch (e) { error.value = (e as Error).message }
}
async function loadCounterparties() { counterparties.value = await api.get<Counterparty[]>('/counterparties') }
watch(query, () => { limit.value = 100; load() }, { deep: true, immediate: true })
watch(version, () => { load(); loadCounterparties() }, { immediate: true })

async function run(fn: () => Promise<unknown>) {
  try { await fn(); error.value = ''; bump() } catch (e) { error.value = (e as Error).message }
}

// --- category choice: all of this Counterparty vs. only this one ---
const pending = reactive<Record<number, number | null>>({})
function chooseCategory(t: Tx, scope: 'counterparty' | 'this') {
  const cid = pending[t.id]
  if (cid == null) return
  run(() => api.put(`/transactions/${t.id}/category`, { category_id: cid, scope })).then(() => { if (!error.value) delete pending[t.id] })
}

// --- edit / Override ---
const editing = ref<number | null>(null)
const draft = reactive({ date: '', amount: 0, counterparty: '' })
function startEdit(t: Tx) {
  editing.value = t.id
  Object.assign(draft, { date: t.date, amount: t.amount, counterparty: t.counterparty })
}
function saveEdit(t: Tx) {
  const body: Record<string, unknown> = {}
  if (draft.date !== t.date) body.date = draft.date
  if (draft.amount !== t.amount) body.amount = draft.amount
  if (draft.counterparty.trim() && draft.counterparty !== t.counterparty) body.counterparty = draft.counterparty.trim()
  run(() => api.patch(`/transactions/${t.id}`, body)).then(() => (editing.value = null))
}

// --- manual add ---
const adding = ref(false)
const fresh = reactive({ date: todayIso(), amount: null as number | null, direction: 'out', counterparty: '', category_id: null as number | null, description: '' })
function addManual() {
  if (!fresh.amount || !fresh.counterparty.trim() || fresh.category_id == null) {
    error.value = 'Date, amount, Counterparty and Category are needed.'
    return
  }
  const amount = Math.abs(fresh.amount) * (fresh.direction === 'out' ? -1 : 1)
  run(() => api.post('/transactions', { ...fresh, amount, counterparty: fresh.counterparty.trim() })).then(() => {
    if (!error.value) Object.assign(fresh, { amount: null, counterparty: '', description: '' })
  })
}

const setExcluded = (t: Tx, excluded: boolean) => run(() => api.post(`/transactions/${t.id}/exclude`, { excluded }))
const remove = (t: Tx) => run(() => api.del(`/transactions/${t.id}`))
const resetOverride = (t: Tx) => run(() => api.del(`/transactions/${t.id}/override`)).then(() => (editing.value = null))

const isRefund = (t: Tx) => t.flow === 'Expense' && t.amount > 0
const total = computed(() => rows.value.reduce((s, t) => s + t.amount, 0))
</script>

<template>
  <div class="tx">
    <div v-if="controls" class="controls row">
      <input v-model="filters.q" type="search" placeholder="Search name or description" aria-label="Search Transactions" />
      <select v-model="filters.flow" aria-label="Flow Type">
        <option value="">All Flow Types</option>
        <option v-for="f in flows" :key="f" :value="f">{{ f }}</option>
      </select>
      <CategorySelect v-model="filters.category_id" placeholder="All Categories" clearable roots />
      <select v-model="filters.counterparty_id" aria-label="Counterparty">
        <option :value="null">All Counterparties</option>
        <option v-for="c in counterparties" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>
      <button v-if="allowAdd" @click="adding = !adding">{{ adding ? 'Close' : 'Add transaction' }}</button>
    </div>

    <form v-if="adding" class="add row" @submit.prevent="addManual">
      <input v-model="fresh.date" type="date" aria-label="Date" required />
      <select v-model="fresh.direction" aria-label="Direction">
        <option value="out">Spent</option>
        <option value="in">Received</option>
      </select>
      <input v-model.number="fresh.amount" type="number" step="0.01" min="0" placeholder="Amount €" aria-label="Amount" required />
      <input v-model="fresh.counterparty" list="cp-names" placeholder="Counterparty" aria-label="Counterparty" required />
      <CategorySelect v-model="fresh.category_id" />
      <input v-model="fresh.description" placeholder="Note (optional)" aria-label="Note" />
      <button class="primary" type="submit">Add Manual Transaction</button>
    </form>
    <datalist id="cp-names"><option v-for="c in counterparties" :key="c.id" :value="c.name" /></datalist>

    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <table v-if="rows.length">
      <thead>
        <tr><th>Date</th><th>Counterparty</th><th>Category</th><th class="num">Amount</th><th><span class="sr">Actions</span></th></tr>
      </thead>
      <tbody>
        <template v-for="t in rows.slice(0, limit)" :key="t.id">
          <tr :class="{ excluded: t.excluded }">
            <td class="date">{{ fmtDate(t.date) }}</td>
            <td>
              {{ t.counterparty }}
              <span v-if="t.manual" class="badge" title="Entered by you">{{ t.recurring_id ? 'Recurring' : 'Manual' }}</span>
              <span v-if="t.overridden" class="badge override" title="Changed by you; the bank's values are kept">Override</span>
              <span v-if="isRefund(t)" class="badge">Refund</span>
              <div v-if="t.description && t.description !== t.counterparty" class="muted small">{{ t.description }}</div>
            </td>
            <td class="cat">
              <div v-if="mode === 'excluded'" class="muted">{{ t.category }}</div>
              <template v-else>
                <CategorySelect :model-value="pending[t.id] ?? (t.uncategorized ? null : t.category_id)"
                                :placeholder="t.uncategorized ? 'Uncategorized' : t.category"
                                @update:model-value="(v) => (pending[t.id] = v)" />
                <div v-if="pending[t.id] != null && pending[t.id] !== t.category_id" class="choice row">
                  <button class="primary" @click="chooseCategory(t, 'counterparty')">All of {{ t.counterparty }}</button>
                  <button @click="chooseCategory(t, 'this')">Only this one</button>
                  <button class="link" @click="delete pending[t.id]">Cancel</button>
                </div>
              </template>
            </td>
            <td class="num amount">{{ eur(t.amount) }}</td>
            <td class="actions">
              <template v-if="mode === 'excluded'">
                <button @click="setExcluded(t, false)">Restore</button>
              </template>
              <template v-else>
                <button class="link" @click="editing === t.id ? (editing = null) : startEdit(t)">Edit</button>
                <button v-if="t.manual && !t.recurring_id" class="link danger"
                        @click="remove(t)">Delete</button>
                <button v-else class="link" @click="setExcluded(t, true)">Exclude</button>
              </template>
            </td>
          </tr>
          <tr v-if="editing === t.id" class="editor">
            <td colspan="5">
              <form class="row" @submit.prevent="saveEdit(t)">
                <input v-model="draft.date" type="date" aria-label="Date" />
                <input v-model.number="draft.amount" type="number" step="0.01" aria-label="Amount (negative = money out)" />
                <input v-model="draft.counterparty" list="cp-names" aria-label="Counterparty" />
                <button class="primary" type="submit">{{ t.manual ? 'Save' : 'Save as Override' }}</button>
                <button v-if="t.overridden" type="button" @click="resetOverride(t)">
                  Reset to bank values
                </button>
                <button type="button" class="link" @click="editing = null">Cancel</button>
              </form>
              <p v-if="t.original" class="muted small">
                Bank values: {{ fmtDate(t.original.date) }}, {{ eur(t.original.amount) }}, {{ t.original.counterparty }}, {{ t.original.category }}
              </p>
            </td>
          </tr>
        </template>
      </tbody>
      <tfoot>
        <tr>
          <td colspan="3" class="muted">{{ rows.length }} Transaction{{ rows.length === 1 ? '' : 's' }}</td>
          <td class="num">{{ eur(total) }}</td><td></td>
        </tr>
      </tfoot>
    </table>
    <p v-else class="muted empty">{{ empty }}</p>
    <button v-if="rows.length > limit" class="more" @click="limit += 200">Show {{ Math.min(200, rows.length - limit) }} more</button>
  </div>
</template>

<style scoped>
.controls { margin-bottom: 0.75rem; }
.controls input[type='search'] { flex: 1 1 14rem; }
.add { padding: 0.75rem; margin-bottom: 0.75rem; background: var(--paper-2); border-radius: 6px; }
.date { white-space: nowrap; color: var(--ink-2); }
.cat select { max-width: 15rem; }
.choice { margin-top: 0.35rem; }
.amount { font-weight: 500; }
.actions { white-space: nowrap; text-align: right; }
.actions .link + .link { margin-left: 0.6rem; }
.editor td { background: var(--paper-2); }
.small { font-size: 0.85rem; }
.empty { padding: 1rem 0; }
.more { margin-top: 0.75rem; }
tfoot td { border-bottom: none; font-weight: 500; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
@media (max-width: 760px) {
  table, tbody, tr, td { display: block; }
  thead { display: none; }
  tr { padding: 0.5rem 0; border-bottom: 1px solid var(--rule); }
  td { border: none; padding: 0.15rem 0; }
  .num, .actions { text-align: left; }
}
</style>
