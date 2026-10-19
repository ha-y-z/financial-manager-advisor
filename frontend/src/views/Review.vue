<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { api, type TxFilters, type TypeMappings } from '../api'
import CategorySelect from '../components/CategorySelect.vue'
import TransactionTable from '../components/TransactionTable.vue'
import { bump, version } from '../state'

const types = ref<TypeMappings | null>(null)
const choice = reactive<Record<string, number | null>>({})
const error = ref('')
const reviewFilters = reactive<TxFilters>({ q: '', flow: '', category_id: null, counterparty_id: null })
const excludedFilters = reactive<TxFilters>({})

watch(version, async () => (types.value = await api.get<TypeMappings>('/type-mappings')), { immediate: true })

async function map(trType: string) {
  try {
    await api.put(`/type-mappings/${encodeURIComponent(trType)}`, { category_id: choice[trType] })
    error.value = ''
    bump()
  } catch (e) { error.value = (e as Error).message }
}
</script>

<template>
  <div>
    <h1 class="title">Review</h1>
    <p class="muted lede">Transactions the app couldn't place. Choosing a Category for one Counterparty usually settles all of its Transactions at once.</p>

    <section v-if="types?.unknown.length" class="block">
      <header><h2>New Trade Republic types</h2></header>
      <p class="muted">These types aren't known yet. Map each one once and every past and future Transaction of that type follows.</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <table>
        <thead><tr><th>Type</th><th class="num">Transactions</th><th>Treat as</th><th></th></tr></thead>
        <tbody>
          <tr v-for="u in types.unknown" :key="u.tr_type">
            <td><code>{{ u.tr_type }}</code></td>
            <td class="num">{{ u.count }}</td>
            <td><CategorySelect v-model="choice[u.tr_type]" placeholder="Flow Type or Category" roots /></td>
            <td><button class="primary" :disabled="choice[u.tr_type] == null" @click="map(u.tr_type)">Map type</button></td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="block">
      <header><h2>Uncategorized</h2></header>
      <TransactionTable :filters="reviewFilters" mode="review" empty="Everything has a Category." />
    </section>

    <section class="block">
      <header><h2>Excluded</h2></header>
      <p class="muted">Excluded Transactions are left out of every chart and stay out on re-import until you restore them.</p>
      <TransactionTable :filters="excludedFilters" mode="excluded" :controls="false" empty="Nothing is excluded." />
    </section>
  </div>
</template>

<style scoped>
.title { font-size: 2rem; font-weight: 600; }
.lede { max-width: 40em; margin: 0.35rem 0 1.5rem; }
section.block > p.muted { margin-bottom: 0.75rem; max-width: 46em; }
code { font-size: 0.9em; }
</style>
