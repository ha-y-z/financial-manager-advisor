<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api, qs, type TypeMappings } from './api'
import UploadZone from './components/UploadZone.vue'
import CashFlow from './views/CashFlow.vue'
import Portfolio from './views/Portfolio.vue'
import Review from './views/Review.vue'
import Setup from './views/Setup.vue'
import { jumpToLatest, loadCategories, version } from './state'

const tabs = [
  { id: 'cash', label: 'Cash flow' },
  { id: 'review', label: 'Review' },
  { id: 'portfolio', label: 'Portfolio' },
  { id: 'setup', label: 'Setup' },
] as const
type Tab = (typeof tabs)[number]['id']
const fromHash = () => tabs.find((t) => t.id === location.hash.slice(1))?.id ?? 'cash'
const tab = ref<Tab>(fromHash())
watch(tab, (t) => history.replaceState(null, '', '#' + t))
const reviewCount = ref(0)

async function refreshCounts() {
  const [open, types] = await Promise.all([
    api.get<unknown[]>('/transactions' + qs({ uncategorized: true })),
    api.get<TypeMappings>('/type-mappings'),
  ])
  reviewCount.value = open.length + types.unknown.length
}

onMounted(() => { loadCategories(); refreshCounts(); jumpToLatest() })
watch(version, () => { loadCategories(); refreshCounts() })
</script>

<template>
  <div class="shell">
    <nav class="rail" aria-label="Sections">
      <div class="mark" aria-hidden="true">
        <svg viewBox="0 0 32 32" width="28" height="28"><path d="M3 9c10 0 12 7 26 7" stroke="var(--income)" stroke-width="5" fill="none"/><path d="M3 23c10 0 12-7 26-7" stroke="var(--expense)" stroke-width="5" fill="none"/></svg>
      </div>
      <button v-for="t in tabs" :key="t.id" :class="{ active: tab === t.id }" :aria-current="tab === t.id ? 'page' : undefined"
              @click="tab = t.id">
        {{ t.label }}<span v-if="t.id === 'review' && reviewCount" class="count">{{ reviewCount }}</span>
      </button>
      <div class="rail-foot"><UploadZone /></div>
    </nav>
    <main>
      <CashFlow v-if="tab === 'cash'" />
      <Review v-else-if="tab === 'review'" />
      <Portfolio v-else-if="tab === 'portfolio'" />
      <Setup v-else />
    </main>
  </div>
</template>

<style scoped>
.shell { display: grid; grid-template-columns: 200px 1fr; min-height: 100vh; }
.rail {
  position: sticky; top: 0; height: 100vh; display: flex; flex-direction: column; gap: 2px;
  padding: 1.25rem 0.75rem; border-right: 1px solid var(--rule); background: var(--paper-2);
}
.mark { padding: 0 0.6rem 1.25rem; }
.rail > button { border: none; text-align: left; padding: 0.5rem 0.6rem; border-radius: 6px; display: flex; justify-content: space-between; color: var(--ink-2); }
.rail > button.active { background: var(--paper); color: var(--ink); font-weight: 600; }
.count { font-size: 0.8rem; background: var(--ink); color: var(--paper); border-radius: 999px; padding: 0 0.45rem; min-width: 1.4rem; text-align: center; }
.rail-foot { margin-top: auto; }
main { padding: 1.75rem clamp(1rem, 3vw, 2.75rem) 4rem; max-width: 1280px; width: 100%; }

@media (max-width: 760px) {
  .shell { grid-template-columns: 1fr; }
  .rail { position: static; height: auto; flex-direction: row; flex-wrap: wrap; align-items: center; padding: 0.5rem 1rem; border-right: none; border-bottom: 1px solid var(--rule); }
  .mark { padding: 0 0.5rem 0 0; }
  .rail-foot { margin: 0 0 0 auto; }
  main { padding: 1.25rem 1rem 3rem; }
}
</style>
