<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { api, type Counterparty, type OwnAccount, type Recurring, type TypeMappings } from '../api'
import CategorySelect from '../components/CategorySelect.vue'
import { bump, categories, eur, fmtDate, todayIso, version } from '../state'

const error = ref('')
const accounts = ref<OwnAccount[]>([])
const cps = ref<Counterparty[]>([])
const recurring = ref<Recurring[]>([])
const mappings = ref<TypeMappings | null>(null)

watch(version, async () => {
  ;[accounts.value, cps.value, recurring.value, mappings.value] = await Promise.all([
    api.get<OwnAccount[]>('/own-accounts'), api.get<Counterparty[]>('/counterparties'),
    api.get<Recurring[]>('/recurring'), api.get<TypeMappings>('/type-mappings'),
  ])
}, { immediate: true })

async function run(fn: () => Promise<unknown>) {
  try { await fn(); error.value = ''; bump(); return true } catch (e) { error.value = (e as Error).message; return false }
}

// --- Own Accounts ---
const setIncomeSource = (a: OwnAccount, on: boolean) => run(() => api.put(`/own-accounts/${a.iban}`, { label: a.label, income_source: on }))
const removeAccount = (a: OwnAccount) => run(() => api.del(`/own-accounts/${a.iban}`))
const setDefault = (c: Counterparty, v: number | null) => run(() => api.patch(`/counterparties/${c.id}`, { default_category_id: v }))
const splitAlias = (raw: string) => run(() => api.post('/counterparties/split', { raw_name: raw }))
const setMapping = (trType: string, v: number | null) => v != null && run(() => api.put(`/type-mappings/${trType}`, { category_id: v }))
const acct = reactive({ iban: '', label: '', income_source: false })
async function addAccount() {
  if (await run(() => api.put(`/own-accounts/${encodeURIComponent(acct.iban)}`, acct))) Object.assign(acct, { iban: '', label: '', income_source: false })
}

// --- Categories ---
const roots = computed(() => categories.value.filter((c) => c.depth === 0).sort((a, b) => a.id - b.id))
const childrenOf = (id: number) => categories.value.filter((c) => c.parent_id === id)
const newName = reactive<Record<number, string>>({})
const renaming = ref<number | null>(null)
const renameTo = ref('')
async function addCategory(parent: number) {
  const name = newName[parent]?.trim()
  if (name && (await run(() => api.post('/categories', { name, parent_id: parent })))) newName[parent] = ''
}
async function rename(id: number) {
  if (await run(() => api.patch(`/categories/${id}`, { name: renameTo.value }))) renaming.value = null
}
async function removeCategory(id: number, path: string) {
  const i = await api.get<{ transactions: number; default_categories: number; subcategories: number; moved_to: string }>(`/categories/${id}/impact`)
  const parts = [`${i.transactions} Transaction${i.transactions === 1 ? '' : 's'}`, `${i.default_categories} Default Categor${i.default_categories === 1 ? 'y' : 'ies'}`]
  if (i.subcategories) parts.push(`${i.subcategories} sub-Categor${i.subcategories === 1 ? 'y' : 'ies'} (deleted too)`)
  if (confirm(`Delete "${path}"?\n\n${parts.join(', ')} will move to "${i.moved_to}".`)) run(() => api.del(`/categories/${id}`))
}

// --- Counterparties ---
const cpSearch = ref('')
const openCp = ref<number | null>(null)
const shownCps = computed(() => cps.value.filter((c) => !cpSearch.value || (c.name + ' ' + c.aliases.join(' ')).toLowerCase().includes(cpSearch.value.toLowerCase())))
const merge = reactive({ keep: null as number | null, drop: null as number | null, defaultFrom: 'keep' as 'keep' | 'drop' | 'none' })
const mergeKeep = computed(() => cps.value.find((c) => c.id === merge.keep))
const mergeDrop = computed(() => cps.value.find((c) => c.id === merge.drop))
async function doMerge() {
  const d = merge.defaultFrom === 'keep' ? mergeKeep.value?.default_category_id : merge.defaultFrom === 'drop' ? mergeDrop.value?.default_category_id : null
  if (await run(() => api.post('/counterparties/merge', { keep_id: merge.keep, drop_id: merge.drop, default_category_id: d ?? null })))
    Object.assign(merge, { keep: null, drop: null, defaultFrom: 'keep' })
}

