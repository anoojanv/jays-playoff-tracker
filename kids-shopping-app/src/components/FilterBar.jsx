import { RETAILERS, RETAILER_IDS } from '../data/retailers.js'
import { CATEGORIES, COLOR_SWATCHES } from '../data/catalog.js'

const PRICE_BANDS = [
  { id: 'under20', label: 'Under $20' },
  { id: '20to40', label: '$20–40' },
  { id: 'over40', label: '$40+' },
]

function toggleIn(list, value) {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value]
}

export default function FilterBar({ filters, setFilters, kid, resultCount }) {
  const set = (patch) => setFilters((f) => ({ ...f, ...patch }))
  const activeCount =
    filters.retailers.length + filters.categories.length + filters.colors.length +
    (filters.price ? 1 : 0) + (filters.dealsOnly ? 1 : 0)

  return (
    <section className="filters">
      <div className="filter-row top">
        <input
          className="search"
          placeholder={`Search ${kid.name}'s picks… (e.g. "hoodie", "Zara")`}
          value={filters.search}
          onChange={(e) => set({ search: e.target.value })}
        />
        <select value={filters.sort} onChange={(e) => set({ sort: e.target.value })}>
          <option value="featured">Featured</option>
          <option value="priceAsc">Price: low → high</option>
          <option value="priceDesc">Price: high → low</option>
        </select>
        <span className="result-count">{resultCount} item{resultCount === 1 ? '' : 's'}</span>
        {activeCount > 0 && (
          <button
            className="clear-filters"
            onClick={() =>
              set({ retailers: [], categories: [], colors: [], price: null, dealsOnly: false })
            }
          >
            Clear filters ({activeCount})
          </button>
        )}
      </div>

      <div className="filter-row chips">
        <span className="chip-label">Store</span>
        {RETAILER_IDS.map((rid) => (
          <button
            key={rid}
            className={`chip ${filters.retailers.includes(rid) ? 'on' : ''}`}
            style={{ '--rc': RETAILERS[rid].color }}
            onClick={() => set({ retailers: toggleIn(filters.retailers, rid) })}
          >
            {RETAILERS[rid].name}
          </button>
        ))}
      </div>

      <div className="filter-row chips">
        <span className="chip-label">Type</span>
        {CATEGORIES.filter((c) => !(kid.id === 'aiden' && c.id === 'dresses')).map((c) => (
          <button
            key={c.id}
            className={`chip ${filters.categories.includes(c.id) ? 'on' : ''}`}
            onClick={() => set({ categories: toggleIn(filters.categories, c.id) })}
          >
            {c.emoji} {c.label}
          </button>
        ))}
      </div>

      <div className="filter-row chips">
        <span className="chip-label">Price</span>
        {PRICE_BANDS.map((b) => (
          <button
            key={b.id}
            className={`chip ${filters.price === b.id ? 'on' : ''}`}
            onClick={() => set({ price: filters.price === b.id ? null : b.id })}
          >
            {b.label}
          </button>
        ))}
        <button
          className={`chip sale ${filters.dealsOnly ? 'on' : ''}`}
          onClick={() => set({ dealsOnly: !filters.dealsOnly })}
        >
          🔥 On sale
        </button>
        <span className="chip-label">Colour</span>
        {Object.keys(COLOR_SWATCHES).map((c) => (
          <button
            key={c}
            title={c}
            className={`swatch ${filters.colors.includes(c) ? 'on' : ''}`}
            style={{ background: COLOR_SWATCHES[c] }}
            onClick={() => set({ colors: toggleIn(filters.colors, c) })}
          />
        ))}
      </div>
    </section>
  )
}
