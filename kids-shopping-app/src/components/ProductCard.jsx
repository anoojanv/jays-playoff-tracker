import { COLOR_SWATCHES } from '../data/catalog.js'

const TAG_LABEL = {
  deal: { text: '🔥 Sale', cls: 'tag-deal' },
  bestseller: { text: '⭐ Popular', cls: 'tag-best' },
  new: { text: '✨ New', cls: 'tag-new' },
}

export default function ProductCard({ item, kid, retailer, selected, onToggle, href }) {
  const price = item.salePrice ?? item.price
  const tag = TAG_LABEL[item.tag]
  return (
    <article className={`card ${selected ? 'selected' : ''}`}>
      <div className="card-art" style={{ background: retailer.bg }}>
        <span className="card-emoji">{item.emoji}</span>
        {tag && <span className={`tag ${tag.cls}`}>{tag.text}</span>}
        <button
          className={`heart ${selected ? 'on' : ''}`}
          onClick={onToggle}
          title={selected ? 'Remove from our list' : 'Add to our list'}
        >
          {selected ? '✓' : '+'}
        </button>
      </div>
      <div className="card-body">
        <div className="card-retailer" style={{ color: retailer.color }}>
          {retailer.name}
          <span className="card-size">{retailer.sizeNote[kid.id]}</span>
        </div>
        <h3>{item.name}</h3>
        <div className="card-foot">
          <div className="price">
            <b>${price.toFixed(2)}</b>
            {item.salePrice != null && <s>${item.price.toFixed(2)}</s>}
          </div>
          <div className="colors">
            {item.colors.map((c) => (
              <i key={c} title={c} style={{ background: COLOR_SWATCHES[c] }} />
            ))}
          </div>
        </div>
        <a className="live-link" href={href} target="_blank" rel="noreferrer">
          Check live stock at {retailer.name} ↗
        </a>
      </div>
    </article>
  )
}