// --- Recurring Entries ---
const rec = reactive({ amount: null as number | null, direction: 'out', counterparty: '', category_id: null as number | null, interval: 'monthly', start: todayIso().slice(0, 8) + '01', end: '' })
async function addRecurring() {
  const amount = Math.abs(rec.amount ?? 0) * (rec.direction === 'out' ? -1 : 1)
  if (await run(() => api.post('/recurring', { ...rec, amount, end: rec.end || null })))
    Object.assign(rec, { amount: null, counterparty: '', category_id: null, end: '' })
}
const recEdit = reactive<Record<number, { amount: number; end: string }>>({})
const startRecEdit = (r: Recurring) => (recEdit[r.id] = { amount: r.amount, end: r.end ?? '' })
async function saveRec(r: Recurring) {
  const e = recEdit[r.id]
  if (await run(() => api.patch(`/recurring/${r.id}`, { amount: e.amount, end: e.end || null }))) delete recEdit[r.id]
}
</script>

<template>
  <div>
    <h1 class="title">Setup</h1>
    <p v-if="error" class="error sticky" role="alert">{{ error }}</p>

    <section class="block">
      <header><h2>Own Accounts</h2></header>
      <p class="muted lede">Transfers to and from these IBANs are Internal Transfers. Mark the account your salary arrives on as Income Source: money coming in from it counts as Income, money going back stays internal.</p>
      <table v-if="accounts.length">
        <thead><tr><th>IBAN</th><th>Name</th><th>Income Source</th><th></th></tr></thead>
        <tbody>
          <tr v-for="a in accounts" :key="a.iban">
            <td><code>{{ a.iban }}</code></td>
            <td>{{ a.label }}</td>
            <td><input type="checkbox" :checked="a.income_source" :aria-label="`Income Source: ${a.iban}`"
                       @change="setIncomeSource(a, ($event.target as HTMLInputElement).checked)" /></td>
            <td class="num"><button class="link danger" @click="removeAccount(a)">Remove</button></td>
          </tr>
        </tbody>
      </table>
      <form class="row add" @submit.prevent="addAccount">
        <input v-model="acct.iban" placeholder="IBAN" aria-label="IBAN" required size="26" />
        <input v-model="acct.label" placeholder="Name, e.g. Sparkasse" aria-label="Account name" />
        <label class="row"><input v-model="acct.income_source" type="checkbox" /> Income Source</label>
        <button class="primary" type="submit">Add account</button>
      </form>
    </section>

    <section class="block">
      <header><h2>Categories</h2></header>
      <p class="muted lede">The four Flow Types are fixed. Below each you can keep two levels of your own Categories.</p>
      <div class="roots">
        <div v-for="r in roots" :key="r.id" class="root">
          <h3>{{ r.name }}</h3>
          <ul class="tree">
            <li v-for="c in childrenOf(r.id)" :key="c.id">
              <div class="cat-line">
                <template v-if="renaming === c.id">
                  <form class="row" @submit.prevent="rename(c.id)"><input v-model="renameTo" aria-label="New name" /><button type="submit">Save</button><button type="button" class="link" @click="renaming = null">Cancel</button></form>
                </template>
                <template v-else>
                  <span>{{ c.name }}</span>
                  <span class="cat-actions">
                    <button class="link" @click="renaming = c.id; renameTo = c.name">Rename</button>
                    <button class="link danger" @click="removeCategory(c.id, c.path)">Delete</button>
                  </span>
                </template>
              </div>
              <ul class="tree">
                <li v-for="g in childrenOf(c.id)" :key="g.id" class="cat-line">
                  <template v-if="renaming === g.id">
                    <form class="row" @submit.prevent="rename(g.id)"><input v-model="renameTo" aria-label="New name" /><button type="submit">Save</button><button type="button" class="link" @click="renaming = null">Cancel</button></form>
                  </template>
                  <template v-else>
                    <span>{{ g.name }}</span>
                    <span class="cat-actions">
                      <button class="link" @click="renaming = g.id; renameTo = g.name">Rename</button>
                      <button class="link danger" @click="removeCategory(g.id, g.path)">Delete</button>
                    </span>
                  </template>
                </li>
                <li><form class="row new" @submit.prevent="addCategory(c.id)"><input v-model="newName[c.id]" :placeholder="`New under ${c.name}`" :aria-label="`New Category under ${c.name}`" /></form></li>
              </ul>
            </li>
            <li v-if="r.name !== 'Internal Transfer'"><form class="row new" @submit.prevent="addCategory(r.id)"><input v-model="newName[r.id]" :placeholder="`New under ${r.name}`" :aria-label="`New Category under ${r.name}`" /></form></li>
          </ul>
        </div>
      </div>
    </section>

    <section class="block">
      <header><h2>Counterparties</h2></header>
      <p class="muted lede">Raw names from the bank (Aliases) are grouped automatically. Merge what belongs together, split what doesn't.</p>

      <form class="merge row" @submit.prevent="doMerge">
        <strong>Merge</strong>
        <select v-model="merge.drop" aria-label="Counterparty to merge away">
          <option :value="null">Counterparty…</option>
          <option v-for="c in cps" :key="c.id" :value="c.id" :disabled="c.id === merge.keep">{{ c.name }}</option>
        </select>
        into
        <select v-model="merge.keep" aria-label="Counterparty to keep">
          <option :value="null">Counterparty…</option>
          <option v-for="c in cps" :key="c.id" :value="c.id" :disabled="c.id === merge.drop">{{ c.name }}</option>
        </select>
        <template v-if="mergeKeep && mergeDrop">
          , keeping Default Category
          <select v-model="merge.defaultFrom" aria-label="Surviving Default Category">
            <option value="keep">{{ mergeKeep.default_category ?? 'none' }} (from {{ mergeKeep.name }})</option>
            <option value="drop">{{ mergeDrop.default_category ?? 'none' }} (from {{ mergeDrop.name }})</option>
            <option value="none">no Default Category</option>
          </select>
          <button class="primary" type="submit">Merge</button>
        </template>
      </form>

      <input v-model="cpSearch" type="search" placeholder="Find a Counterparty or Alias" aria-label="Find Counterparty" class="cp-search" />
      <table>
        <thead><tr><th>Counterparty</th><th>Default Category</th><th class="num">Transactions</th><th class="num">Aliases</th></tr></thead>
        <tbody>
          <template v-for="c in shownCps.slice(0, 150)" :key="c.id">
            <tr>
              <td>{{ c.name }}</td>
              <td><CategorySelect :model-value="c.default_category_id" placeholder="None" clearable :label="`Default Category for ${c.name}`"
                                  @update:model-value="(v) => setDefault(c, v)" /></td>
              <td class="num">{{ c.transactions }}</td>
              <td class="num"><button class="link" :aria-expanded="openCp === c.id" @click="openCp = openCp === c.id ? null : c.id">{{ c.aliases.length }}</button></td>
            </tr>
            <tr v-if="openCp === c.id" class="aliases">
              <td colspan="4">
                <ul>
                  <li v-for="a in c.aliases" :key="a" class="row">
                    <code>{{ a }}</code>
                    <button v-if="c.aliases.length > 1" class="link" @click="splitAlias(a)">Split into its own Counterparty</button>
                  </li>
                </ul>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
      <p v-if="shownCps.length > 150" class="muted">Showing 150 of {{ shownCps.length }}; search to narrow down.</p>
    </section>

    <section class="block">
      <header><h2>Recurring Entries</h2></header>
      <p class="muted lede">For regular payments outside the imported account, like insurance paid from your salary account. Each occurrence becomes a Manual Transaction; changes apply only to future occurrences.</p>
      <table v-if="recurring.length">
        <thead><tr><th>Counterparty</th><th>Category</th><th>Every</th><th>From</th><th>Until</th><th class="num">Amount</th><th></th></tr></thead>
        <tbody>
          <tr v-for="r in recurring" :key="r.id">
            <td>{{ r.counterparty }}</td>
            <td>{{ r.category }}</td>
            <td>{{ { monthly: 'month', quarterly: 'quarter', yearly: 'year' }[r.interval] }}</td>
            <td>{{ fmtDate(r.start) }}</td>
            <td>
              <input v-if="recEdit[r.id]" v-model="recEdit[r.id].end" type="date" aria-label="End date" />
              <span v-else>{{ r.end ? fmtDate(r.end) : 'open' }}</span>
            </td>
            <td class="num">
              <input v-if="recEdit[r.id]" v-model.number="recEdit[r.id].amount" type="number" step="0.01" aria-label="Amount" class="amount" />
              <span v-else>{{ eur(r.amount) }}</span>
            </td>
            <td class="num">
              <template v-if="recEdit[r.id]"><button class="primary" @click="saveRec(r)">Save</button> <button class="link" @click="delete recEdit[r.id]">Cancel</button></template>
              <template v-else><button class="link" @click="startRecEdit(r)">Change or end</button></template>
            </td>
          </tr>
        </tbody>
      </table>
      <form class="row add" @submit.prevent="addRecurring">
        <select v-model="rec.direction" aria-label="Direction"><option value="out">Pay</option><option value="in">Receive</option></select>
        <input v-model.number="rec.amount" type="number" step="0.01" min="0" placeholder="Amount €" aria-label="Amount" required class="amount" />
        <input v-model="rec.counterparty" placeholder="Counterparty" aria-label="Counterparty" required />
        <CategorySelect v-model="rec.category_id" />
        <select v-model="rec.interval" aria-label="Interval"><option value="monthly">monthly</option><option value="quarterly">quarterly</option><option value="yearly">yearly</option></select>
        <label class="row">from <input v-model="rec.start" type="date" required /></label>
        <label class="row">until <input v-model="rec.end" type="date" /></label>
        <button class="primary" type="submit">Add Recurring Entry</button>
      </form>
    </section>

    <section class="block" v-if="mappings">
      <header><h2>Trade Republic types</h2></header>
      <p class="muted lede">How each export type is read. Changes apply to all past and future Transactions. Transfer types ({{ mappings.builtin.join(', ') }}) are decided by IBAN via your Own Accounts.</p>
      <table>
        <thead><tr><th>Type</th><th>Treated as</th></tr></thead>
        <tbody>
          <tr v-for="m in mappings.mappings" :key="m.tr_type">
            <td><code>{{ m.tr_type }}</code></td>
            <td><CategorySelect :model-value="m.category_id" roots :label="`Mapping for ${m.tr_type}`"
                                @update:model-value="(v) => setMapping(m.tr_type, v)" /></td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.title { font-size: 2rem; font-weight: 600; margin-bottom: 0.5rem; }
