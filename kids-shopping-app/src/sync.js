// Shared-list sync client. The list lives in Netlify Blobs behind
// /api/list (see netlify/functions/list.mjs). Both parents read/write the
// same document; entries are merged last-write-wins by timestamp so two
// phones editing at once don't clobber each other. When the API is
// unreachable (e.g. plain `vite dev`), the app degrades to localStorage.

const API = '/api/list'
const LS_KEY = 'btshq-list-v1'

export function loadLocal() {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY)) || { entries: {} }
  } catch {
    return { entries: {} }
  }
}

export function saveLocal(doc) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(doc))
  } catch {
    // storage full/blocked — sync still covers us
  }
}

export function mergeDocs(a, b) {
  const entries = { ...a.entries }
  for (const [key, entry] of Object.entries(b.entries || {})) {
    const mine = entries[key]
    if (!mine || (entry.ts || 0) > (mine.ts || 0)) entries[key] = entry
  }
  // Deleted entries are tombstones ({removed: true}); drop old ones.
  const cutoff = Date.now() - 1000 * 60 * 60 * 24 * 30
  for (const key of Object.keys(entries)) {
    if (entries[key].removed && entries[key].ts < cutoff) delete entries[key]
  }
  return { entries }
}

export async function fetchRemote(pin) {
  const res = await fetch(API, { headers: { 'x-family-pin': pin } })
  if (res.status === 401) throw new Error('bad-pin')
  if (!res.ok) throw new Error('unavailable')
  return res.json()
}

export async function pushRemote(pin, doc) {
  const res = await fetch(API, {
    method: 'PUT',
    headers: { 'content-type': 'application/json', 'x-family-pin': pin },
    body: JSON.stringify(doc),
  })
  if (res.status === 401) throw new Error('bad-pin')
  if (!res.ok) throw new Error('unavailable')
  return res.json()
}
