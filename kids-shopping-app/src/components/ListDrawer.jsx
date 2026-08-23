import { useMemo, useState } from 'react'
import { KIDS } from '../data/kids.js'
import { RETAILERS, RETAILER_IDS, itemSearchUrl } from '../data/retailers.js'
import { CATALOG } from '../data/catalog.js'

const byId = Object.fromEntries(CATALOG.map((p) => [p.id, p]))

export default function ListDrawer({ open, onClose, entries, updateEntry, profile }) {
  const [copied, setCopied] = useState(false)

  const groups = useMemo(() => {
    const g = {}
    for (const e of entries) {
      const item = byId[e.productId]
      if (!item) continue
      ;(g[item.retailer] ||= []).push({ entry: e, item })
    }
    for (const rid of Object.keys(g)) {
      g[rid].sort((a, b) => a.item.kid.localeCompare(b.item.kid))
    }
    return g
  }, [entries])

  const total = entries.reduce((sum, e) => {
    const item = byId[e.productId]
    if (!item || e.purchased) return sum
    return sum + (item.salePrice ?? item.price) * (e.qty || 1)
  }, 0)
  const doneCount = entries.filter((e) => e.purchased).length

  const copyList = async () => {
    const lines = []
    for (const rid of RETAILER_IDS) {
      if (!groups[rid]) continue
      lines.push(`\n${RETAILERS[rid].name} (${RETAILERS[rid].home}):`)
      for (const { entry, item } of groups[rid]) {
        const kid = KIDS[item.kid]
        lines.push(
          `  ${entry.purchased ? '[x]' : '[ ]'} ${kid.name} — ${item.name} x${entry.qty || 1} · ${RETAILERS[rid].sizeNote[item.kid]} · $${(item.salePrice ?? item.price).toFixed(2)}`,
        )
      }
    }
    try {
      await navigator.clipboard.writeText(`Back to School list:${lines.join('\n')}`)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // clipboard blocked — no-op
    }
  }

  return (
    <>
      <div className={`drawer-scrim ${open ? 'show' : ''}`} onClick={onClose} />
      <aside className={`drawer ${open ? 'open' : ''}`}>
        <div className="drawer-head">
          <h2>🛒 Our shared list</h2>
          <button className="drawer-close" onClick={onClose}>✕</button>
        </div>

        {entries.length === 0 ? (
          <div className="drawer-empty">
            <span>🧺</span>
            <p>Nothing picked yet. Tap <b>+</b> on any item to add it — {profile.name === 'Anoojan' ? 'Mom' : 'Anoojan'} will see it here too.</p>
          </div>
        ) : (
          <>
            <div className="drawer-summary">
              <div>
                <b>${total.toFixed(2)}</b>
                <small>est. total left to buy</small>
              </div>
              <div>
                <b>{entries.length - doneCount}</b>
                <small>to buy</small>
              </div>
              <div>
                <b>{doneCount}</b>
                <small>done ✓</small>
              </div>
              <button className="copy-btn" onClick={copyList}>
                {copied ? 'Copied ✓' : '📋 Copy list'}
              </button>
            </div>

            <div className="drawer-groups">
              {RETAILER_IDS.filter((rid) => groups[rid]).map((rid) => {
                const r = RETAILERS[rid]
                const rows = groups[rid]
                const sub = rows.reduce(
                  (s, { entry, item }) =>
                    entry.purchased ? s : s + (item.salePrice ?? item.price) * (entry.qty || 1),
                  0,
                )
                return (
                  <div className="group" key={rid}>
                    <div className="group-head" style={{ '--rc': r.color }}>
                      <b>{r.name}</b>
                      <span>${sub.toFixed(2)}</span>
                      <a className="checkout" href={r.home} target="_blank" rel="noreferrer">
                        Checkout at {r.short} ↗
                      </a>
                    </div>
                    {rows.map(({ entry, item }) => {
                      const kid = KIDS[item.kid]
                      return (
                        <div className={`row ${entry.purchased ? 'done' : ''}`} key={entry.key}>
                          <button
                            className={`check ${entry.purchased ? 'on' : ''}`}
                            title={entry.purchased ? 'Mark as not bought' : 'Mark as bought'}
                            onClick={() => updateEntry(entry.key, { purchased: !entry.purchased })}
                          >
                            {entry.purchased ? '✓' : ''}
                          </button>
                          <span className="row-kid" style={{ background: kid.accentSoft }}>
                            {kid.emoji} {kid.name}
                          </span>
                          <div className="row-main">
                            <a href={itemSearchUrl(item, kid)} target="_blank" rel="noreferrer">
                              {item.emoji} {item.name} ↗
                            </a>
                            <small>
                              {r.sizeNote[item.kid]} · added by {entry.addedBy}
                            </small>
                          </div>
                          <div className="qty">
                            <button onClick={() => updateEntry(entry.key, { qty: Math.max(1, (entry.qty || 1) - 1) })}>−</button>
                            <span>{entry.qty || 1}</span>
                            <button onClick={() => updateEntry(entry.key, { qty: (entry.qty || 1) + 1 })}>+</button>
                          </div>
                          <span className="row-price">
                            ${((byId[entry.productId].salePrice ?? byId[entry.productId].price) * (entry.qty || 1)).toFixed(2)}
                          </span>
                          <button
                            className="remove"
                            title="Remove"
                            onClick={() => updateEntry(entry.key, { removed: true })}
                          >
                            🗑
                          </button>
                        </div>
                      )
                    })}
                  </div>
                )
              })}
            </div>
            <p className="drawer-fine">
              Each item link opens a live, in-size search on the store's Canadian site — add it to
              that store's cart there, then hit <b>Checkout</b> once per store.
            </p>
          </>
        )}
      </aside>
    </>
  )
}
