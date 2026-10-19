<script setup lang="ts">
import { computed } from 'vue'
import { categories } from '../state'

const props = defineProps<{
  modelValue: number | null | undefined
  placeholder?: string
  label?: string
  /** the empty option is a real choice ("All Categories", "None") */
  clearable?: boolean
  /** Flow Type roots are a real choice (filters, type mappings); elsewhere a root means Uncategorized */
  roots?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [number | null] }>()

const childrenOf = (id: number) => categories.value.filter((c) => c.parent_id === id)
// step 1: Flow Type groups of main Categories (depth 1); step 2: the chosen main Category's subcategories
const groups = computed(() =>
  categories.value
    .filter((r) => r.depth === 0)
    .sort((a, b) => a.id - b.id)
    .map((root) => {
      const mains = childrenOf(root.id)
      const self = props.roots || !mains.length ? [{ id: root.id, name: mains.length ? `${root.name} (Flow Type only)` : root.name }] : []
      return { root, options: [...self, ...mains.map((c) => ({ id: c.id, name: c.name }))] }
    })
    .filter((g) => g.options.length),
)
const picked = computed(() => categories.value.find((c) => c.id === props.modelValue))
const mainId = computed(() => (picked.value?.depth === 2 ? picked.value.parent_id! : picked.value?.id))
// a value that isn't offered (e.g. a root without `roots`) shows the placeholder instead of a blank select
const shown = computed(() => (groups.value.some((g) => g.options.some((o) => o.id === mainId.value)) ? mainId.value! : ''))
const main = computed(() => (shown.value === '' ? undefined : categories.value.find((c) => c.id === shown.value)))
const subs = computed(() => (main.value?.depth === 1 ? childrenOf(main.value.id) : []))
const pick = (e: Event) => {
  const v = (e.target as HTMLSelectElement).value
  emit('update:modelValue', v ? Number(v) : null)
}
</script>

<template>
  <span class="row cat-pick">
    <select :value="shown" :aria-label="label ?? 'Category'" @change="pick">
      <option v-if="clearable || shown === ''" value="" :disabled="!clearable">{{ placeholder ?? 'Choose a Category' }}</option>
      <optgroup v-for="g in groups" :key="g.root.id" :label="g.root.name">
        <option v-for="o in g.options" :key="o.id" :value="o.id">{{ o.name }}</option>
      </optgroup>
    </select>
    <select v-if="main && subs.length" :value="modelValue" :aria-label="`${label ?? 'Category'}: subcategory`" @change="pick">
      <option :value="main.id">{{ clearable && roots ? `All of ${main.name}` : `${main.name} only` }}</option>
      <option v-for="s in subs" :key="s.id" :value="s.id">{{ s.name }}</option>
    </select>
  </span>
</template>
