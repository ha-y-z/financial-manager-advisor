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

const hasChildren = (id: number) => categories.value.some((c) => c.parent_id === id)
const groups = computed(() =>
  categories.value
    .filter((r) => r.depth === 0)
    .sort((a, b) => a.id - b.id)
    .map((root) => ({
      root,
      options: categories.value
        .filter((c) => c.flow === root.flow && (c.depth > 0 || props.roots || !hasChildren(c.id)))
        .map((c) => ({ id: c.id, name: c.depth === 0 ? (hasChildren(c.id) ? `${c.name} (Flow Type only)` : c.name) : c.path.split(' › ').slice(1).join(' › ') })),
    }))
    .filter((g) => g.options.length),
)
// a value that isn't offered (e.g. a root without `roots`) shows the placeholder instead of a blank select
const shown = computed(() => (groups.value.some((g) => g.options.some((o) => o.id === props.modelValue)) ? props.modelValue! : ''))
const pick = (e: Event) => {
  const v = (e.target as HTMLSelectElement).value
  emit('update:modelValue', v ? Number(v) : null)
}
</script>

<template>
  <select :value="shown" :aria-label="label ?? 'Category'" @change="pick">
    <option v-if="clearable || shown === ''" value="" :disabled="!clearable">{{ placeholder ?? 'Choose a Category' }}</option>
    <optgroup v-for="g in groups" :key="g.root.id" :label="g.root.name">
      <option v-for="o in g.options" :key="o.id" :value="o.id">{{ o.name }}</option>
    </optgroup>
  </select>
</template>
