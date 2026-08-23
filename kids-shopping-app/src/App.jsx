import { useEffect, useMemo, useRef, useState } from 'react'
import { KIDS, KID_IDS } from './data/kids.js'
import { RETAILERS, RETAILER_IDS, itemSearchUrl } from './data/retailers.js'
import { CATALOG, CATEGORIES, COLOR_SWATCHES } from './data/catalog.js'
import Login from './components/Login.jsx'
import Header from './components/Header.jsx'
import FilterBar from './components/FilterBar.jsx'
import ProductCard from './components/ProductCard.jsx'
import ListDrawer from './components/ListDrawer.jsx'
import { loadLocal, saveLocal, mergeDocs, fetchRemote, pushRemote } from './sync.js'

const PROFILE_KEY = 'btshq-profile-v1'

const EMPTY_FILTERS = {
  retailers: [],
  categories: [],
  colors: [],
  price: null, // 'under20' | '20to40' | 'over40'
  dealsOnly: false,
  search: '',
  sort: 'featured',
}

export default function App() {
  const [profile, setProfile] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(PROFILE_KEY))
    } catch {
      return null
    }
  })
  const [kidId, setKidId] = useState('aiden')
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [doc, setDoc] = useState(loadLocal)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [syncState, setSyncState] = useState('local') // local | syncing | synced | error
  const pushTimer = useRef(null)
  const docRef = useRef(doc)
  docRef.current = doc

  const kid = KIDS[kidId]

  // Initial pull + gentle polling so both phones stay in step.
  useEffect(() => {
    if (!profile) return
    let alive = true
    const pull = async () => {
      try {
        setSyncState((s) => (s === 'local' ? 'syncing' : s))
        const remote = await fetchRemote(profile.pin)
        if (!alive) return
        setDoc((cur) => {
          const merged = mergeDocs(cur, remote)
          saveLocal(merged)
          return merged
        })
        setSyncState('synced')
      } catch (e) {
        if (!alive) return
        setSyncState(e.message === 'bad-pin' ? 'bad-pin' : 'local')
      }
    }
    pull()
    const iv = setInterval(pull, 30000)
    return () => {
      alive = false
      clearInterval(iv)
    }
  }, [profile])

  const scheduleUpdate = (mutate) => {
    setDoc((cur) => {
      const next = { entries: { ...cur.entries } }
      mutate(next)
      saveLocal(next)
      return next
    })
    if (!profile) return
    clearTimeout(pushTimer.current)
    pushTimer.current = setTimeout(async () => {
      try {
        setSyncState('syncing')
        const remote = await pushRemote(profile.pin, docRef.current)
        setDoc((cur) => {
          const merged = mergeDocs(cur, remote)
          saveLocal(merged)
          return merged
        })
        setSyncState('synced')
      } catch (e) {
        setSyncState(e.message === 'bad-pin' ? 'bad-pin' : 'local')
      }
    }, 600)
  }

  const entryKey = (item) => `${item.kid}:${item.id}`
  const activeEntries = useMemo(
    () => Object.values(doc.entries).filter((e) => !e.removed),
    [doc],
  )

  const toggleItem = (item) => {
    const key = entryKey(item)
    scheduleUpdate((next) => {
      const cur = next.entries[key]
      if (cur && !cur.removed) {
        next.entries[key] = { ...cur, removed: true, ts: Date.now() }
      } else {
        next.entries[key] = {
          key,
          productId: item.id,
          kid: item.kid,
          qty: 1,
          purchased: false,
          addedBy: profile?.name || 'me',
          removed: false,
          ts: Date.now(),
        }
      }
    })
  }

  const updateEntry = (key, patch) => {
    scheduleUpdate((next) => {
      const cur = next.entries[key]
      if (cur) next.entries[key] = { ...cur, ...patch, ts: Date.now() }
    })
  }

  const filtered = useMemo(() => {
    let items = CATALOG.filter((p) => p.kid === kidId)
    const f = filters
    if (f.retailers.length) items = items.filter((p) => f.retailers.includes(p.retailer))
    if (f.categories.length) items = items.filter((p) => f.categories.includes(p.category))
    if (f.colors.length) items = items.filter((p) => p.colors.some((c) => f.colors.includes(c)))
    if (f.dealsOnly) items = items.filter((p) => p.salePrice != null)
    if (f.price) {
      items = items.filter((p) => {
        const price = p.salePrice ?? p.price
        if (f.price === 'under20') return price < 20
        if (f.price === '20to40') return price >= 20 && price <= 40
        return price > 40
      })
    }
    if (f.search.trim()) {
      const q = f.search.trim().toLowerCase()
      items = items.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.category.includes(q) ||
          RETAILERS[p.retailer].name.toLowerCase().includes(q),
      )
    }
    if (f.sort === 'priceAsc') items = [...items].sort((a, b) => (a.salePrice ?? a.price) - (b.salePrice ?? b.price))
    if (f.sort === 'priceDesc') items = [...items].sort((a, b) => (b.salePrice ?? b.price) - (a.salePrice ?? a.price))
    return items
  }, [kidId, filters])

  if (!profile) {
    return (
      <Login
        onDone={(p) => {
          localStorage.setItem(PROFILE_KEY, JSON.stringify(p))
          setProfile(p)
        }}
      />
    )
  }

  const kidCounts = Object.fromEntries(
    KID_IDS.map((id) => [id, activeEntries.filter((e) => e.kid === id && !e.purchased).length]),
  )

  return (
    <div className="app" data-kid={kidId}>
      <Header
        profile={profile}
        kid={kid}
        kidId={kidId}
        kidCounts={kidCounts}
        onKid={setKidId}
        listCount={activeEntries.filter((e) => !e.purchased).length}
        syncState={syncState}
        onOpenList={() => setDrawerOpen(true)}
        onSignOut={() => {
          localStorage.removeItem(PROFILE_KEY)
          setProfile(null)
        }}
      />

      <section className="retailer-strip">
        <span className="strip-label">Live stock in {kid.name}'s size:</span>
        {RETAILER_IDS.map((rid) => {
          const r = RETAILERS[rid]
          return (
            <a
              key={rid}
              className="retailer-pill"
              style={{ '--rc': r.color, '--rb': r.bg }}
              href={r.search(`${kid.searchWord} clothes`)}
              target="_blank"
              rel="noreferrer"
              title={`${r.name} — ${r.sizeNote[kidId]}`}
            >
              <b>{r.short}</b> {r.name}
              <small>{r.sizeNote[kidId]}</small>
            </a>
          )
        })}
      </section>

      <FilterBar filters={filters} setFilters={setFilters} kid={kid} resultCount={filtered.length} />

      <main className="grid">
        {filtered.map((item) => {
          const key = entryKey(item)
          const entry = doc.entries[key]
          return (
            <ProductCard
              key={item.id}
              item={item}
              kid={kid}
              retailer={RETAILERS[item.retailer]}
              selected={!!entry && !entry.removed}
              onToggle={() => toggleItem(item)}
              href={itemSearchUrl(item, kid)}
            />
          )
        })}
        {filtered.length === 0 && (
          <div className="empty">
            <span>🧺</span>
            <p>Nothing matches those filters — try clearing a couple.</p>
            <button onClick={() => setFilters(EMPTY_FILTERS)}>Clear all filters</button>
          </div>
        )}
      </main>

      <ListDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        entries={activeEntries}
        updateEntry={updateEntry}
        profile={profile}
      />
    </div>
  )
}
