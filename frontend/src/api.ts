export type Flow = 'Income' | 'Expense' | 'Investment Flow' | 'Internal Transfer'

export interface Filter {
  flow?: Flow
  category_id?: number
  counterparty_id?: number
  uncategorized?: boolean
  start?: string
  end?: string
}

export interface TxFilters {
  q?: string; flow?: Flow | ''; category_id?: number | null; counterparty_id?: number | null
  uncategorized?: boolean; start?: string; end?: string
}

export interface Info { sum: number; count: number; top: { name: string; sum: number }[] }

export interface CatNode {
  key: string; name: string; value: number; info: Info; filter: Filter; children: CatNode[]
}

export interface Analytics {
  monthly: { month: string; income: number; expense: number; rate: number | null }[]
  sunburst: { Expense: CatNode[]; Income: CatNode[] }
  sankey: {
    nodes: { name: string; label: string; info?: Info | null; filter?: Filter | null }[]
    links: { source: string; target: string; value: number; info: Info | null; filter: Filter | null }[]
  }
  top: { name: string; info: Info; filter: Filter }[]
  totals: { income: number; expense: number; invested: number }
}

export interface Tx {
  id: number; date: string; amount: number; counterparty_id: number | null; counterparty: string
  category_id: number | null; category: string; flow: Flow | null; uncategorized: boolean
  description: string; tr_type: string | null; manual: boolean; recurring_id: number | null
  overridden: boolean; excluded: boolean
  original: { date: string; amount: number; counterparty: string; category: string } | null
}

export interface Category { id: number; name: string; parent_id: number | null; flow: Flow; depth: number; path: string }

export interface Counterparty {
  id: number; name: string; default_category_id: number | null; default_category: string | null
  aliases: string[]; transactions: number
}

export interface OwnAccount { iban: string; label: string; income_source: boolean }

export interface Recurring {
  id: number; amount: number; counterparty: string; category_id: number; category: string
  interval: 'monthly' | 'quarterly' | 'yearly'; start: string; end: string | null
}

export interface TypeMappings {
  mappings: { tr_type: string; category_id: number; category: string }[]
  unknown: { tr_type: string; count: number }[]
  builtin: string[]
}

export interface Holding { isin: string; name: string; quantity: number; price: number; value: number; tags: string[] }
export interface SnapshotSummary { id: number; date: string; total: number }
export interface SnapshotDetail extends SnapshotSummary {
  holdings: Holding[]
  by_tag: { name: string; value: number; isins: string[] }[]
}

async function req<T>(method: string, url: string, body?: unknown): Promise<T> {
  const isForm = body instanceof FormData
  const r = await fetch('/api' + url, {
    method,
    headers: body === undefined || isForm ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  })
  const data = await r.json().catch(() => null)
  if (!r.ok) {
    const detail = data?.detail
    throw new Error(typeof detail === 'string' ? detail : `The server answered ${r.status}.`)
  }
  return data as T
}

export const api = {
  get: <T>(url: string) => req<T>('GET', url),
  post: <T = unknown>(url: string, body?: unknown) => req<T>('POST', url, body),
  put: <T = unknown>(url: string, body?: unknown) => req<T>('PUT', url, body),
  patch: <T = unknown>(url: string, body?: unknown) => req<T>('PATCH', url, body),
  del: <T = unknown>(url: string) => req<T>('DELETE', url),
}

export function qs(params: object) {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '' && v !== false)
  return entries.length ? '?' + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])) : ''
}
