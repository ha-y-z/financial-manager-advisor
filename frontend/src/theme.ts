import { ref } from 'vue'
import { categories } from './state'
import type { Info } from './api'
import { esc, eur } from './state'

const mq = window.matchMedia('(prefers-color-scheme: dark)')
const dark = ref(mq.matches)
mq.addEventListener('change', (e) => (dark.value = e.matches))

/** CSS tokens for charts; reading `dark` makes computed chart options re-render on a theme switch. */
export function tokens() {
  void dark.value
  const s = getComputedStyle(document.documentElement)
  const v = (n: string) => s.getPropertyValue(n).trim()
  return {
    paper: v('--paper'), ink: v('--ink'), ink2: v('--ink-2'), ink3: v('--ink-3'), rule: v('--rule'),
    income: v('--income'), expense: v('--expense'), invest: v('--invest'), saved: v('--saved'),
    reserves: v('--reserves'), neutral: v('--neutral'),
    series: Array.from({ length: 8 }, (_, i) => v(`--series-${i + 1}`)),
    font: 'Schibsted Grotesk Variable, system-ui, sans-serif',
  }
}

/** Color follows the entity: a Category's hue is fixed by its first-level ancestor's position, never its rank. */
export function categoryColor(id: number | undefined, t = tokens()) {
  const cats = categories.value
  let c = cats.find((x) => x.id === id)
  while (c && c.depth > 1) c = cats.find((x) => x.id === c!.parent_id)
  if (!c || c.depth !== 1) return t.neutral
  const siblings = cats.filter((x) => x.parent_id === c!.parent_id).map((x) => x.id).sort((a, b) => a - b)
  return t.series[siblings.indexOf(c.id)] ?? t.neutral
}

export function infoTooltip(title: string, info?: Info | null, extra = '') {
  if (!info) return `<b>${esc(title)}</b>${extra}`
  const top = info.top.map((x) => `<li>${esc(x.name)} <span>${eur(x.sum)}</span></li>`).join('')
  return `<div class="tip"><b>${esc(title)}</b><div class="tip-sum">${eur(info.sum)}</div>
    <div class="tip-count">${info.count} transaction${info.count === 1 ? '' : 's'}</div>${extra}
    ${top ? `<ol>${top}</ol>` : ''}</div>`
}

export function baseOption(t = tokens()) {
  return {
    textStyle: { fontFamily: t.font, color: t.ink2 },
    tooltip: {
      backgroundColor: t.paper, borderColor: t.rule, textStyle: { color: t.ink, fontFamily: t.font },
      extraCssText: 'box-shadow:none;border-radius:6px;padding:10px 12px;',
    },
    animationDuration: 400,
  }
}