.lede { max-width: 46em; margin-bottom: 1rem; }
.sticky { position: sticky; top: 0; background: var(--paper); padding: 0.5rem 0; z-index: 5; }
.add { margin-top: 0.75rem; }
.amount { width: 7rem; }
.roots { display: grid; grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); gap: 1.5rem 2rem; }
.root h3 { padding-bottom: 0.35rem; border-bottom: 2px solid var(--ink); margin-bottom: 0.35rem; }
.tree { list-style: none; margin: 0; padding: 0; }
.tree .tree { padding-left: 1rem; border-left: 1px solid var(--rule); margin: 0.1rem 0 0.4rem 0.2rem; }
.cat-line { display: flex; justify-content: space-between; gap: 0.5rem; padding: 0.15rem 0; }
.cat-actions { visibility: hidden; white-space: nowrap; font-size: 0.85rem; }
.cat-actions .link + .link { margin-left: 0.5rem; }
.cat-line:hover .cat-actions, .cat-line:focus-within .cat-actions { visibility: visible; }
.new input { border-style: dashed; width: 100%; font-size: 0.9rem; padding: 0.15rem 0.4rem; margin: 0.15rem 0; }
.merge { padding: 0.75rem; background: var(--paper-2); border-radius: 6px; margin-bottom: 1rem; }
.cp-search { width: min(24rem, 100%); margin-bottom: 0.5rem; }
.aliases td { background: var(--paper-2); }
.aliases ul { list-style: none; margin: 0; padding: 0; }
@media (hover: none) { .cat-actions { visibility: visible; } }
</style>
