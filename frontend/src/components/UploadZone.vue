<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api'
import { bump, eur, fmtDate, jumpToLatest } from '../state'

const picker = ref<HTMLInputElement>()
const dragging = ref(false)
const busy = ref(false)
const result = ref<{ ok: boolean; title: string; lines: string[] } | null>(null)
let depth = 0

async function importFile(file: File) {
  const ext = file.name.toLowerCase().split('.').pop()
  if (ext !== 'csv' && ext !== 'pdf') {
    result.value = { ok: false, title: `${file.name} wasn't imported`, lines: ['Drop a Trade Republic CSV export or a Portfolio Statement PDF.'] }
    return
  }
  const form = new FormData()
  form.append('file', file)
  busy.value = true
  try {
    if (ext === 'csv') {
      const s = await api.post<{ new: number; known: number; uncategorized: number; excluded: number }>('/import/transactions', form)
      result.value = {
        ok: true, title: `Imported ${file.name}`,
        lines: [`${s.new} new`, `${s.known} already known`, `${s.uncategorized} uncategorized`, `${s.excluded} excluded`],
      }
      await jumpToLatest()
    } else {
      const s = await api.post<{ date: string; holdings: number; total: number; replaced: boolean }>('/import/portfolio', form)
      result.value = {
        ok: true, title: `Portfolio of ${fmtDate(s.date)} imported`,
        lines: [`${s.holdings} Holdings worth ${eur(s.total)}`, s.replaced ? 'Replaced the Snapshot with the same date' : 'New Snapshot', 'The PDF itself was not stored'],
      }
    }
    bump()
  } catch (e) {
    result.value = { ok: false, title: `${file.name} wasn't imported`, lines: [(e as Error).message] }
  } finally {
    busy.value = false
  }
}

function onPick(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) importFile(f)
  ;(e.target as HTMLInputElement).value = ''
}

const hasFiles = (e: DragEvent) => e.dataTransfer?.types.includes('Files')
function enter(e: DragEvent) { if (hasFiles(e)) { depth++; dragging.value = true } }
function leave() { if (--depth <= 0) { depth = 0; dragging.value = false } }
function over(e: DragEvent) { if (hasFiles(e)) e.preventDefault() }
function drop(e: DragEvent) {
  e.preventDefault()
  depth = 0
  dragging.value = false
  const f = e.dataTransfer?.files[0]
  if (f) importFile(f)
}

onMounted(() => {
  window.addEventListener('dragenter', enter)
  window.addEventListener('dragleave', leave)
  window.addEventListener('dragover', over)
  window.addEventListener('drop', drop)
})
onBeforeUnmount(() => {
  window.removeEventListener('dragenter', enter)
  window.removeEventListener('dragleave', leave)
  window.removeEventListener('dragover', over)
  window.removeEventListener('drop', drop)
})
</script>

<template>
  <div>
    <button class="import" :disabled="busy" @click="picker?.click()">{{ busy ? 'Importing…' : 'Import file' }}</button>
    <p class="hint muted">or drop a CSV or PDF anywhere</p>
    <input ref="picker" type="file" accept=".csv,.pdf" hidden @change="onPick" />

    <div v-if="dragging" class="overlay" aria-hidden="true">
      <div>
        <h1>Drop to import</h1>
        <p>Trade Republic CSV export or Portfolio Statement PDF</p>
      </div>
    </div>

    <div v-if="result" class="result" :class="{ bad: !result.ok }" role="status">
      <div class="row" style="justify-content: space-between">
        <strong>{{ result.title }}</strong>
        <button class="link" @click="result = null">Close</button>
      </div>
      <ul><li v-for="l in result.lines" :key="l">{{ l }}</li></ul>
    </div>
  </div>
</template>

<style scoped>
.import { width: 100%; background: var(--ink); color: var(--paper); border-color: var(--ink); }
.hint { font-size: 0.8rem; margin-top: 0.35rem; text-align: center; }
.overlay {
  position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; text-align: center;
  background: color-mix(in srgb, var(--paper) 88%, transparent); border: 3px dashed var(--ink-3);
}
.overlay h1 { font-size: 2.5rem; }
.result {
  position: fixed; left: 1rem; bottom: 1rem; z-index: 40; width: min(340px, calc(100vw - 2rem));
  background: var(--paper); border: 1px solid var(--rule); border-left: 4px solid var(--income); border-radius: 6px; padding: 0.75rem 1rem;
}
.result.bad { border-left-color: var(--danger); }
.result ul { margin: 0.4rem 0 0; padding-left: 1.1rem; color: var(--ink-2); }
@media (max-width: 760px) { .hint { display: none; } }
</style>
